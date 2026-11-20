"""Pure business rules (assessment section 2.6).

Nothing here touches the database or reads a clock: every function receives the
instant/date it needs, so behaviour is deterministic and exhaustively unit-testable.
All "calendar" notions (weeks, quarters, due dates, today) are computed in the company
time zone; timestamps stay timezone-aware UTC.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from fractions import Fraction
from zoneinfo import ZoneInfo

WEEKS_SHOWN = 13
TODO_TARGET = Fraction(90, 100)


class Status(StrEnum):
    """Measurable status."""

    ON_TRACK = "on_track"
    OFF_TRACK = "off_track"
    PENDING = "pending"


class RockStatus(StrEnum):
    """Rock status."""

    ON_TRACK = "on_track"
    OFF_TRACK = "off_track"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Goal:
    """A measurable goal. Boundaries are inclusive."""

    type: str
    value: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None

    def met_by(self, score: Decimal) -> bool:
        """Return whether ``score`` satisfies the goal (inclusive boundaries)."""
        if self.type == "at_least" and self.value is not None:
            return score >= self.value
        if self.type == "at_most" and self.value is not None:
            return score <= self.value
        if self.type == "exactly" and self.value is not None:
            return score == self.value
        if self.type == "between" and self.minimum is not None and self.maximum is not None:
            return self.minimum <= score <= self.maximum
        msg = f"invalid goal: {self}"
        raise ValueError(msg)


# --------------------------------------------------------------------------- time


def local_date(instant: datetime, tz: ZoneInfo) -> date:
    """Calendar date of an instant in the company time zone."""
    return instant.astimezone(tz).date()


def week_start_of(day: date) -> date:
    """Monday of the ISO week containing ``day``."""
    return day - timedelta(days=day.weekday())


def current_week_start(now: datetime, tz: ZoneInfo) -> date:
    """Monday (company time) of the week containing ``now``."""
    return week_start_of(local_date(now, tz))


def last_closed_week_start(now: datetime, tz: ZoneInfo) -> date:
    """Monday of the full week before the current one."""
    return current_week_start(now, tz) - timedelta(days=7)


def last_n_weeks(now: datetime, tz: ZoneInfo, count: int = WEEKS_SHOWN) -> list[date]:
    """The ``count`` week starts ending with (and including) the current week, oldest first."""
    current = current_week_start(now, tz)
    return [current - timedelta(days=7 * offset) for offset in range(count - 1, -1, -1)]


def week_end_exclusive(week_start: date, tz: ZoneInfo) -> datetime:
    """UTC instant at which the week ends: next Monday 00:00 company time (DST-safe)."""
    next_monday = week_start + timedelta(days=7)
    return datetime.combine(next_monday, time.min, tzinfo=tz).astimezone(UTC)


def quarter_of(day: date) -> str:
    """Calendar quarter label, e.g. ``2026-Q4``."""
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def is_valid_week_start(day: date) -> bool:
    """Whether ``day`` is a Monday."""
    return day.weekday() == 0


# ------------------------------------------------------------------- rounding


def round_half_up(value: Decimal | Fraction | int) -> int:
    """Round to a whole number, halves up (12.5 -> 13)."""
    return int(_to_decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def round_half_up_1dp(value: Decimal | Fraction | int) -> Decimal:
    """Round to one decimal place, halves up (8.25 -> 8.3)."""
    return _to_decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _to_decimal(value: Decimal | Fraction | int) -> Decimal:
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


# ------------------------------------------------------------- measurable status


def measurable_status(goal: Goal, score: Decimal | None, week_start: date, current_week: date) -> Status:
    """Status of one measurable-week.

    A missing score is ``pending`` for the current week and ``off_track`` for any closed week.
    """
    if score is None:
        return Status.PENDING if week_start >= current_week else Status.OFF_TRACK
    return Status.ON_TRACK if goal.met_by(score) else Status.OFF_TRACK


# --------------------------------------------------------------------- to-dos


@dataclass(frozen=True)
class TodoFacts:
    """The fields of a To-Do that the rules need."""

    id: str
    due_date: date
    done_at: datetime | None


@dataclass(frozen=True)
class CompletionRate:
    """To-Do completion for one due week."""

    due: int
    done: int
    rate_percent: int
    meets_target: bool


def todo_completion(todos: Iterable[TodoFacts], week_start: date, tz: ZoneInfo) -> CompletionRate | None:
    """Completion rate for the To-Dos due in ``week_start``'s week.

    A To-Do counts as done only if it was completed before the due week ended (company time);
    completing it later does not count. No To-Dos due means no rate (``None``).
    """
    week_end = week_end_exclusive(week_start, tz)
    due_end = week_start + timedelta(days=7)
    due = [t for t in todos if week_start <= t.due_date < due_end]
    if not due:
        return None
    done = sum(1 for t in due if t.done_at is not None and t.done_at < week_end)
    ratio = Fraction(done, len(due))
    return CompletionRate(
        due=len(due),
        done=done,
        rate_percent=round_half_up(ratio * 100),
        meets_target=ratio >= TODO_TARGET,
    )


def is_overdue(due_date: date, done_at: datetime | None, today: date) -> bool:
    """Not done and due before today (due today is not overdue)."""
    return done_at is None and due_date < today


# ---------------------------------------------------------------------- rocks


def rock_status(seeded: str, milestones: Sequence[tuple[date, bool]], today: date) -> RockStatus:
    """Computed Rock status from the seeded status and (due_date, done) milestones."""
    if seeded == RockStatus.COMPLETE:
        return RockStatus.COMPLETE
    if seeded == RockStatus.OFF_TRACK:
        return RockStatus.OFF_TRACK
    if any(not done and due < today for due, done in milestones):
        return RockStatus.OFF_TRACK
    return RockStatus.ON_TRACK


def rock_progress(seeded: str, milestones: Sequence[tuple[date, bool]]) -> int:
    """Completed / total milestones as a whole percent; with none, 0 (or 100 when complete)."""
    if not milestones:
        return 100 if seeded == RockStatus.COMPLETE else 0
    completed = sum(1 for _, done in milestones if done)
    return round_half_up(Fraction(completed * 100, len(milestones)))


# --------------------------------------------------------------------- issues


def issue_sort_key(
    priority: int | None, created_at: datetime, seq: int, issue_id: str
) -> tuple[int, int, datetime, int, str]:
    """Sort key: priority 5..1 first, unprioritised last, then oldest first, then stable tie-breakers."""
    return (1 if priority is None else 0, -(priority or 0), created_at, seq, issue_id)


# -------------------------------------------------------------------- ratings


def average_rating(ratings: Iterable[int]) -> Decimal | None:
    """Mean of submitted ratings to one decimal (half up); ``None`` when nobody rated."""
    values = list(ratings)
    if not values:
        return None
    return round_half_up_1dp(Fraction(sum(values), len(values)))
