"""Rules report (README format). Every value is computed from persisted data and ``now``."""

from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, rules
from app.services.team_reads import goal_of, todo_facts


def format_instant(instant: datetime) -> str:
    """ISO 8601 UTC with a trailing ``Z``."""
    return instant.isoformat().replace("+00:00", "Z")


def build_report(session: Session, now: datetime, tz: ZoneInfo) -> dict[str, Any]:
    """Compute the full rules report for ``now`` (a UTC instant)."""
    weeks = rules.last_n_weeks(now, tz)
    current = weeks[-1]
    today = rules.local_date(now, tz)

    scores = {(s.measurable_id, s.week_start): s.value for s in session.scalars(select(models.Score))}
    measurables = defaultdict(list)
    for m in session.scalars(select(models.Measurable).order_by(models.Measurable.id)):
        measurables[m.team_id].append(m)
    todos = defaultdict(list)
    for t in session.scalars(select(models.Todo)):
        todos[t.team_id].append(t)
    rocks = defaultdict(list)
    for r in session.scalars(select(models.Rock).order_by(models.Rock.id)):
        rocks[r.team_id].append(r)
    milestones = defaultdict(list)
    for ms in session.scalars(select(models.Milestone)):
        milestones[ms.rock_id].append((ms.due_date, ms.done))
    open_issues = defaultdict(list)
    for i in session.scalars(select(models.Issue).where(models.Issue.solved_at.is_(None))):
        open_issues[i.team_id].append(i)
    meetings: defaultdict[str, dict[str, Any]] = defaultdict(dict)
    for mt in session.scalars(
        select(models.Meeting).where(models.Meeting.status == "ended").order_by(models.Meeting.id)
    ):
        meetings[mt.team_id][mt.id] = mt.summary

    teams: dict[str, Any] = {}
    for team in session.scalars(select(models.Team).order_by(models.Team.id)):
        team_todos = todos[team.id]
        completion: dict[str, Any] = {}
        for week in weeks:
            rate = rules.todo_completion(todo_facts(team_todos), week, tz)
            completion[week.isoformat()] = (
                None
                if rate is None
                else {
                    "due": rate.due,
                    "done": rate.done,
                    "rate_percent": rate.rate_percent,
                    "meets_target": rate.meets_target,
                }
            )
        ordered_issues = sorted(
            open_issues[team.id], key=lambda i: rules.issue_sort_key(i.priority, i.created_at, i.seq, i.id)
        )
        teams[team.id] = {
            "measurable_status": {
                m.id: {
                    week.isoformat(): rules.measurable_status(goal_of(m), scores.get((m.id, week)), week, current).value
                    for week in weeks
                }
                for m in measurables[team.id]
            },
            "todo_completion": completion,
            "overdue_todos": sorted(t.id for t in team_todos if rules.is_overdue(t.due_date, t.done_at, today)),
            "rocks": {
                r.id: {
                    "status": rules.rock_status(r.status, milestones[r.id], today).value,
                    "progress_percent": rules.rock_progress(r.status, milestones[r.id]),
                }
                for r in rocks[team.id]
            },
            "issue_order": [i.id for i in ordered_issues],
            "meetings": dict(meetings[team.id]),
        }
    return {"now": format_instant(now), "teams": teams}
