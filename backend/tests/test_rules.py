"""Unit tests for every business rule in assessment section 2.6 (pure functions, no database)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app import rules
from app.rules import Goal, RockStatus, Status, TodoFacts

TZ = ZoneInfo("America/Chicago")
D = Decimal


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


# ------------------------------------------------------------------ R-TIME


@pytest.mark.parametrize(
    ("instant", "expected_week"),
    [
        (utc(2026, 11, 11, 15), date(2026, 11, 9)),  # default now: Wednesday 9am Chicago
        (utc(2026, 11, 16, 5, 59, 59), date(2026, 11, 9)),  # Sunday 23:59:59 CST is still the old week
        (utc(2026, 11, 16, 6, 0, 0), date(2026, 11, 16)),  # Monday 00:00:00 CST starts the new week
        (utc(2026, 11, 9, 5, 59), date(2026, 11, 2)),  # t28 completion instant
        (utc(2026, 11, 9, 6, 1), date(2026, 11, 9)),  # t29 completion instant
        (utc(2026, 3, 9, 4, 59), date(2026, 3, 2)),  # Sunday 23:59 CDT after DST start (Mar 8 2026)
        (utc(2026, 3, 9, 5, 0), date(2026, 3, 9)),  # Monday 00:00 CDT
        (utc(2026, 11, 2, 5, 59), date(2026, 10, 26)),  # Sunday 23:59 CST... after DST end (Nov 1 2026)
    ],
)
def test_week_start_uses_company_timezone(instant: datetime, expected_week: date) -> None:
    assert rules.current_week_start(instant, TZ) == expected_week


def test_thirteen_weeks_end_with_current_week() -> None:
    weeks = rules.last_n_weeks(utc(2026, 11, 11, 15), TZ)
    assert len(weeks) == 13
    assert weeks[0] == date(2026, 8, 17)
    assert weeks[-1] == date(2026, 11, 9)
    assert all(w.weekday() == 0 for w in weeks)


def test_last_closed_week_is_week_before_current() -> None:
    assert rules.last_closed_week_start(utc(2026, 11, 11, 15), TZ) == date(2026, 11, 2)


def test_week_end_is_dst_aware() -> None:
    # Week of Nov 2 ends Mon Nov 9 00:00 CST (UTC-6) = 06:00Z, while Oct weeks end at 05:00Z (CDT).
    assert rules.week_end_exclusive(date(2026, 11, 2), TZ) == utc(2026, 11, 9, 6)
    assert rules.week_end_exclusive(date(2026, 10, 26), TZ) == utc(2026, 11, 2, 6)  # DST ended Nov 1
    assert rules.week_end_exclusive(date(2026, 10, 19), TZ) == utc(2026, 10, 26, 5)
    assert rules.week_end_exclusive(date(2026, 3, 2), TZ) == utc(2026, 3, 9, 5)  # DST began Mar 8


@pytest.mark.parametrize(
    ("instant", "quarter"),
    [
        (utc(2026, 9, 30, 20), "2026-Q3"),
        (utc(2026, 10, 1, 4, 59), "2026-Q3"),  # 23:59 CDT on Sep 30
        (utc(2026, 10, 1, 5, 0), "2026-Q4"),
        (utc(2027, 1, 1, 5, 59), "2026-Q4"),  # 23:59 CST on Dec 31
        (utc(2027, 1, 1, 6, 0), "2027-Q1"),
    ],
)
def test_quarter_is_calendar_quarter_in_company_time(instant: datetime, quarter: str) -> None:
    assert rules.quarter_of(rules.local_date(instant, TZ)) == quarter


# --------------------------------------------------------- R-MEASURABLE-STATUS

CURRENT = date(2026, 11, 9)
CLOSED = date(2026, 11, 2)


@pytest.mark.parametrize(
    ("goal", "score", "expected"),
    [
        (Goal("at_least", D(10)), D(10), Status.ON_TRACK),  # boundary inclusive
        (Goal("at_least", D(10)), D("9.99"), Status.OFF_TRACK),
        (Goal("at_least", D(10)), D(11), Status.ON_TRACK),
        (Goal("at_most", D("3.0")), D("3.0"), Status.ON_TRACK),  # boundary inclusive
        (Goal("at_most", D("3.0")), D("3.1"), Status.OFF_TRACK),
        (Goal("at_most", D("3.0")), D(0), Status.ON_TRACK),
        (Goal("between", minimum=D(2), maximum=D(4)), D(2), Status.ON_TRACK),  # min inclusive
        (Goal("between", minimum=D(2), maximum=D(4)), D(4), Status.ON_TRACK),  # max inclusive
        (Goal("between", minimum=D(2), maximum=D(4)), D("1.8"), Status.OFF_TRACK),
        (Goal("between", minimum=D(2), maximum=D(4)), D("4.5"), Status.OFF_TRACK),
        (Goal("exactly", D(1)), D(1), Status.ON_TRACK),
        (Goal("exactly", D(1)), D(0), Status.OFF_TRACK),
        (Goal("exactly", D(1)), D(2), Status.OFF_TRACK),
        (Goal("at_least", D(0)), D(0), Status.ON_TRACK),  # zero is a real score, not "missing"
    ],
)
def test_measurable_status_goal_types_and_inclusive_boundaries(goal: Goal, score: Decimal, expected: Status) -> None:
    assert rules.measurable_status(goal, score, CLOSED, CURRENT) is expected


def test_closed_week_without_score_is_off_track() -> None:
    assert rules.measurable_status(Goal("at_least", D(1)), None, CLOSED, CURRENT) is Status.OFF_TRACK


def test_current_week_without_score_is_pending() -> None:
    assert rules.measurable_status(Goal("at_least", D(1)), None, CURRENT, CURRENT) is Status.PENDING


def test_current_week_with_score_is_evaluated_not_pending() -> None:
    assert rules.measurable_status(Goal("at_least", D(500)), D(520), CURRENT, CURRENT) is Status.ON_TRACK


def test_invalid_goal_raises() -> None:
    with pytest.raises(ValueError, match="invalid goal"):
        Goal("sideways", D(1)).met_by(D(1))


# --------------------------------------------------------- R-TODO-COMPLETION

WEEK = date(2026, 11, 2)  # Mon Nov 2 .. Sun Nov 8


def todo(todo_id: str, due: date, done_at: datetime | None) -> TodoFacts:
    return TodoFacts(todo_id, due, done_at)


def test_t28_done_sunday_2359_chicago_counts_in_due_week() -> None:
    # 2026-11-09T05:59Z == Sunday Nov 8, 23:59 CST -> still within the due week.
    result = rules.todo_completion([todo("t28", date(2026, 11, 6), utc(2026, 11, 9, 5, 59))], WEEK, TZ)
    assert result is not None
    assert (result.due, result.done) == (1, 1)


def test_t29_done_monday_0001_chicago_does_not_count() -> None:
    # 2026-11-09T06:01Z == Monday Nov 9, 00:01 CST -> after the due week ended.
    result = rules.todo_completion([todo("t29", date(2026, 11, 8), utc(2026, 11, 9, 6, 1))], WEEK, TZ)
    assert result is not None
    assert (result.due, result.done) == (1, 0)


def test_done_exactly_at_week_end_instant_does_not_count() -> None:
    result = rules.todo_completion([todo("x", date(2026, 11, 8), utc(2026, 11, 9, 6, 0))], WEEK, TZ)
    assert result is not None
    assert result.done == 0


def test_done_after_due_date_but_inside_due_week_counts() -> None:
    result = rules.todo_completion([todo("x", date(2026, 11, 3), utc(2026, 11, 7, 18))], WEEK, TZ)
    assert result is not None
    assert result.done == 1


def test_done_before_due_week_counts() -> None:
    result = rules.todo_completion([todo("x", date(2026, 11, 3), utc(2026, 10, 20))], WEEK, TZ)
    assert result is not None
    assert result.done == 1


def test_dst_end_week_boundary_uses_cst_offset() -> None:
    # Week of Oct 26 ends Mon Nov 2 00:00 CST = 06:00Z (an extra hour because DST ended Nov 1).
    in_week = todo("a", date(2026, 10, 30), utc(2026, 11, 2, 5, 30))  # Sun 23:30 CST
    out_week = todo("b", date(2026, 10, 30), utc(2026, 11, 2, 6, 30))  # Mon 00:30 CST
    result = rules.todo_completion([in_week, out_week], date(2026, 10, 26), TZ)
    assert result is not None
    assert (result.due, result.done) == (2, 1)


def test_zero_due_returns_none() -> None:
    assert rules.todo_completion([todo("x", date(2026, 11, 20), None)], WEEK, TZ) is None
    assert rules.todo_completion([], WEEK, TZ) is None


def test_week_membership_is_by_due_date_inclusive_of_monday_and_sunday() -> None:
    todos = [
        todo("mon", date(2026, 11, 2), None),
        todo("sun", date(2026, 11, 8), None),
        todo("prev-sun", date(2026, 11, 1), None),
        todo("next-mon", date(2026, 11, 9), None),
    ]
    result = rules.todo_completion(todos, WEEK, TZ)
    assert result is not None
    assert result.due == 2


def test_exactly_ninety_percent_meets_target() -> None:
    todos = [todo(f"t{i}", date(2026, 11, 3), utc(2026, 11, 3, 18)) for i in range(9)]
    todos.append(todo("late", date(2026, 11, 3), None))
    result = rules.todo_completion(todos, WEEK, TZ)
    assert result is not None
    assert (result.due, result.done, result.rate_percent, result.meets_target) == (10, 9, 90, True)


def test_target_compares_exact_ratio_not_rounded_percent() -> None:
    # 179/200 = 89.5% rounds half-up to 90 but is below the 90% target.
    todos = [todo(f"d{i}", date(2026, 11, 3), utc(2026, 11, 3, 18)) for i in range(179)]
    todos += [todo(f"n{i}", date(2026, 11, 3), None) for i in range(21)]
    result = rules.todo_completion(todos, WEEK, TZ)
    assert result is not None
    assert result.rate_percent == 90
    assert result.meets_target is False


@pytest.mark.parametrize(
    ("done", "due", "percent"),
    [(1, 8, 13), (3, 4, 75), (1, 3, 33), (2, 3, 67), (0, 5, 0), (5, 5, 100), (1, 16, 6)],
)
def test_rate_percent_rounds_half_up(done: int, due: int, percent: int) -> None:
    # 1/8 = 12.5% -> 13 (half up); 1/16 = 6.25% -> 6
    todos = [todo(f"d{i}", date(2026, 11, 3), utc(2026, 11, 3, 18)) for i in range(done)]
    todos += [todo(f"n{i}", date(2026, 11, 3), None) for i in range(due - done)]
    result = rules.todo_completion(todos, WEEK, TZ)
    assert result is not None
    assert result.rate_percent == percent


# --------------------------------------------------------------- R-OVERDUE


def test_overdue_rules() -> None:
    today = date(2026, 11, 11)
    assert rules.is_overdue(date(2026, 11, 10), None, today) is True
    assert rules.is_overdue(date(2026, 11, 11), None, today) is False  # due today
    assert rules.is_overdue(date(2026, 11, 12), None, today) is False
    assert rules.is_overdue(date(2026, 11, 1), utc(2026, 11, 2), today) is False  # done late is not overdue


def test_today_is_company_local_date() -> None:
    # 2026-11-12T04:00Z is still Nov 11 in Chicago (22:00 CST)
    assert rules.local_date(utc(2026, 11, 12, 4), TZ) == date(2026, 11, 11)
    assert rules.local_date(utc(2026, 11, 12, 6), TZ) == date(2026, 11, 12)


# ------------------------------------------------------------------ R-ROCK

TODAY = date(2026, 11, 11)


@pytest.mark.parametrize(
    ("seeded", "milestones", "expected"),
    [
        ("complete", [(date(2026, 1, 1), False)], RockStatus.COMPLETE),  # complete wins
        ("off_track", [], RockStatus.OFF_TRACK),
        ("on_track", [], RockStatus.ON_TRACK),  # no milestones -> seeded status alone
        ("on_track", [(date(2026, 11, 11), False)], RockStatus.ON_TRACK),  # due today is not past due
        ("on_track", [(date(2026, 11, 10), False)], RockStatus.OFF_TRACK),  # unfinished and past due
        ("on_track", [(date(2026, 11, 10), True)], RockStatus.ON_TRACK),  # past due but done
        ("on_track", [(date(2026, 11, 10), True), (date(2026, 12, 1), False)], RockStatus.ON_TRACK),
        ("off_track", [(date(2026, 12, 1), False)], RockStatus.OFF_TRACK),
    ],
)
def test_rock_status(seeded: str, milestones: list[tuple[date, bool]], expected: RockStatus) -> None:
    assert rules.rock_status(seeded, milestones, TODAY) is expected


@pytest.mark.parametrize(
    ("seeded", "done_flags", "expected"),
    [
        ("complete", [], 100),
        ("on_track", [], 0),
        ("off_track", [], 0),
        ("on_track", [True, False, False], 33),
        ("on_track", [True] + [False] * 7, 13),  # 1/8 = 12.5% -> 13
        ("on_track", [True, True, False], 67),
        ("complete", [True, True], 100),
        ("on_track", [False, False], 0),
    ],
)
def test_rock_progress(seeded: str, done_flags: list[bool], expected: int) -> None:
    assert rules.rock_progress(seeded, [(date(2026, 12, 1), d) for d in done_flags]) == expected


# ------------------------------------------------------------ R-ISSUE-ORDER


def test_issue_order_priority_desc_then_oldest_then_unprioritised_last() -> None:
    rows = [
        ("i4", None, utc(2026, 9, 1), 4),
        ("i3", 3, utc(2026, 10, 5), 3),
        ("i1", 5, utc(2026, 10, 20), 1),
        ("i2", 5, utc(2026, 10, 14), 2),
        ("i5", 4, utc(2026, 11, 9), 5),
        ("i0", None, utc(2026, 8, 1), 6),
    ]
    ordered = sorted(rows, key=lambda r: rules.issue_sort_key(r[1], r[2], r[3], r[0]))
    assert [r[0] for r in ordered] == ["i2", "i1", "i5", "i3", "i0", "i4"]


def test_issue_order_deterministic_tie_breaker() -> None:
    same = utc(2026, 11, 11, 15)
    rows = [("b", 3, same, 2), ("a", 3, same, 1)]
    ordered = sorted(rows, key=lambda r: rules.issue_sort_key(r[1], r[2], r[3], r[0]))
    assert [r[0] for r in ordered] == ["a", "b"]


# --------------------------------------------------------------- R-RATING


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ([8, 9, 7], D("8.0")),
        ([8, 9, 8, 8], D("8.3")),  # 8.25 -> 8.3 half up
        ([], None),
        ([10], D("10.0")),
        ([1, 2], D("1.5")),
        ([7, 8, 8], D("7.7")),  # 7.666... -> 7.7
        ([9, 10, 10, 10, 10, 10, 10, 10], D("9.9")),  # 9.875 -> 9.9
        ([1, 1, 2], D("1.3")),  # 1.333
    ],
)
def test_average_rating(ratings: list[int], expected: Decimal | None) -> None:
    assert rules.average_rating(ratings) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("12.5"), 13), (D("12.49"), 12), (D("0.5"), 1), (D(0), 0), (D("99.5"), 100)]
)
def test_round_half_up_whole(value: Decimal, expected: int) -> None:
    assert rules.round_half_up(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(D("8.25"), D("8.3")), (D("8.24"), D("8.2")), (D("8.35"), D("8.4")), (D("2.05"), D("2.1"))]
)
def test_round_half_up_one_decimal(value: Decimal, expected: Decimal) -> None:
    assert rules.round_half_up_1dp(value) == expected
