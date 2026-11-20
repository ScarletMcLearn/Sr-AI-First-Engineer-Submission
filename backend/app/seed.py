"""Idempotent seed loader.

Every insert uses ``ON CONFLICT DO NOTHING`` so re-running never duplicates rows and never
overwrites changes users made after the first load. Seed ids are preserved.
"""

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models, rules
from app.summary import MeasurableFacts, build_summary

DEFAULT_SEED_PATH = Path(__file__).resolve().parents[2] / "seed.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeedMeta(_Strict):
    """Seed metadata."""

    now: datetime
    timezone: str
    current_quarter: str
    notes: str


class SeedCompany(_Strict):
    """Company record."""

    id: str
    name: str
    timezone: str


class SeedTeam(_Strict):
    """Team record."""

    id: str
    name: str


class SeedUser(_Strict):
    """User record."""

    id: str
    name: str
    email: str
    role: Literal["admin", "team_member", "observer"]


class SeedMembership(_Strict):
    """Membership record."""

    user_id: str
    team_id: str


class SeedGoal(_Strict):
    """Goal record."""

    type: Literal["at_least", "at_most", "between", "exactly"]
    value: Decimal | None = None
    min: Decimal | None = None
    max: Decimal | None = None


class SeedMeasurable(_Strict):
    """Measurable record."""

    id: str
    team_id: str
    name: str
    owner_id: str
    unit: str
    goal: SeedGoal


class SeedScore(_Strict):
    """Score record."""

    measurable_id: str
    week_start: date
    value: Decimal


class SeedRock(_Strict):
    """Rock record."""

    id: str
    team_id: str
    title: str
    owner_id: str
    quarter: str
    status: Literal["on_track", "off_track", "complete"]


class SeedMilestone(_Strict):
    """Milestone record."""

    id: str
    rock_id: str
    title: str
    due_date: date
    done: bool


class SeedSource(_Strict):
    """Issue source."""

    measurable_id: str
    week_start: date


class SeedIssue(_Strict):
    """Issue record."""

    id: str
    team_id: str
    title: str
    owner_id: str
    priority: int | None
    created_at: datetime
    solved_at: datetime | None
    resolution_note: str | None
    source: SeedSource | None


class SeedTodo(_Strict):
    """To-Do record."""

    id: str
    team_id: str
    title: str
    owner_id: str
    due_date: date
    done_at: datetime | None
    source_issue_id: str | None
    created_at: datetime


class SeedRating(_Strict):
    """Meeting rating."""

    user_id: str
    rating: int


class SeedMeeting(_Strict):
    """Ended meeting record."""

    id: str
    team_id: str
    facilitator_id: str
    started_at: datetime
    ended_at: datetime
    attendee_ids: list[str]
    ratings: list[SeedRating]


class SeedData(_Strict):
    """Whole seed file."""

    meta: SeedMeta
    company: SeedCompany
    teams: list[SeedTeam]
    users: list[SeedUser]
    memberships: list[SeedMembership]
    measurables: list[SeedMeasurable]
    scores: list[SeedScore]
    rocks: list[SeedRock]
    milestones: list[SeedMilestone]
    issues: list[SeedIssue]
    todos: list[SeedTodo]
    meetings: list[SeedMeeting]


def load_seed_file(path: Path | None = None) -> SeedData:
    """Read and validate the seed file."""
    target = path or DEFAULT_SEED_PATH
    return SeedData.model_validate(json.loads(target.read_text(encoding="utf-8")))


def _insert(session: Session, model: type[models.Base], rows: list[dict[str, Any]]) -> int:
    """Insert rows, skipping existing ones; return the number actually inserted."""
    if not rows:
        return 0
    table = models.table_of(model)
    # Chunked so large files stay below the bind-parameter limit; RETURNING counts real inserts.
    inserted = 0
    for start in range(0, len(rows), 500):
        stmt = insert(table).values(rows[start : start + 500]).on_conflict_do_nothing().returning(text("1"))
        inserted += len(session.execute(stmt).all())
    return inserted


def _in_window(instant: datetime, start: datetime, end: datetime) -> bool:
    return start <= instant <= end


def load_seed(session: Session, data: SeedData) -> dict[str, int]:
    """Insert the seed data (idempotent). Returns inserted-row counts per table."""
    tz = ZoneInfo(data.company.timezone)
    counts: dict[str, int] = {}
    session.execute(text("SET LOCAL app.seeding = 'on'"))  # lets historical ratings be imported

    counts["companies"] = _insert(session, models.Company, [data.company.model_dump()])
    counts["users"] = _insert(
        session, models.User, [{**u.model_dump(), "company_id": data.company.id} for u in data.users]
    )
    counts["teams"] = _insert(
        session, models.Team, [{**t.model_dump(), "company_id": data.company.id} for t in data.teams]
    )
    counts["team_memberships"] = _insert(session, models.TeamMembership, [m.model_dump() for m in data.memberships])
    counts["measurables"] = _insert(
        session,
        models.Measurable,
        [
            {
                "id": m.id,
                "team_id": m.team_id,
                "name": m.name,
                "owner_id": m.owner_id,
                "unit": m.unit,
                "goal_type": m.goal.type,
                "goal_value": m.goal.value,
                "goal_min": m.goal.min,
                "goal_max": m.goal.max,
                "position": position,
            }
            for position, m in enumerate(data.measurables)
        ],
    )
    counts["scores"] = _insert(
        session,
        models.Score,
        [
            {"measurable_id": s.measurable_id, "week_start": s.week_start, "value": s.value, "version": 1}
            for s in data.scores
        ],
    )
    counts["rocks"] = _insert(session, models.Rock, [r.model_dump() for r in data.rocks])
    counts["milestones"] = _insert(
        session,
        models.Milestone,
        [{**m.model_dump(), "position": position} for position, m in enumerate(data.milestones)],
    )

    # Meetings first: Issues/To-Dos reference the meeting during which they were solved/created.
    scores = {(s.measurable_id, s.week_start): s.value for s in data.scores}
    meeting_rows: list[dict[str, Any]] = []
    attendee_rows: list[dict[str, Any]] = []
    rating_rows: list[dict[str, Any]] = []
    for meeting in data.meetings:
        issues_solved = [
            i.id
            for i in data.issues
            if i.team_id == meeting.team_id
            and i.solved_at is not None
            and _in_window(i.solved_at, meeting.started_at, meeting.ended_at)
        ]
        todos_created = [
            t.id
            for t in data.todos
            if t.team_id == meeting.team_id and _in_window(t.created_at, meeting.started_at, meeting.ended_at)
        ]
        week = rules.last_closed_week_start(meeting.started_at, tz)
        summary = build_summary(
            scorecard_week=week,
            as_of=meeting.started_at,
            tz=tz,
            measurables=[
                MeasurableFacts(
                    m.id,
                    rules.Goal(m.goal.type, m.goal.value, m.goal.min, m.goal.max),
                )
                for m in data.measurables
                if m.team_id == meeting.team_id
            ],
            scores=scores,
            issues_solved=issues_solved,
            todos_created=todos_created,
            attendee_ids=meeting.attendee_ids,
            ratings=[r.rating for r in meeting.ratings],
        )
        meeting_rows.append(
            {
                "id": meeting.id,
                "team_id": meeting.team_id,
                "facilitator_id": meeting.facilitator_id,
                "status": "ended",
                "started_at": meeting.started_at,
                "ended_at": meeting.ended_at,
                "section_index": 2,
                "section_started_at": meeting.started_at,
                "version": 1,
                "scorecard_week": week,
                "summary": summary,
            }
        )
        attendee_rows += [
            {"meeting_id": meeting.id, "user_id": uid, "joined_at": meeting.started_at} for uid in meeting.attendee_ids
        ]
        rating_rows += [
            {
                "meeting_id": meeting.id,
                "user_id": r.user_id,
                "rating": r.rating,
                "updated_at": meeting.ended_at,
            }
            for r in meeting.ratings
        ]
    counts["meetings"] = _insert(session, models.Meeting, meeting_rows)
    counts["meeting_attendees"] = _insert(session, models.MeetingAttendee, attendee_rows)
    counts["meeting_ratings"] = _insert(session, models.MeetingRating, rating_rows)

    def meeting_for(team_id: str, instant: datetime | None) -> str | None:
        if instant is None:
            return None
        for meeting in data.meetings:
            if meeting.team_id == team_id and _in_window(instant, meeting.started_at, meeting.ended_at):
                return meeting.id
        return None

    counts["issues"] = _insert(
        session,
        models.Issue,
        [
            {
                "id": i.id,
                "team_id": i.team_id,
                "title": i.title,
                "owner_id": i.owner_id,
                "priority": i.priority,
                "created_at": i.created_at,
                "solved_at": i.solved_at,
                "resolution_note": i.resolution_note,
                "source_measurable_id": i.source.measurable_id if i.source else None,
                "source_week_start": i.source.week_start if i.source else None,
                "solved_in_meeting_id": meeting_for(i.team_id, i.solved_at),
            }
            for i in data.issues
        ],
    )
    counts["todos"] = _insert(
        session,
        models.Todo,
        [
            {
                "id": t.id,
                "team_id": t.team_id,
                "title": t.title,
                "owner_id": t.owner_id,
                "due_date": t.due_date,
                "done_at": t.done_at,
                "source_issue_id": t.source_issue_id,
                "created_at": t.created_at,
                "created_in_meeting_id": meeting_for(t.team_id, t.created_at),
            }
            for t in data.todos
        ],
    )
    return counts


def expected_counts(data: SeedData) -> dict[str, int]:
    """Row counts the seed file should produce, for verification."""
    return {
        "companies": 1,
        "users": len(data.users),
        "teams": len(data.teams),
        "team_memberships": len(data.memberships),
        "measurables": len(data.measurables),
        "scores": len(data.scores),
        "rocks": len(data.rocks),
        "milestones": len(data.milestones),
        "meetings": len(data.meetings),
        "meeting_attendees": sum(len(m.attendee_ids) for m in data.meetings),
        "meeting_ratings": sum(len(m.ratings) for m in data.meetings),
        "issues": len(data.issues),
        "todos": len(data.todos),
    }


def seed_database(session: Session, path: Path | None = None) -> dict[str, int]:
    """Validate and load the seed file, commit, and log inserted counts to stderr."""
    data = load_seed_file(path)
    counts = load_seed(session, data)
    session.commit()
    print(f"seed: inserted {counts}", file=sys.stderr)
    return counts
