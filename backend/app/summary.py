"""Meeting summary snapshot construction (pure).

A summary is computed once - when the meeting ends (or when historical meetings are seeded) -
and then persisted as JSON on the meeting row. Later edits to scores, Issues or To-Dos never
change it: that is the "snapshot" strategy for keeping history stable.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app import rules


@dataclass(frozen=True)
class MeasurableFacts:
    """Measurable fields needed to compute a status."""

    id: str
    goal: rules.Goal


def build_summary(
    *,
    scorecard_week: date,
    as_of: datetime,
    tz: ZoneInfo,
    measurables: Iterable[MeasurableFacts],
    scores: Mapping[tuple[str, date], Decimal],
    issues_solved: Iterable[str],
    todos_created: Iterable[str],
    attendee_ids: Iterable[str],
    ratings: Iterable[int],
) -> dict[str, Any]:
    """Assemble the persisted summary. ``as_of`` is the meeting's start (decides closed vs. current weeks)."""
    current = rules.current_week_start(as_of, tz)
    statuses = {
        m.id: rules.measurable_status(m.goal, scores.get((m.id, scorecard_week)), scorecard_week, current).value
        for m in sorted(measurables, key=lambda m: m.id)
    }
    average = rules.average_rating(ratings)
    return {
        "scorecard_week": scorecard_week.isoformat(),
        "measurable_status": statuses,
        "issues_solved": sorted(issues_solved),
        "todos_created": sorted(todos_created),
        "attendee_ids": sorted(attendee_ids),
        "rating": None if average is None else float(average),
    }
