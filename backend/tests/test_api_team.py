"""Team page API behaviour: scorecard, scores, Issues, To-Dos, Rocks."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

Login = Callable[[str], TestClient]
LEAD = "/api/teams/team_lead"


def test_scorecard_shape_and_statuses(login: Login) -> None:
    body = login("u3").get(f"{LEAD}/scorecard").json()
    assert body["weeks"][0] == "2026-08-17"
    assert body["weeks"][-1] == "2026-11-09"
    assert len(body["weeks"]) == 13
    assert body["current_week"] == "2026-11-09"
    assert body["last_closed_week"] == "2026-11-02"
    rows = {m["id"]: m for m in body["measurables"]}
    assert set(rows) == {"m1", "m2", "m3", "m4", "m5"}
    m5 = {c["week_start"]: c for c in rows["m5"]["cells"]}
    assert m5["2026-10-19"]["value"] is None
    assert m5["2026-10-19"]["status"] == "off_track"  # missing score in a closed week
    assert m5["2026-11-02"]["status"] == "off_track"
    m1 = {c["week_start"]: c for c in rows["m1"]["cells"]}
    assert m1["2026-11-09"] == {
        "week_start": "2026-11-09",
        "value": None,
        "status": "pending",
        "version": None,
        "issue_id": None,
    }
    assert m1["2026-11-02"]["issue_id"] == "i5"  # existing unsolved linked Issue is surfaced
    assert rows["m3"]["goal"] == {"type": "between", "value": None, "min": 2.0, "max": 4.0}
    assert rows["m1"]["owner"] == {"id": "u2", "name": "Blake Brooks"}


def test_set_score_updates_status_and_last_save_wins(login: Login) -> None:
    client = login("u3")
    url = f"{LEAD}/measurables/m1/scores/2026-11-09"
    first = client.put(url, json={"value": 12}).json()
    cell = next(c for c in first["measurables"][0]["cells"] if c["week_start"] == "2026-11-09")
    assert (cell["value"], cell["status"], cell["version"]) == (12.0, "on_track", 1)
    second = login("u2").put(url, json={"value": 4}).json()
    cell = next(c for c in second["measurables"][0]["cells"] if c["week_start"] == "2026-11-09")
    assert (cell["value"], cell["status"], cell["version"]) == (4.0, "off_track", 2)


def test_set_score_boundary_is_on_track(login: Login) -> None:
    cell = next(
        c
        for c in login("u3")
        .put(f"{LEAD}/measurables/m1/scores/2026-11-09", json={"value": 10})
        .json()["measurables"][0]["cells"]
        if c["week_start"] == "2026-11-09"
    )
    assert cell["status"] == "on_track"


def test_set_score_lost_update_protection(login: Login) -> None:
    client = login("u3")
    url = f"{LEAD}/measurables/m1/scores/2026-11-02"  # seeded, version 1
    assert client.put(url, json={"value": 9, "expected_version": 1}).status_code == 200
    stale = client.put(url, json={"value": 5, "expected_version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_version"


def test_set_score_validation(login: Login) -> None:
    client = login("u3")
    assert client.put(f"{LEAD}/measurables/m1/scores/2026-11-10", json={"value": 1}).status_code == 422  # not a Monday
    assert (
        client.put(f"{LEAD}/measurables/m1/scores/2026-08-10", json={"value": 1}).status_code == 422
    )  # outside window
    assert client.put(f"{LEAD}/measurables/m1/scores/2026-11-16", json={"value": 1}).status_code == 422  # future
    assert client.put(f"{LEAD}/measurables/m1/scores/2026-11-09", json={"value": "abc"}).status_code == 422
    assert client.put(f"{LEAD}/measurables/m1/scores/2026-11-09", json={}).status_code == 422
    assert client.put(f"{LEAD}/measurables/m_nope/scores/2026-11-09", json={"value": 1}).status_code == 404


def test_make_issue_creates_then_returns_existing(login: Login) -> None:
    client = login("u3")
    url = f"{LEAD}/measurables/m5/weeks/2026-10-19/issue"  # m5 has no score that week -> off track
    first = client.post(url)
    assert first.status_code == 201
    issue = first.json()["issue"]
    assert first.json()["created"] is True
    assert issue["title"] == "Cash on hand, week of Oct 19"
    assert issue["owner"]["id"] == "u3"  # the user who clicked
    assert issue["source"] == {"measurable_id": "m5", "measurable_name": "Cash on hand", "week_start": "2026-10-19"}
    again = login("u2").post(url)
    assert again.status_code == 200
    assert again.json()["created"] is False
    assert again.json()["issue"]["id"] == issue["id"]


def test_make_issue_returns_seeded_unsolved_issue(login: Login) -> None:
    result = login("u3").post(f"{LEAD}/measurables/m1/weeks/2026-11-02/issue").json()
    assert result["issue"]["id"] == "i5"
    assert result["created"] is False


def test_make_issue_after_solving_creates_a_new_issue(login: Login) -> None:
    client = login("u3")
    url = f"{LEAD}/measurables/m1/weeks/2026-11-02/issue"
    assert client.post(f"{LEAD}/issues/i5/solve", json={"note": "handled"}).status_code == 200
    fresh = client.post(url)
    assert fresh.status_code == 201
    assert fresh.json()["issue"]["id"] != "i5"


def test_make_issue_only_for_off_track_cells(login: Login) -> None:
    client = login("u3")
    assert client.post(f"{LEAD}/measurables/m1/weeks/2026-11-09/issue").status_code == 422  # pending
    assert client.post(f"{LEAD}/measurables/m1/weeks/2026-10-19/issue").status_code == 422  # on track (12)
    assert client.post(f"{LEAD}/measurables/m1/weeks/2026-11-03/issue").status_code == 422  # not a Monday


def test_issue_order_matches_rule(login: Login) -> None:
    ids = [i["id"] for i in login("u3").get(f"{LEAD}/issues").json()]
    assert ids == ["i2", "i1", "i5", "i3", "i4"]  # p5 oldest first, p4, p3, unprioritised last


def test_solved_issues_listed_separately(login: Login) -> None:
    solved = login("u3").get(f"{LEAD}/issues?status=solved").json()
    assert [i["id"] for i in solved] == ["i6", "i7"]  # newest solved first
    assert solved[0]["resolution_note"] == "Bank holiday moved the run; added a reminder."
    assert solved[0]["solved_at"] == "2026-11-04T15:40:00Z"


def test_create_issue_owner_is_creator_and_priority_optional(login: Login) -> None:
    client = login("u4")
    created = client.post(f"{LEAD}/issues", json={"title": "  Trim whitespace  "})
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Trim whitespace"
    assert body["priority"] is None
    assert body["owner"]["id"] == "u4"
    with_priority = client.post(f"{LEAD}/issues", json={"title": "Urgent", "priority": 5}).json()
    assert with_priority["priority"] == 5


def test_create_issue_validation(login: Login) -> None:
    client = login("u4")
    assert client.post(f"{LEAD}/issues", json={}).status_code == 422
    assert client.post(f"{LEAD}/issues", json={"title": "   "}).status_code == 422
    assert client.post(f"{LEAD}/issues", json={"title": "x", "priority": 0}).status_code == 422
    assert client.post(f"{LEAD}/issues", json={"title": "x", "priority": 6}).status_code == 422
    assert client.post(f"{LEAD}/issues", json={"title": "x", "priority": "high"}).status_code == 422
    assert client.post(f"{LEAD}/issues", json={"title": "x", "priority": True}).status_code == 422
    assert (
        client.post(f"{LEAD}/issues", json={"title": "x", "owner_id": "u2"}).status_code == 422
    )  # owner is not client-settable


def test_new_issue_slots_into_order(login: Login) -> None:
    client = login("u4")
    new_id = client.post(f"{LEAD}/issues", json={"title": "Five", "priority": 5}).json()["id"]
    ids = [i["id"] for i in client.get(f"{LEAD}/issues").json()]
    assert ids == ["i2", "i1", new_id, "i5", "i3", "i4"]  # newest p5 sorts after older p5s


def test_set_and_clear_priority(login: Login) -> None:
    client = login("u4")
    assert client.patch(f"{LEAD}/issues/i4", json={"priority": 5}).json()["priority"] == 5
    assert client.patch(f"{LEAD}/issues/i4", json={"priority": None}).json()["priority"] is None
    assert client.patch(f"{LEAD}/issues/i4", json={"priority": 9}).status_code == 422
    assert client.patch(f"{LEAD}/issues/i4", json={}).status_code == 422


def test_priority_lost_update_protection(login: Login) -> None:
    client = login("u4")
    assert client.patch(f"{LEAD}/issues/i4", json={"priority": 2, "expected_version": 1}).status_code == 200
    assert client.patch(f"{LEAD}/issues/i4", json={"priority": 3, "expected_version": 1}).status_code == 409


def test_solve_requires_note_and_sets_solved_time(login: Login) -> None:
    client = login("u4")
    assert client.post(f"{LEAD}/issues/i3/solve", json={}).status_code == 422
    assert client.post(f"{LEAD}/issues/i3/solve", json={"note": "   "}).status_code == 422
    solved = client.post(f"{LEAD}/issues/i3/solve", json={"note": "Rota agreed"})
    assert solved.status_code == 200
    assert solved.json()["resolution_note"] == "Rota agreed"
    assert solved.json()["solved_at"] == "2026-11-11T15:00:00Z"
    assert client.post(f"{LEAD}/issues/i3/solve", json={"note": "again"}).status_code == 409
    assert "i3" not in [i["id"] for i in client.get(f"{LEAD}/issues").json()]


def test_todo_from_issue_due_in_seven_days_and_linked(login: Login) -> None:
    client = login("u3")
    created = client.post(f"{LEAD}/issues/i1/todos", json={"title": "Interview 3 candidates", "owner_id": "u4"})
    assert created.status_code == 201
    todo = created.json()
    assert todo["due_date"] == "2026-11-18"  # 7 calendar days after Nov 11 (company local date)
    assert todo["source_issue_id"] == "i1"
    assert todo["source_issue_title"] == "Hiring pipeline is slow"
    assert todo["owner"]["id"] == "u4"
    assert todo["done_at"] is None
    assert todo["overdue"] is False


def test_todo_from_issue_validation(login: Login) -> None:
    client = login("u3")
    url = f"{LEAD}/issues/i1/todos"
    assert client.post(url, json={"owner_id": "u2"}).status_code == 422
    assert client.post(url, json={"title": " ", "owner_id": "u2"}).status_code == 422
    assert client.post(url, json={"title": "t"}).status_code == 422
    assert client.post(url, json={"title": "t", "owner_id": "u5"}).status_code == 422  # observer
    assert client.post(url, json={"title": "t", "owner_id": "nobody"}).status_code == 422
    assert client.post(f"{LEAD}/issues/i_nope/todos", json={"title": "t", "owner_id": "u2"}).status_code == 404
    assert (
        client.post(f"{LEAD}/issues/i8/todos", json={"title": "t", "owner_id": "u2"}).status_code == 404
    )  # other team's issue


def test_todo_due_date_uses_company_local_date(login: Login, clocks) -> None:
    from datetime import UTC, datetime

    clocks.business._instant = datetime(2026, 11, 12, 4, 0, tzinfo=UTC)  # still Nov 11 in Chicago (22:00)
    todo = login("u3").post(f"{LEAD}/issues/i1/todos", json={"title": "t", "owner_id": "u3"}).json()
    assert todo["due_date"] == "2026-11-18"


def test_todos_overdue_flags_and_completion_rate(login: Login) -> None:
    body = login("u3").get(f"{LEAD}/todos").json()
    by_id = {t["id"]: t for t in body["todos"]}
    assert by_id["t12"]["overdue"] is True
    assert by_id["t31"]["overdue"] is True  # due Nov 10
    assert by_id["t30"]["overdue"] is False  # due today
    assert by_id["t32"]["overdue"] is False
    assert by_id["t1"]["overdue"] is False  # done
    assert by_id["t30"]["source_issue_title"] == "Payroll runs, week of Oct 26"
    assert body["last_closed_week"] == "2026-11-02"
    assert body["completion"] == {
        "week_start": "2026-11-02",
        "due": 10,
        "done": 9,
        "rate_percent": 90,
        "meets_target": True,
    }
    assert body["target_percent"] == 90


def test_complete_and_undo_todo(login: Login) -> None:
    client = login("u3")
    done = client.post(f"{LEAD}/todos/t12/complete").json()
    assert done["done_at"] == "2026-11-11T15:00:00Z"
    assert done["overdue"] is False
    assert client.post(f"{LEAD}/todos/t12/complete").json()["done_at"] == "2026-11-11T15:00:00Z"  # idempotent
    undone = client.post(f"{LEAD}/todos/t12/undo").json()
    assert undone["done_at"] is None
    assert undone["overdue"] is True
    assert client.post(f"{LEAD}/todos/t_nope/complete").status_code == 404


def test_completion_rate_is_computed_not_stored(login: Login) -> None:
    client = login("u3")
    client.post(f"{LEAD}/todos/t29/undo")  # was done late (does not count either way)
    assert client.get(f"{LEAD}/todos").json()["completion"]["done"] == 9
    # t12 is due Nov 1 (week of Oct 26): completing it now is after its due week -> still not counted.
    client.post(f"{LEAD}/todos/t12/complete")
    assert client.get(f"{LEAD}/todos").json()["completion"]["done"] == 9


def test_rocks_current_quarter(login: Login) -> None:
    body = login("u3").get(f"{LEAD}/rocks").json()
    assert body["quarter"] == "2026-Q4"
    rocks = {r["id"]: r for r in body["rocks"]}
    assert set(rocks) == {"r1", "r2", "r3", "r4", "r5"}
    assert rocks["r1"]["status"] == "on_track"  # ms2 due today is not past due
    assert rocks["r1"]["progress_percent"] == 33
    assert rocks["r2"]["status"] == "off_track"  # ms5 due Nov 10 unfinished
    assert rocks["r2"]["progress_percent"] == 13  # 1/8 = 12.5 -> 13
    assert rocks["r3"] == {**rocks["r3"], "status": "complete", "progress_percent": 100, "milestones": []}
    assert rocks["r4"]["status"] == "off_track"
    assert rocks["r5"]["status"] == "on_track"
    ms = {m["id"]: m for m in rocks["r2"]["milestones"]}
    assert ms["ms5"]["past_due"] is True
    assert ms["ms4"]["done"] is True
    r1_ms = {m["id"]: m for m in rocks["r1"]["milestones"]}
    assert r1_ms["ms2"]["past_due"] is False


def test_rocks_are_read_only(login: Login) -> None:
    client = login("u3")
    assert client.post(f"{LEAD}/rocks", json={"title": "x"}).status_code in {404, 405}
    assert client.delete(f"{LEAD}/rocks/r1").status_code in {404, 405}


def test_team_detail_lists_eligible_owners(login: Login) -> None:
    body = login("u3").get(f"{LEAD}").json()
    owners = {o["id"] for o in body["eligible_owners"]}
    assert owners == {"u1", "u2", "u3", "u4"}  # no observer (u5)
    assert {m["id"] for m in body["members"]} == {"u1", "u2", "u3", "u4", "u5"}


def test_db_rejects_invalid_data_even_if_app_would_not(session: Session) -> None:
    import pytest
    from sqlalchemy.exc import IntegrityError

    bad_statements = [
        "INSERT INTO issues (id, team_id, title, owner_id, created_at) VALUES ('x1','team_lead','t','u5',now())",  # observer owner
        "INSERT INTO issues (id, team_id, title, owner_id, created_at) VALUES ('x2','team_sales','t','u3',now())",  # not a member
        "INSERT INTO issues (id, team_id, title, owner_id, priority, created_at) VALUES ('x3','team_lead','t','u2',9,now())",
        "INSERT INTO issues (id, team_id, title, owner_id, created_at, solved_at) VALUES ('x4','team_lead','t','u2',now(),now())",
        "INSERT INTO scores VALUES ('m1','2026-11-10',1,1,NULL,NULL)",  # not a Monday
        (
            "INSERT INTO issues (id, team_id, title, owner_id, created_at, source_measurable_id, source_week_start) "
            "VALUES ('x5','team_lead','t','u2',now(),'m6','2026-11-02')"  # measurable of another team
        ),
        (
            "INSERT INTO issues (id, team_id, title, owner_id, created_at, source_measurable_id, source_week_start) "
            "VALUES ('x6','team_lead','t','u2',now(),'m1','2026-11-02')"  # duplicate unsolved source (i5)
        ),
    ]
    for statement in bad_statements:
        with pytest.raises(IntegrityError):
            session.execute(text(statement))
        session.rollback()
