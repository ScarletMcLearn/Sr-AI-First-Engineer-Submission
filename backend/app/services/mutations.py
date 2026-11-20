"""Write operations for scores, Issues and To-Dos."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models, rules
from app.auth import Principal
from app.errors import conflict, invalid, not_found
from app.schemas import IssueOut, MakeIssueOut, TodoOut
from app.services import team_reads
from app.services.common import new_id, notify, user_refs
from app.services.team_reads import goal_of, week_label

MAKE_ISSUE_ATTEMPTS = 3


def _changed(session: Session, team_id: str, what: str) -> None:
    notify(session, {"type": "data_changed", "team_id": team_id, "resource": what})


def _validate_meeting(session: Session, team_id: str, meeting_id: str | None) -> str | None:
    """A mutation may be tagged with the team's *active* meeting it happened in.

    Takes a shared row lock (``FOR SHARE``) on the meeting that is held until the mutation commits.
    ``meetings.end`` needs ``FOR UPDATE`` on the same row, so ending the meeting (and snapshotting its
    summary) waits for in-flight attributed mutations, and a mutation that starts after the meeting
    ended sees ``status = 'ended'`` (the lock re-reads the committed row) and is rejected with 409.
    Lock order is always meeting row first, then Issue row; ``end`` only ever locks the meeting.
    Concurrent attributed mutations share the lock and do not serialise against each other.
    """
    if meeting_id is None:
        return None
    meeting = session.scalars(
        select(models.Meeting)
        .where(models.Meeting.id == meeting_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    ).first()
    if meeting is None or meeting.team_id != team_id:
        raise not_found("Meeting not found")
    if meeting.status != "active":
        raise conflict("The meeting has ended", "meeting_ended")
    return meeting_id


# ----------------------------------------------------------------- scores


def set_score(
    session: Session,
    principal: Principal,
    team_id: str,
    measurable_id: str,
    week_start: date,
    value: Decimal,
    expected_version: int | None,
    now: datetime,
    tz: ZoneInfo,
) -> tuple[Decimal, int]:
    """Upsert a score. Last save wins unless ``expected_version`` is supplied (lost-update protection)."""
    measurable = session.get(models.Measurable, measurable_id)
    if measurable is None or measurable.team_id != team_id:
        raise not_found("Measurable not found")
    if week_start not in rules.last_n_weeks(now, tz):
        raise invalid("week_start must be a Monday within the last 13 weeks (including the current week)")
    table = models.table_of(models.Score)
    values = {
        "measurable_id": measurable_id,
        "week_start": week_start,
        "value": value,
        "version": 1,
        "updated_at": now,
        "updated_by": principal.user.id,
    }
    if expected_version is None:
        stmt = (
            insert(table)
            .values(values)
            .on_conflict_do_update(
                index_elements=["measurable_id", "week_start"],
                set_={
                    "value": value,
                    "version": table.c.version + 1,
                    "updated_at": now,
                    "updated_by": principal.user.id,
                },
            )
            .returning(table.c.version)
        )
        version = session.execute(stmt).scalar_one()
    elif expected_version == 0:
        version = session.execute(
            insert(table).values(values).on_conflict_do_nothing().returning(table.c.version)
        ).scalar_one_or_none()
        if version is None:
            raise conflict("The score was changed by someone else", "stale_version")
    else:
        version = session.execute(
            update(table)
            .where(
                table.c.measurable_id == measurable_id,
                table.c.week_start == week_start,
                table.c.version == expected_version,
            )
            .values(value=value, version=table.c.version + 1, updated_at=now, updated_by=principal.user.id)
            .returning(table.c.version)
        ).scalar_one_or_none()
        if version is None:
            raise conflict("The score was changed by someone else", "stale_version")
    _changed(session, team_id, "scorecard")
    session.commit()
    return value, int(version)


# ----------------------------------------------------------------- issues


def make_issue(
    session: Session,
    principal: Principal,
    team_id: str,
    measurable_id: str,
    week_start: date,
    now: datetime,
    tz: ZoneInfo,
) -> MakeIssueOut:
    """Create the unsolved Issue for an off-track measurable-week, or return the existing one.

    Duplicate-free under concurrency: the insert relies on a partial unique index
    (``uq_issues_open_per_source``) with ``ON CONFLICT DO NOTHING``; the loser of a race simply
    reads the winner's row. There is no check-then-insert window.
    """
    measurable = session.get(models.Measurable, measurable_id)
    if measurable is None or measurable.team_id != team_id:
        raise not_found("Measurable not found")
    weeks = rules.last_n_weeks(now, tz)
    if week_start not in weeks:
        raise invalid("week_start must be a Monday within the last 13 weeks (including the current week)")
    score = session.get(models.Score, (measurable_id, week_start))
    status = rules.measurable_status(goal_of(measurable), score.value if score else None, week_start, weeks[-1])
    if status is not rules.Status.OFF_TRACK:
        raise invalid("Only off-track scores can be made into an Issue", {"status": status.value})

    table = models.table_of(models.Issue)
    open_filter = (
        table.c.source_measurable_id == measurable_id,
        table.c.source_week_start == week_start,
        table.c.solved_at.is_(None),
    )
    for _ in range(MAKE_ISSUE_ATTEMPTS):
        inserted = session.execute(
            insert(table)
            .values(
                id=new_id("i"),
                team_id=team_id,
                title=f"{measurable.name}, week of {week_label(week_start)}",
                owner_id=principal.user.id,
                priority=None,
                created_at=now,
                source_measurable_id=measurable_id,
                source_week_start=week_start,
            )
            .on_conflict_do_nothing(
                index_elements=["source_measurable_id", "source_week_start"],
                index_where=(table.c.solved_at.is_(None)) & (table.c.source_measurable_id.is_not(None)),
            )
            .returning(table.c.id)
        ).scalar_one_or_none()
        issue_id = inserted or session.execute(select(table.c.id).where(*open_filter)).scalar_one_or_none()
        if issue_id is not None:
            if inserted:
                _changed(session, team_id, "issues")
            session.commit()
            issue = session.get(models.Issue, issue_id)
            assert issue is not None
            return MakeIssueOut(issue=team_reads.get_issue_out(session, issue), created=inserted is not None)
        session.rollback()  # the conflicting Issue was solved between insert and read: retry
    raise conflict("Could not create the Issue; please retry", "retry")


def create_issue(
    session: Session,
    principal: Principal,
    team_id: str,
    title: str,
    priority: int | None,
    meeting_id: str | None,
    now: datetime,
) -> IssueOut:
    """Create a manual Issue owned by the creator."""
    _validate_meeting(session, team_id, meeting_id)
    issue = models.Issue(
        id=new_id("i"), team_id=team_id, title=title, owner_id=principal.user.id, priority=priority, created_at=now
    )
    session.add(issue)
    _changed(session, team_id, "issues")
    session.commit()
    return team_reads.get_issue_out(session, issue)


def _load_issue(session: Session, team_id: str, issue_id: str, *, lock: bool = False) -> models.Issue:
    stmt = select(models.Issue).where(models.Issue.id == issue_id, models.Issue.team_id == team_id)
    issue = session.scalars(stmt.with_for_update() if lock else stmt).first()
    if issue is None:
        raise not_found("Issue not found")
    return issue


def set_issue_priority(
    session: Session, team_id: str, issue_id: str, priority: int | None, expected_version: int | None
) -> IssueOut:
    """Set or clear priority; optional optimistic locking on ``expected_version``."""
    issue = _load_issue(session, team_id, issue_id, lock=True)
    if expected_version is not None and issue.version != expected_version:
        raise conflict("The Issue was changed by someone else", "stale_version", {"current_version": issue.version})
    issue.priority = priority
    issue.version += 1
    _changed(session, team_id, "issues")
    session.commit()
    return team_reads.get_issue_out(session, issue)


def solve_issue(
    session: Session, team_id: str, issue_id: str, note: str, meeting_id: str | None, now: datetime
) -> IssueOut:
    """Solve an Issue with a required note."""
    meeting = _validate_meeting(session, team_id, meeting_id)
    issue = _load_issue(session, team_id, issue_id, lock=True)
    if issue.solved_at is not None:
        raise conflict("The Issue is already solved", "already_solved")
    issue.solved_at = max(now, issue.created_at)
    issue.resolution_note = note
    issue.solved_in_meeting_id = meeting
    issue.version += 1
    _changed(session, team_id, "issues")
    session.commit()
    return team_reads.get_issue_out(session, issue)


# ------------------------------------------------------------------ to-dos


def _todo_out(session: Session, todo: models.Todo, today: date) -> TodoOut:
    owners = user_refs(session, [todo.owner_id])
    title = None
    if todo.source_issue_id:
        title = session.scalars(select(models.Issue.title).where(models.Issue.id == todo.source_issue_id)).first()
    return TodoOut(
        id=todo.id,
        team_id=todo.team_id,
        title=todo.title,
        owner=owners[todo.owner_id],
        due_date=todo.due_date,
        done_at=todo.done_at,
        created_at=todo.created_at,
        source_issue_id=todo.source_issue_id,
        source_issue_title=title,
        overdue=rules.is_overdue(todo.due_date, todo.done_at, today),
        created_in_meeting_id=todo.created_in_meeting_id,
    )


def create_todo_from_issue(
    session: Session,
    team_id: str,
    issue_id: str,
    title: str,
    owner_id: str,
    meeting_id: str | None,
    now: datetime,
    tz: ZoneInfo,
) -> TodoOut:
    """Create a To-Do linked to an Issue, due seven calendar days from today (company time)."""
    meeting = _validate_meeting(session, team_id, meeting_id)
    issue = _load_issue(session, team_id, issue_id)
    owner = session.get(models.User, owner_id)
    eligible = owner is not None and owner.role != "observer"
    if eligible and owner is not None and owner.role != "admin":
        eligible = session.get(models.TeamMembership, (owner_id, team_id)) is not None
    if not eligible:
        raise invalid("owner_id must be an Admin or a Team Member of this team", {"field": "owner_id"})
    today = rules.local_date(now, tz)
    todo = models.Todo(
        id=new_id("t"),
        team_id=team_id,
        title=title,
        owner_id=owner_id,
        due_date=today + timedelta(days=7),
        done_at=None,
        source_issue_id=issue.id,
        created_at=now,
        created_in_meeting_id=meeting,
    )
    session.add(todo)
    _changed(session, team_id, "todos")
    session.commit()
    return _todo_out(session, todo, today)


def set_todo_done(session: Session, team_id: str, todo_id: str, *, done: bool, now: datetime, tz: ZoneInfo) -> TodoOut:
    """Mark a To-Do done (keeping an earlier completion time) or undo completion."""
    todo = session.scalars(
        select(models.Todo).where(models.Todo.id == todo_id, models.Todo.team_id == team_id).with_for_update()
    ).first()
    if todo is None:
        raise not_found("To-Do not found")
    if done and todo.done_at is None:
        todo.done_at = now
    elif not done:
        todo.done_at = None
    _changed(session, team_id, "todos")
    session.commit()
    return _todo_out(session, todo, rules.local_date(now, tz))
