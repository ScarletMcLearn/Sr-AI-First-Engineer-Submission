"""Seed loading and the rules report (README format), including alternative APP_NOW values."""

import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import rules
from app.config import get_settings
from app.seed import expected_counts, load_seed_file, seed_database
from app.services.report import build_report

TZ = ZoneInfo("America/Chicago")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NOW = datetime(2026, 11, 11, 15, tzinfo=UTC)
EXPECTED_WEEKS = [(date(2026, 8, 17) + timedelta(days=7 * i)).isoformat() for i in range(13)]


def report(session: Session, now: datetime = DEFAULT_NOW) -> dict[str, Any]:
    result = build_report(session, now, TZ)
    parsed: dict[str, Any] = json.loads(json.dumps(result))  # exactly what the CLI would serialise
    return parsed


# -------------------------------------------------------------------- seed


def test_seed_matches_source_counts_and_ids(session: Session) -> None:
    data = load_seed_file()
    for table, expected in expected_counts(data).items():
        assert session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == expected, table
    for table, ids in {
        "users": [u.id for u in data.users],
        "issues": [i.id for i in data.issues],
        "todos": [t.id for t in data.todos],
        "measurables": [m.id for m in data.measurables],
        "rocks": [r.id for r in data.rocks],
        "milestones": [m.id for m in data.milestones],
        "meetings": [m.id for m in data.meetings],
    }.items():
        stored = set(session.execute(text(f"SELECT id FROM {table}")).scalars())
        assert stored == set(ids), table


def test_seed_is_idempotent_and_never_overwrites_user_changes(session: Session) -> None:
    session.execute(text("UPDATE issues SET title = 'Edited by a user' WHERE id = 'i1'"))
    session.execute(text("UPDATE scores SET value = 77 WHERE measurable_id = 'm1' AND week_start = '2026-11-02'"))
    session.commit()
    before = session.execute(text("SELECT count(*) FROM scores")).scalar_one()
    counts = seed_database(session)
    assert set(counts.values()) == {0}  # nothing inserted the second time
    assert session.execute(text("SELECT count(*) FROM scores")).scalar_one() == before
    assert session.execute(text("SELECT title FROM issues WHERE id = 'i1'")).scalar_one() == "Edited by a user"
    assert (
        session.execute(
            text("SELECT value FROM scores WHERE measurable_id='m1' AND week_start='2026-11-02'")
        ).scalar_one()
        == 77
    )


def test_seed_links_issues_and_todos_to_meetings_by_timestamp(session: Session) -> None:
    rows = session.execute(
        text("SELECT id, solved_in_meeting_id FROM issues WHERE solved_in_meeting_id IS NOT NULL")
    ).all()
    assert {(r[0], r[1]) for r in rows} == {("i7", "mt1"), ("i6", "mt2")}
    rows = session.execute(
        text("SELECT id, created_in_meeting_id FROM todos WHERE created_in_meeting_id IS NOT NULL")
    ).all()
    assert {(r[0], r[1]) for r in rows} == {("t20", "mt1"), ("t30", "mt2")}


# ------------------------------------------------------------------ report


def test_report_structure_and_coverage(session: Session) -> None:
    data = report(session)
    assert set(data) == {"now", "teams"}
    assert data["now"] == "2026-11-11T15:00:00Z"
    assert set(data["teams"]) == {"team_lead", "team_sales", "team_ops"}
    seed = load_seed_file()
    for team_id, team in data["teams"].items():
        assert set(team) == {
            "measurable_status",
            "todo_completion",
            "overdue_todos",
            "rocks",
            "issue_order",
            "meetings",
        }
        assert set(team["measurable_status"]) == {m.id for m in seed.measurables if m.team_id == team_id}
        for weeks in team["measurable_status"].values():
            assert list(weeks) == EXPECTED_WEEKS
            assert set(weeks.values()) <= {"on_track", "off_track", "pending"}
        assert list(team["todo_completion"]) == EXPECTED_WEEKS
        assert set(team["rocks"]) == {r.id for r in seed.rocks if r.team_id == team_id}


def test_report_independent_oracle_for_trap_cases(session: Session) -> None:
    lead = report(session)["teams"]["team_lead"]
    status = lead["measurable_status"]
    assert status["m5"]["2026-10-19"] == "off_track"  # missing score, closed week
    assert status["m5"]["2026-11-09"] == "on_track"  # has a current-week score (520 >= 500)
    assert status["m1"]["2026-11-09"] == "pending"  # missing score, current week
    assert status["m1"]["2026-10-12"] == "on_track"
    assert status["m1"]["2026-09-07"] == "on_track"  # 10 >= 10 inclusive boundary
    assert status["m2"]["2026-09-07"] == "on_track"  # 3.0 <= 3.0 inclusive boundary
    assert status["m3"]["2026-08-31"] == "on_track"  # 4 within [2, 4], max inclusive
    assert status["m3"]["2026-08-24"] == "on_track"  # 2 within [2, 4], min inclusive
    assert status["m3"]["2026-09-07"] == "off_track"  # 4.5 above max
    assert status["m4"]["2026-08-17"] == "on_track"  # exactly 1
    assert status["m4"]["2026-09-21"] == "off_track"  # 2 != 1
    assert status["m4"]["2026-08-31"] == "off_track"  # 0 != 1
    completion = lead["todo_completion"]
    # Week of Nov 2: t20-t29 due (10). t28 (done Sun 23:59 CST) counts; t29 (done Mon 00:01 CST) does not.
    assert completion["2026-11-02"] == {"due": 10, "done": 9, "rate_percent": 90, "meets_target": True}
    # Week of Oct 26: t10, t11 (done 23:30 CST Sunday, DST just ended), t12 (never done) -> 2/3
    assert completion["2026-10-26"] == {"due": 3, "done": 2, "rate_percent": 67, "meets_target": False}
    assert completion["2026-09-14"] == {"due": 2, "done": 2, "rate_percent": 100, "meets_target": True}
    assert completion["2026-11-09"] == {"due": 3, "done": 0, "rate_percent": 0, "meets_target": False}
    assert completion["2026-08-17"] is None
    assert lead["overdue_todos"] == ["t12", "t31"]  # t30 is due today -> not overdue
    assert lead["rocks"]["r1"] == {"status": "on_track", "progress_percent": 33}  # ms2 due today: not past due
    assert lead["rocks"]["r2"] == {"status": "off_track", "progress_percent": 13}  # ms5 past due; 1/8 = 12.5 -> 13
    assert lead["rocks"]["r3"] == {"status": "complete", "progress_percent": 100}  # complete, no milestones
    assert lead["rocks"]["r4"] == {"status": "off_track", "progress_percent": 0}
    assert lead["rocks"]["r5"] == {"status": "on_track", "progress_percent": 0}
    assert lead["issue_order"] == ["i2", "i1", "i5", "i3", "i4"]
    other = report(session)["teams"]
    assert other["team_sales"]["issue_order"] == ["i8"]
    assert other["team_ops"]["overdue_todos"] == []
    assert other["team_sales"]["overdue_todos"] == []  # t40 due Nov 12


def test_report_historical_meetings(session: Session) -> None:
    meetings = report(session)["teams"]["team_lead"]["meetings"]
    assert set(meetings) == {"mt1", "mt2"}
    assert meetings["mt1"] == {
        "scorecard_week": "2026-10-19",
        "measurable_status": {
            "m1": "on_track",
            "m2": "on_track",
            "m3": "on_track",
            "m4": "on_track",
            "m5": "off_track",
        },
        "issues_solved": ["i7"],
        "todos_created": ["t20"],
        "attendee_ids": ["u1", "u2", "u3", "u4", "u5"],
        "rating": 8.0,
    }
    assert meetings["mt2"]["scorecard_week"] == "2026-10-26"
    assert meetings["mt2"]["issues_solved"] == ["i6"]
    assert meetings["mt2"]["todos_created"] == ["t30"]
    assert meetings["mt2"]["rating"] == 8.3
    assert report(session)["teams"]["team_sales"]["meetings"] == {}


def test_report_ids_are_plain_string_sorted(session: Session) -> None:
    data = report(session)["teams"]["team_lead"]
    assert data["overdue_todos"] == sorted(data["overdue_todos"])
    for meeting in data["meetings"].values():
        for key in ("issues_solved", "todos_created", "attendee_ids"):
            assert meeting[key] == sorted(meeting[key])


def test_report_is_derived_from_data_not_constants(session: Session) -> None:
    session.execute(text("UPDATE todos SET done_at = '2026-11-11T14:00:00Z' WHERE id = 't12'"))
    session.execute(text("DELETE FROM scores WHERE measurable_id = 'm2' AND week_start = '2026-10-26'"))
    session.commit()
    lead = report(session)["teams"]["team_lead"]
    assert lead["overdue_todos"] == ["t31"]
    assert lead["measurable_status"]["m2"]["2026-10-26"] == "off_track"
    # t12 was completed after its due week, so the 2026-10-26 rate is unchanged.
    assert lead["todo_completion"]["2026-10-26"]["done"] == 2


@pytest.mark.parametrize(
    ("now", "first_week", "last_week"),
    [
        (datetime(2026, 11, 18, 15, tzinfo=UTC), "2026-08-24", "2026-11-16"),
        (datetime(2026, 11, 16, 5, 59, 59, tzinfo=UTC), "2026-08-17", "2026-11-09"),  # Sunday 23:59:59 Chicago
        (datetime(2026, 11, 16, 6, 0, 0, tzinfo=UTC), "2026-08-24", "2026-11-16"),  # Monday 00:00:00 Chicago
        (datetime(2027, 1, 5, 12, tzinfo=UTC), "2026-10-12", "2027-01-04"),  # next quarter/year
    ],
)
def test_report_adapts_to_other_app_now_values(
    session: Session, now: datetime, first_week: str, last_week: str
) -> None:
    data = report(session, now)
    weeks = list(data["teams"]["team_lead"]["measurable_status"]["m1"])
    assert (weeks[0], weeks[-1], len(weeks)) == (first_week, last_week, 13)
    assert data["now"] == now.isoformat().replace("+00:00", "Z")
    assert list(data["teams"]["team_lead"]["todo_completion"]) == weeks


def test_report_alternative_now_changes_computed_values(session: Session) -> None:
    later = report(session, datetime(2026, 11, 20, 15, tzinfo=UTC))["teams"]["team_lead"]
    assert later["overdue_todos"] == ["t12", "t30", "t31", "t32"]  # everything due before Nov 20 and open
    assert later["rocks"]["r1"]["status"] == "off_track"  # ms2 (Nov 11) now unfinished and past due
    assert later["measurable_status"]["m1"]["2026-11-09"] == "off_track"  # week closed with no score
    assert later["measurable_status"]["m1"]["2026-11-16"] == "pending"
    # Historical meeting summaries are snapshots and do not move.
    assert later["meetings"]["mt1"]["scorecard_week"] == "2026-10-19"


def test_report_q1_rocks_status_independent_of_quarter(session: Session) -> None:
    data = report(session, datetime(2027, 1, 5, 12, tzinfo=UTC))["teams"]["team_lead"]
    assert data["rocks"]["r3"] == {"status": "complete", "progress_percent": 100}
    assert data["rocks"]["r5"]["status"] == "on_track"


def test_report_cli_prints_only_json_to_stdout() -> None:
    env = {**os.environ, "DATABASE_URL": get_settings().database_url, "APP_NOW": "2026-11-11T15:00:00Z"}
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "rules-report"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    parsed = json.loads(result.stdout)  # would raise if anything but JSON were printed
    assert parsed["now"] == "2026-11-11T15:00:00Z"
    assert result.stdout.endswith("}\n")
    again = subprocess.run(
        [sys.executable, "-m", "app.cli", "rules-report"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert again.stdout == result.stdout  # deterministic


def test_report_cli_honours_app_now_env() -> None:
    env = {**os.environ, "DATABASE_URL": get_settings().database_url, "APP_NOW": "2026-11-18T15:00:00Z"}
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "rules-report"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    parsed = json.loads(result.stdout)
    assert parsed["now"] == "2026-11-18T15:00:00Z"
    assert list(parsed["teams"]["team_ops"]["measurable_status"]["m7"])[-1] == "2026-11-16"


def test_rules_module_week_helpers_agree_with_report() -> None:
    weeks = rules.last_n_weeks(DEFAULT_NOW, TZ)
    assert [w.isoformat() for w in weeks] == EXPECTED_WEEKS
