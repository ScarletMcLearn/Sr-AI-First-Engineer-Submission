"""Server-side authorization: roles and team boundaries (assessment 2.4 / 2.7)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

Login = Callable[[str], TestClient]

ADMIN, MEMBER_LEAD_SALES, MEMBER_LEAD, OBSERVER_LEAD, OBSERVER_SALES, MEMBER_OPS = "u1", "u2", "u3", "u5", "u7", "u8"
WEEK = "2026-11-02"


def test_unauthenticated_requests_are_401(login: Login, app_factory: Callable[[], TestClient]) -> None:
    anon = app_factory()
    for path in ("/api/me", "/api/teams", "/api/teams/team_lead/scorecard", "/api/meetings/mt1"):
        response = anon.get(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "unauthorized"


def test_forged_cookie_is_rejected(app_factory: Callable[[], TestClient]) -> None:
    client = app_factory()
    client.cookies.set("l10_session", "dTE=.deadbeef")
    assert client.get("/api/me").status_code == 401


def test_login_unknown_user_is_404(app_factory: Callable[[], TestClient]) -> None:
    assert app_factory().post("/api/auth/login", json={"user_id": "nope"}).status_code == 404


def test_login_rejects_role_in_body(app_factory: Callable[[], TestClient]) -> None:
    response = app_factory().post("/api/auth/login", json={"user_id": "u5", "role": "admin"})
    assert response.status_code == 422


def test_admin_sees_every_team(login: Login) -> None:
    teams = login(ADMIN).get("/api/teams").json()
    assert {t["id"] for t in teams} == {"team_lead", "team_sales", "team_ops"}
    for team_id in ("team_lead", "team_sales", "team_ops"):
        assert login(ADMIN).get(f"/api/teams/{team_id}/scorecard").status_code == 200


def test_member_sees_only_own_teams(login: Login) -> None:
    teams = login(MEMBER_LEAD_SALES).get("/api/teams").json()
    assert {t["id"] for t in teams} == {"team_lead", "team_sales"}
    assert {t["id"] for t in login("u9").get("/api/teams").json()} == {"team_ops"}


def test_member_reads_own_team(login: Login) -> None:
    assert login(MEMBER_LEAD).get("/api/teams/team_lead/scorecard").status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/teams/team_sales",
        "/api/teams/team_sales/scorecard",
        "/api/teams/team_sales/issues",
        "/api/teams/team_sales/todos",
        "/api/teams/team_sales/rocks",
        "/api/teams/team_sales/meetings",
        "/api/teams/team_sales/meetings/active",
    ],
)
def test_member_denied_other_team_reads(login: Login, path: str) -> None:
    response = login(MEMBER_LEAD).get(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_guessed_unknown_team_id_is_refused_for_non_admin(login: Login) -> None:
    assert login(MEMBER_LEAD).get("/api/teams/team_nope/scorecard").status_code == 403
    assert login(ADMIN).get("/api/teams/team_nope/scorecard").status_code == 404


def test_member_denied_cross_team_writes(login: Login) -> None:
    client = login(MEMBER_LEAD)  # u3 is in team_lead only
    assert client.post("/api/teams/team_sales/issues", json={"title": "x"}).status_code == 403
    assert client.put(f"/api/teams/team_sales/measurables/m6/scores/{WEEK}", json={"value": 60}).status_code == 403
    assert client.post("/api/teams/team_sales/issues/i8/solve", json={"note": "n"}).status_code == 403
    assert client.post("/api/teams/team_sales/todos/t40/complete").status_code == 403
    assert client.post("/api/teams/team_sales/meetings").status_code == 403
    assert client.post(f"/api/teams/team_sales/measurables/m6/weeks/{WEEK}/issue").status_code == 403


def test_entity_from_another_team_cannot_be_modified_via_own_team_path(login: Login) -> None:
    client = login(MEMBER_LEAD_SALES)  # member of both teams: path team must match entity team
    assert client.post("/api/teams/team_lead/issues/i8/solve", json={"note": "n"}).status_code == 404
    assert client.post("/api/teams/team_lead/todos/t40/complete").status_code == 404
    assert client.put(f"/api/teams/team_lead/measurables/m6/scores/{WEEK}", json={"value": 1}).status_code == 404
    assert client.patch("/api/teams/team_lead/issues/i8", json={"priority": 1}).status_code == 404


def test_observer_can_read_own_team(login: Login) -> None:
    client = login(OBSERVER_LEAD)
    for path in ("scorecard", "issues", "todos", "rocks", "meetings"):
        assert client.get(f"/api/teams/team_lead/{path}").status_code == 200, path


def test_observer_denied_other_team_reads(login: Login) -> None:
    assert login(OBSERVER_LEAD).get("/api/teams/team_ops/scorecard").status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PUT", f"/api/teams/team_lead/measurables/m1/scores/{WEEK}", {"value": 11}),
        ("POST", f"/api/teams/team_lead/measurables/m1/weeks/{WEEK}/issue", None),
        ("POST", "/api/teams/team_lead/issues", {"title": "x"}),
        ("PATCH", "/api/teams/team_lead/issues/i1", {"priority": 2}),
        ("POST", "/api/teams/team_lead/issues/i1/solve", {"note": "done"}),
        ("POST", "/api/teams/team_lead/issues/i1/todos", {"title": "t", "owner_id": "u2"}),
        ("POST", "/api/teams/team_lead/todos/t12/complete", None),
        ("POST", "/api/teams/team_lead/todos/t12/undo", None),
        ("POST", "/api/teams/team_lead/meetings", None),
    ],
)
def test_observer_write_is_refused(login: Login, method: str, path: str, body: dict[str, object] | None) -> None:
    response = login(OBSERVER_LEAD).request(method, path, json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_observer_cannot_own_via_todo_owner_assignment(login: Login) -> None:
    response = login(MEMBER_LEAD).post("/api/teams/team_lead/issues/i1/todos", json={"title": "t", "owner_id": "u5"})
    assert response.status_code == 422


def test_todo_owner_must_belong_to_team(login: Login) -> None:
    response = login(MEMBER_LEAD).post(
        "/api/teams/team_lead/issues/i1/todos",
        json={"title": "t", "owner_id": "u8"},  # u8 is Operations only
    )
    assert response.status_code == 422


def test_admin_can_write_in_any_team(login: Login) -> None:
    client = login(ADMIN)
    assert client.post("/api/teams/team_ops/issues", json={"title": "Admin raised"}).status_code == 201
    assert client.post("/api/teams/team_sales/meetings").status_code == 201


def test_meeting_actions_denied_across_teams(login: Login) -> None:
    started = login(MEMBER_LEAD).post("/api/teams/team_lead/meetings")
    meeting_id = started.json()["id"]
    outsider = login(MEMBER_OPS)
    assert outsider.get(f"/api/meetings/{meeting_id}").status_code == 403
    assert outsider.post(f"/api/meetings/{meeting_id}/join").status_code == 403
    assert outsider.put(f"/api/meetings/{meeting_id}/rating", json={"rating": 5}).status_code == 403
    assert outsider.post(f"/api/meetings/{meeting_id}/advance", json={}).status_code == 403
    assert outsider.get(f"/api/meetings/{meeting_id}/summary").status_code in {403, 409}
    assert outsider.get("/api/meetings/mt1/summary").status_code == 403


def test_unknown_meeting_is_404_for_authenticated_users(login: Login) -> None:
    assert login(MEMBER_LEAD).get("/api/meetings/mt_nope").status_code == 404


def test_error_responses_hide_internals(login: Login) -> None:
    response = login(MEMBER_LEAD).get("/api/teams/team_sales/scorecard")
    assert set(response.json()["error"]) == {"code", "message", "details"}
    assert "Traceback" not in response.text
