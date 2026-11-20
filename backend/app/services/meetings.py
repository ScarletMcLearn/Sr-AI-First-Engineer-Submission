"""Level 10 meeting lifecycle. PostgreSQL is the only owner of meeting state.

Every transition runs in one short transaction that first locks the meeting row
(``SELECT ... FOR UPDATE``), validates, mutates, bumps ``version`` and queues a ``NOTIFY``
that is delivered on commit. ``version`` is monotonic, so clients can discard stale or
out-of-order state.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models, rules
from app.auth import Principal
from app.clock import Clocks
from app.errors import conflict, forbidden, not_found
from app.schemas import (
    AttendeeOut,
    MeetingListItemOut,
    MeetingStateOut,
    MeetingSummaryOut,
    SectionOut,
    UserOut,
    UserRef,
)
from app.services.common import new_id, notify
from app.summary import MeasurableFacts, build_summary

SECTIONS: tuple[tuple[str, str, int], ...] = (
    ("scorecard", "Scorecard", 5 * 60),
    ("ids", "IDS", 60 * 60),
    ("conclude", "Conclude", 10 * 60),
)


def _lock(session: Session, meeting_id: str) -> models.Meeting:
    meeting = session.scalars(select(models.Meeting).where(models.Meeting.id == meeting_id).with_for_update()).first()
    if meeting is None:
        raise not_found("Meeting not found")
    return meeting


def _record(
    session: Session, meeting: models.Meeting, event_type: str, at: datetime, payload: dict[str, object]
) -> None:
    """Bump the version, append the event log row and queue the realtime notification."""
    meeting.version += 1
    session.add(models.MeetingEvent(meeting_id=meeting.id, type=event_type, payload=payload, created_at=at))
    notify(
        session,
        {
            "type": "meeting",
            "event": event_type,
            "meeting_id": meeting.id,
            "team_id": meeting.team_id,
            "version": meeting.version,
        },
    )


def state(session: Session, meeting: models.Meeting, timer_now: datetime) -> MeetingStateOut:
    """Authoritative state; elapsed time is computed here from the server's clock only."""
    section_key, _, planned = SECTIONS[meeting.section_index]
    reference = meeting.ended_at or timer_now
    elapsed = max(0, int((reference - meeting.section_started_at).total_seconds()))
    users = {u.id: u for u in session.scalars(select(models.User))}
    ratings = {
        r.user_id: r.rating
        for r in session.scalars(select(models.MeetingRating).where(models.MeetingRating.meeting_id == meeting.id))
    }
    attendee_rows = list(
        session.scalars(
            select(models.MeetingAttendee)
            .where(models.MeetingAttendee.meeting_id == meeting.id)
            .order_by(models.MeetingAttendee.joined_at, models.MeetingAttendee.user_id)
        )
    )
    facilitator = users[meeting.facilitator_id]
    return MeetingStateOut(
        id=meeting.id,
        team_id=meeting.team_id,
        status=meeting.status,
        facilitator=UserRef(id=facilitator.id, name=facilitator.name),
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        version=meeting.version,
        scorecard_week=meeting.scorecard_week,
        sections=[SectionOut(key=k, title=t, planned_seconds=s) for k, t, s in SECTIONS],
        section_index=meeting.section_index,
        section_key=section_key,
        section_started_at=meeting.section_started_at,
        server_time=timer_now,
        section_elapsed_seconds=elapsed,
        section_planned_seconds=planned,
        overtime_seconds=max(0, elapsed - planned),
        attendees=[
            AttendeeOut(
                user=UserOut(id=u.id, name=u.name, email=u.email, role=u.role),
                joined_at=a.joined_at,
                rating=ratings.get(a.user_id),
            )
            for a in attendee_rows
            for u in [users[a.user_id]]
        ],
        average_rating=_average(ratings.values()),
        summary=MeetingSummaryOut.model_validate(meeting.summary) if meeting.summary else None,
    )


def _average(values: object) -> float | None:
    average = rules.average_rating(list(values))  # type: ignore[call-overload]
    return None if average is None else float(average)


def get_state(session: Session, meeting_id: str, clocks: Clocks) -> MeetingStateOut:
    """Current state of one meeting."""
    meeting = session.get(models.Meeting, meeting_id)
    if meeting is None:
        raise not_found("Meeting not found")
    return state(session, meeting, clocks.timer.now())


def meeting_team(session: Session, meeting_id: str) -> str:
    """Team id of a meeting (404 if unknown) - used for authorization before any other work."""
    team_id = session.scalars(select(models.Meeting.team_id).where(models.Meeting.id == meeting_id)).first()
    if team_id is None:
        raise not_found("Meeting not found")
    return team_id


def active_meeting(session: Session, team_id: str, clocks: Clocks) -> MeetingStateOut | None:
    """The team's active meeting, if any."""
    meeting = session.scalars(
        select(models.Meeting).where(models.Meeting.team_id == team_id, models.Meeting.status == "active")
    ).first()
    return state(session, meeting, clocks.timer.now()) if meeting else None


def list_meetings(session: Session, team_id: str) -> list[MeetingListItemOut]:
    """Meetings for a team, newest first."""
    rows = list(
        session.scalars(
            select(models.Meeting).where(models.Meeting.team_id == team_id).order_by(models.Meeting.started_at.desc())
        )
    )
    names = {u.id: u.name for u in session.scalars(select(models.User))}
    return [
        MeetingListItemOut(
            id=m.id,
            status=m.status,
            facilitator=UserRef(id=m.facilitator_id, name=names[m.facilitator_id]),
            started_at=m.started_at,
            ended_at=m.ended_at,
        )
        for m in rows
    ]


def start(session: Session, principal: Principal, team_id: str, clocks: Clocks, tz: ZoneInfo) -> MeetingStateOut:
    """Start a meeting; the starter becomes facilitator and first attendee.

    The partial unique index ``uq_meetings_one_active_per_team`` makes concurrent starts safe:
    exactly one INSERT succeeds, the others get a clean 409.
    """
    started = clocks.timer.now()
    table = models.table_of(models.Meeting)
    meeting_id = new_id("mt")
    inserted = session.execute(
        insert(table)
        .values(
            id=meeting_id,
            team_id=team_id,
            facilitator_id=principal.user.id,
            status="active",
            started_at=started,
            section_index=0,
            section_started_at=started,
            version=1,
            scorecard_week=rules.last_closed_week_start(clocks.business.now(), tz),
        )
        .on_conflict_do_nothing(index_elements=["team_id"], index_where=table.c.status == "active")
        .returning(table.c.id)
    ).scalar_one_or_none()
    if inserted is None:
        session.rollback()
        raise conflict("This team already has an active meeting", "meeting_already_active")
    session.add(models.MeetingAttendee(meeting_id=meeting_id, user_id=principal.user.id, joined_at=started))
    session.flush()
    meeting = session.get_one(models.Meeting, meeting_id)
    _record(session, meeting, "started", started, {"facilitator_id": principal.user.id})
    session.commit()
    return state(session, meeting, started)


def join(session: Session, principal: Principal, meeting_id: str, clocks: Clocks) -> MeetingStateOut:
    """Join (idempotent). Anyone who can read the team may join, Observers included."""
    now = clocks.timer.now()
    meeting = _lock(session, meeting_id)
    if meeting.status != "active":
        raise conflict("The meeting has ended", "meeting_ended")
    inserted = session.execute(
        insert(models.table_of(models.MeetingAttendee))
        .values(meeting_id=meeting_id, user_id=principal.user.id, joined_at=now)
        .on_conflict_do_nothing()
        .returning(models.table_of(models.MeetingAttendee).c.user_id)
    ).scalar_one_or_none()
    if inserted is not None:
        _record(session, meeting, "joined", now, {"user_id": principal.user.id})
    session.commit()
    return state(session, meeting, now)


def advance(
    session: Session, principal: Principal, meeting_id: str, expected_version: int | None, clocks: Clocks
) -> MeetingStateOut:
    """Move to the next agenda section (facilitator only). Never happens automatically."""
    now = clocks.timer.now()
    meeting = _lock(session, meeting_id)
    _require_facilitator(meeting, principal)
    _require_active(meeting, expected_version)
    if meeting.section_index >= len(SECTIONS) - 1:
        raise conflict("Already in the last section", "last_section")
    meeting.section_index += 1
    meeting.section_started_at = now
    _record(session, meeting, "advanced", now, {"section": SECTIONS[meeting.section_index][0]})
    session.commit()
    return state(session, meeting, now)


def end(
    session: Session, principal: Principal, meeting_id: str, expected_version: int | None, clocks: Clocks, tz: ZoneInfo
) -> MeetingStateOut:
    """End the meeting at any time (facilitator only) and persist the immutable summary snapshot."""
    now = clocks.timer.now()
    meeting = _lock(session, meeting_id)
    _require_facilitator(meeting, principal)
    _require_active(meeting, expected_version)
    meeting.summary = _snapshot(session, meeting, clocks.business.now(), tz)
    meeting.status = "ended"
    meeting.ended_at = now
    _record(session, meeting, "ended", now, {})
    session.commit()
    return state(session, meeting, now)


def rate(session: Session, principal: Principal, meeting_id: str, rating: int, clocks: Clocks) -> MeetingStateOut:
    """Set or change the caller's rating; only in the Conclude section of an active meeting."""
    now = clocks.timer.now()
    meeting = _lock(session, meeting_id)
    if not principal.can_write:
        raise forbidden("Observers cannot rate meetings")
    if meeting.status != "active":
        raise conflict("Ratings are final once the meeting has ended", "meeting_ended")
    attendee = session.get(models.MeetingAttendee, (meeting_id, principal.user.id))
    if attendee is None:
        raise forbidden("Join the meeting before rating it")
    if SECTIONS[meeting.section_index][0] != "conclude":
        raise conflict("Ratings open in the Conclude section", "rating_not_open")
    table = models.table_of(models.MeetingRating)
    session.execute(
        insert(table)
        .values(meeting_id=meeting_id, user_id=principal.user.id, rating=rating, updated_at=now)
        .on_conflict_do_update(index_elements=["meeting_id", "user_id"], set_={"rating": rating, "updated_at": now})
    )
    _record(session, meeting, "rated", now, {"user_id": principal.user.id})
    session.commit()
    return state(session, meeting, now)


def summary(session: Session, meeting_id: str) -> MeetingSummaryOut:
    """Persisted summary of an ended meeting."""
    meeting = session.get(models.Meeting, meeting_id)
    if meeting is None:
        raise not_found("Meeting not found")
    if meeting.summary is None:
        raise conflict("The meeting has not ended yet", "meeting_active")
    return MeetingSummaryOut.model_validate(meeting.summary)


def _require_facilitator(meeting: models.Meeting, principal: Principal) -> None:
    if meeting.facilitator_id != principal.user.id:
        raise forbidden("Only the facilitator can do that")


def _require_active(meeting: models.Meeting, expected_version: int | None) -> None:
    if meeting.status != "active":
        raise conflict("The meeting has ended", "meeting_ended")
    if expected_version is not None and expected_version != meeting.version:
        raise conflict(
            "The meeting changed; refresh and try again", "stale_version", {"current_version": meeting.version}
        )


def _snapshot(session: Session, meeting: models.Meeting, business_now: datetime, tz: ZoneInfo) -> dict[str, object]:
    """Compute the end-of-meeting summary from current data (persisted, then never recomputed)."""
    measurables = list(session.scalars(select(models.Measurable).where(models.Measurable.team_id == meeting.team_id)))
    scores = {
        (s.measurable_id, s.week_start): s.value
        for s in session.scalars(
            select(models.Score).where(
                models.Score.measurable_id.in_([m.id for m in measurables]),
                models.Score.week_start == meeting.scorecard_week,
            )
        )
    }
    solved = list(session.scalars(select(models.Issue.id).where(models.Issue.solved_in_meeting_id == meeting.id)))
    created = list(session.scalars(select(models.Todo.id).where(models.Todo.created_in_meeting_id == meeting.id)))
    attendees = list(
        session.scalars(select(models.MeetingAttendee.user_id).where(models.MeetingAttendee.meeting_id == meeting.id))
    )
    ratings = list(
        session.scalars(select(models.MeetingRating.rating).where(models.MeetingRating.meeting_id == meeting.id))
    )
    return build_summary(
        scorecard_week=meeting.scorecard_week,
        as_of=business_now,
        tz=tz,
        measurables=[MeasurableFacts(m.id, rules_goal(m)) for m in measurables],
        scores=scores,
        issues_solved=solved,
        todos_created=created,
        attendee_ids=attendees,
        ratings=ratings,
    )


def rules_goal(m: models.Measurable) -> rules.Goal:
    """Domain goal for a measurable."""
    return rules.Goal(m.goal_type, m.goal_value, m.goal_min, m.goal_max)


def _noop() -> None:  # pragma: no cover
    text("SELECT 1")
