"""Read models for the Team page: scorecard, issues, to-dos, rocks."""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.base import Executable

from app import models, rules
from app.errors import not_found
from app.schemas import (
    CellOut,
    CompletionOut,
    GoalOut,
    IssueOut,
    MeasurableRowOut,
    MilestoneOut,
    RockOut,
    RocksOut,
    ScorecardOut,
    SourceOut,
    TodoOut,
    TodosOut,
    UserRef,
)
from app.services.common import user_refs


def _pairs(session: Session, stmt: Executable) -> dict[str, str]:
    """Two-column query as a dict."""
    return {str(key): str(value) for key, value in session.execute(stmt).all()}


def goal_of(m: models.Measurable) -> rules.Goal:
    """Domain goal for a measurable row."""
    return rules.Goal(m.goal_type, m.goal_value, m.goal_min, m.goal_max)


def team_measurables(session: Session, team_id: str) -> list[models.Measurable]:
    """Measurables of a team in display order."""
    return list(
        session.scalars(
            select(models.Measurable).where(models.Measurable.team_id == team_id).order_by(models.Measurable.position)
        )
    )


def scorecard(session: Session, team_id: str, now: datetime, tz: ZoneInfo) -> ScorecardOut:
    """Measurables x last 13 weeks with computed statuses (3 queries, no N+1)."""
    weeks = rules.last_n_weeks(now, tz)
    current = weeks[-1]
    measurables = team_measurables(session, team_id)
    ids = [m.id for m in measurables]
    scores = {
        (s.measurable_id, s.week_start): s
        for s in session.scalars(
            select(models.Score).where(models.Score.measurable_id.in_(ids), models.Score.week_start.in_(weeks))
        )
    }
    open_issues = {
        (i.source_measurable_id, i.source_week_start): i.id
        for i in session.scalars(
            select(models.Issue).where(
                models.Issue.team_id == team_id,
                models.Issue.solved_at.is_(None),
                models.Issue.source_measurable_id.is_not(None),
            )
        )
    }
    owners = user_refs(session, [m.owner_id for m in measurables])
    rows = []
    for m in measurables:
        goal = goal_of(m)
        cells = []
        for week in weeks:
            score = scores.get((m.id, week))
            value: Decimal | None = score.value if score else None
            cells.append(
                CellOut(
                    week_start=week,
                    value=value,
                    status=rules.measurable_status(goal, value, week, current).value,
                    version=score.version if score else None,
                    issue_id=open_issues.get((m.id, week)),
                )
            )
        rows.append(
            MeasurableRowOut(
                id=m.id,
                name=m.name,
                owner=owners[m.owner_id],
                unit=m.unit,
                goal=GoalOut(type=m.goal_type, value=m.goal_value, min=m.goal_min, max=m.goal_max),
                cells=cells,
            )
        )
    return ScorecardOut(
        team_id=team_id,
        current_week=current,
        last_closed_week=rules.last_closed_week_start(now, tz),
        weeks=weeks,
        measurables=rows,
    )


def issue_out(
    issue: models.Issue,
    owners: dict[str, UserRef],
    measurable_names: dict[str, str],
) -> IssueOut:
    """Serialize an Issue row."""
    source = None
    if issue.source_measurable_id and issue.source_week_start:
        source = SourceOut(
            measurable_id=issue.source_measurable_id,
            measurable_name=measurable_names.get(issue.source_measurable_id, issue.source_measurable_id),
            week_start=issue.source_week_start,
        )
    return IssueOut(
        id=issue.id,
        team_id=issue.team_id,
        title=issue.title,
        owner=owners[issue.owner_id],
        priority=issue.priority,
        created_at=issue.created_at,
        solved_at=issue.solved_at,
        resolution_note=issue.resolution_note,
        source=source,
        version=issue.version,
    )


def issues(session: Session, team_id: str, *, solved: bool) -> list[IssueOut]:
    """Unsolved Issues in Issue order, or solved Issues newest-solved first."""
    stmt = select(models.Issue).where(models.Issue.team_id == team_id)
    stmt = stmt.where(models.Issue.solved_at.is_not(None) if solved else models.Issue.solved_at.is_(None))
    rows = list(session.scalars(stmt))
    if solved:
        rows.sort(key=lambda i: (i.solved_at or i.created_at, i.seq), reverse=True)
    else:
        rows.sort(key=lambda i: rules.issue_sort_key(i.priority, i.created_at, i.seq, i.id))
    owners = user_refs(session, [i.owner_id for i in rows])
    names = _pairs(
        session, select(models.Measurable.id, models.Measurable.name).where(models.Measurable.team_id == team_id)
    )
    return [issue_out(i, owners, names) for i in rows]


def get_issue_out(session: Session, issue: models.Issue) -> IssueOut:
    """Serialize a single Issue."""
    owners = user_refs(session, [issue.owner_id])
    names = _pairs(
        session, select(models.Measurable.id, models.Measurable.name).where(models.Measurable.team_id == issue.team_id)
    )
    return issue_out(issue, owners, names)


def todo_facts(rows: list[models.Todo]) -> list[rules.TodoFacts]:
    """Rule inputs for To-Do rows."""
    return [rules.TodoFacts(t.id, t.due_date, t.done_at) for t in rows]


def todos(session: Session, team_id: str, now: datetime, tz: ZoneInfo) -> TodosOut:
    """To-Dos (open first, by due date) plus the last closed week's completion rate."""
    rows = list(session.scalars(select(models.Todo).where(models.Todo.team_id == team_id)))
    today = rules.local_date(now, tz)
    rows.sort(key=lambda t: (t.done_at is not None, t.due_date, t.seq))
    owners = user_refs(session, [t.owner_id for t in rows])
    titles = _pairs(session, select(models.Issue.id, models.Issue.title).where(models.Issue.team_id == team_id))
    week = rules.last_closed_week_start(now, tz)
    rate = rules.todo_completion(todo_facts(rows), week, tz)
    return TodosOut(
        todos=[
            TodoOut(
                id=t.id,
                team_id=t.team_id,
                title=t.title,
                owner=owners[t.owner_id],
                due_date=t.due_date,
                done_at=t.done_at,
                created_at=t.created_at,
                source_issue_id=t.source_issue_id,
                source_issue_title=titles.get(t.source_issue_id) if t.source_issue_id else None,
                overdue=rules.is_overdue(t.due_date, t.done_at, today),
                created_in_meeting_id=t.created_in_meeting_id,
            )
            for t in rows
        ],
        last_closed_week=week,
        completion=None
        if rate is None
        else CompletionOut(
            week_start=week,
            due=rate.due,
            done=rate.done,
            rate_percent=rate.rate_percent,
            meets_target=rate.meets_target,
        ),
    )


def rocks(session: Session, team_id: str, now: datetime, tz: ZoneInfo) -> RocksOut:
    """Current quarter's Rocks with computed status/progress and their Milestones."""
    today = rules.local_date(now, tz)
    quarter = rules.quarter_of(today)
    rock_rows = list(
        session.scalars(
            select(models.Rock)
            .where(models.Rock.team_id == team_id, models.Rock.quarter == quarter)
            .order_by(models.Rock.id)
        )
    )
    by_rock: dict[str, list[models.Milestone]] = defaultdict(list)
    for ms in session.scalars(
        select(models.Milestone)
        .where(models.Milestone.rock_id.in_([r.id for r in rock_rows]))
        .order_by(models.Milestone.position)
    ):
        by_rock[ms.rock_id].append(ms)
    owners = user_refs(session, [r.owner_id for r in rock_rows])
    result = []
    for rock in rock_rows:
        pairs = [(ms.due_date, ms.done) for ms in by_rock[rock.id]]
        result.append(
            RockOut(
                id=rock.id,
                title=rock.title,
                owner=owners[rock.owner_id],
                quarter=rock.quarter,
                status=rules.rock_status(rock.status, pairs, today).value,
                progress_percent=rules.rock_progress(rock.status, pairs),
                milestones=[
                    MilestoneOut(
                        id=ms.id,
                        title=ms.title,
                        due_date=ms.due_date,
                        done=ms.done,
                        past_due=not ms.done and ms.due_date < today,
                    )
                    for ms in by_rock[rock.id]
                ],
            )
        )
    return RocksOut(quarter=quarter, rocks=result)


def require_in_team[T: models.Base](row: T | None, team_id: str) -> T:
    """404 unless the row exists and belongs to ``team_id`` (prevents cross-team id guessing)."""
    if row is None or getattr(row, "team_id", None) != team_id:
        raise not_found()
    return row


def week_label(day: date) -> str:
    """Human label such as ``Nov 2`` used in generated Issue titles."""
    return f"{day:%b} {day.day}"
