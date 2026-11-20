"""Meeting lifecycle, permissions, ratings, timer and summaries."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.clock import Clocks, FrozenClock

Login = Callable[[str], TestClient]
LEAD = "/api/teams/team_lead"


def start(client: TestClient) -> dict[str, Any]:
    response = client.post(f"{LEAD}/meetings")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def to_conclude(facilitator: TestClient, meeting_id: str) -> None:
    for _ in range(2):
        assert facilitator.post(f"/api/meetings/{meeting_id}/advance", json={}).status_code == 200


def test_start_makes_starter_facilitator_and_attendee(login: Login) -> None:
    meeting = start(login("u3"))
    assert meeting["status"] == "active"
    assert meeting["facilitator"] == {"id": "u3", "name": "Casey Cho"}
    assert meeting["section_key"] == "scorecard"
    assert meeting["scorecard_week"] == "2026-11-02"  # last closed week at the default clock
    assert [a["user"]["id"] for a in meeting["attendees"]] == ["u3"]
    assert [(s["key"], s["planned_seconds"]) for s in meeting["sections"]] == [
        ("scorecard", 300),
        ("ids", 3600),
        ("conclude", 600),
    ]
    assert meeting["version"] == 2  # started + attendee recorded


def test_only_one_active_meeting_per_team(login: Login) -> None:
    start(login("u3"))
    second = login("u2").post(f"{LEAD}/meetings")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "meeting_already_active"
    assert login("u1").post("/api/teams/team_sales/meetings").status_code == 201  # other teams unaffected


def test_new_meeting_allowed_after_previous_ended(login: Login) -> None:
    client = login("u3")
    meeting = start(client)
    assert client.post(f"/api/meetings/{meeting['id']}/end", json={}).status_code == 200
    assert client.post(f"{LEAD}/meetings").status_code == 201


def test_active_meeting_endpoint(login: Login) -> None:
    client = login("u2")
    assert client.get(f"{LEAD}/meetings/active").json() == {"meeting": None}
    meeting = start(login("u3"))
    assert client.get(f"{LEAD}/meetings/active").json()["meeting"]["id"] == meeting["id"]


def test_observer_can_join_but_not_start_or_facilitate(login: Login) -> None:
    meeting = start(login("u3"))
    observer = login("u5")
    joined = observer.post(f"/api/meetings/{meeting['id']}/join")
    assert joined.status_code == 200
    assert {a["user"]["id"] for a in joined.json()["attendees"]} == {"u3", "u5"}
    assert observer.post(f"/api/meetings/{meeting['id']}/advance", json={}).status_code == 403
    assert observer.post(f"/api/meetings/{meeting['id']}/end", json={}).status_code == 403
    assert observer.put(f"/api/meetings/{meeting['id']}/rating", json={"rating": 8}).status_code == 403


def test_join_is_idempotent_and_does_not_bump_version(login: Login) -> None:
    meeting = start(login("u3"))
    client = login("u2")
    first = client.post(f"/api/meetings/{meeting['id']}/join").json()
    second = client.post(f"/api/meetings/{meeting['id']}/join").json()
    assert first["version"] == second["version"]
    assert len(second["attendees"]) == 2


def test_only_facilitator_advances_and_ends(login: Login) -> None:
    meeting = start(login("u3"))
    other = login("u2")
    other.post(f"/api/meetings/{meeting['id']}/join")
    assert other.post(f"/api/meetings/{meeting['id']}/advance", json={}).status_code == 403
    assert other.post(f"/api/meetings/{meeting['id']}/end", json={}).status_code == 403
    admin = login("u1")  # even an Admin is not the facilitator
    admin.post(f"/api/meetings/{meeting['id']}/join")
    assert admin.post(f"/api/meetings/{meeting['id']}/advance", json={}).status_code == 403
    state = login("u3").post(f"/api/meetings/{meeting['id']}/advance", json={}).json()
    assert state["section_key"] == "ids"


def test_advance_through_sections_and_stop_at_last(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    keys = [facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={}).json()["section_key"] for _ in range(2)]
    assert keys == ["ids", "conclude"]
    last = facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={})
    assert last.status_code == 409
    assert last.json()["error"]["code"] == "last_section"


def test_stale_expected_version_is_rejected(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    stale = facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={"expected_version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_version"
    fresh = facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={"expected_version": meeting["version"]})
    assert fresh.status_code == 200


def test_facilitator_can_end_at_any_time(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    ended = facilitator.post(f"/api/meetings/{meeting['id']}/end", json={})
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    assert ended.json()["ended_at"] is not None


def test_timer_is_server_owned_and_overtime_does_not_auto_advance(login: Login, clocks: Clocks) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    viewer = login("u2")
    assert isinstance(clocks.timer, FrozenClock)
    clocks.timer.advance(timedelta(seconds=290))
    state = viewer.get(f"/api/meetings/{meeting['id']}").json()
    assert (state["section_elapsed_seconds"], state["overtime_seconds"]) == (290, 0)
    clocks.timer.advance(timedelta(seconds=75))  # 365s elapsed in a 300s section
    state = viewer.get(f"/api/meetings/{meeting['id']}").json()
    assert (state["section_elapsed_seconds"], state["overtime_seconds"]) == (365, 65)
    assert state["section_key"] == "scorecard"  # no automatic advance
    assert facilitator.get(f"/api/meetings/{meeting['id']}").json()["section_elapsed_seconds"] == 365  # same everywhere
    advanced = facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={}).json()
    assert (advanced["section_elapsed_seconds"], advanced["overtime_seconds"]) == (0, 0)  # timer restarts per section


def test_late_joiner_gets_current_section_and_elapsed(login: Login, clocks: Clocks) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={})
    assert isinstance(clocks.timer, FrozenClock)
    clocks.timer.advance(timedelta(seconds=42))
    late = login("u4").post(f"/api/meetings/{meeting['id']}/join").json()
    assert late["section_key"] == "ids"
    assert late["section_elapsed_seconds"] == 42


def test_ratings_rules(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    mid = meeting["id"]
    rate = lambda c, v: c.put(f"/api/meetings/{mid}/rating", json={"rating": v})
    to_conclude(facilitator, mid)
    assert rate(facilitator, 8).status_code == 200
    assert rate(facilitator, 6).json()["attendees"][0]["rating"] == 6  # can change until the end
    for bad in (0, 11, -1, 5.5, "9", None, True):
        assert rate(facilitator, bad).status_code == 422, bad
    outsider_member = login("u2")  # has not joined -> not an attendee
    assert rate(outsider_member, 7).status_code == 403
    outsider_member.post(f"/api/meetings/{mid}/join")
    assert rate(outsider_member, 10).status_code == 200
    observer = login("u5")
    observer.post(f"/api/meetings/{mid}/join")
    assert rate(observer, 5).status_code == 403


def test_ratings_only_open_in_conclude(login: Login) -> None:
    facilitator = login("u3")
    mid = start(facilitator)["id"]
    rate = lambda v: facilitator.put(f"/api/meetings/{mid}/rating", json={"rating": v})
    for section in ("scorecard", "ids"):
        assert facilitator.get(f"/api/meetings/{mid}").json()["section_key"] == section
        early = rate(7)
        assert early.status_code == 409, section
        assert early.json()["error"]["code"] == "rating_not_open"
        assert facilitator.get(f"/api/meetings/{mid}").json()["attendees"][0]["rating"] is None
        facilitator.post(f"/api/meetings/{mid}/advance", json={})
    assert rate(7).status_code == 200
    assert rate(9).json()["attendees"][0]["rating"] == 9


def test_ratings_become_immutable_after_end(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    to_conclude(facilitator, meeting["id"])
    facilitator.put(f"/api/meetings/{meeting['id']}/rating", json={"rating": 9})
    facilitator.post(f"/api/meetings/{meeting['id']}/end", json={})
    late = facilitator.put(f"/api/meetings/{meeting['id']}/rating", json={"rating": 1})
    assert late.status_code == 409
    assert facilitator.get(f"/api/meetings/{meeting['id']}").json()["attendees"][0]["rating"] == 9
    assert facilitator.post(f"/api/meetings/{meeting['id']}/join").status_code == 409


def test_summary_of_new_meeting_is_a_stable_snapshot(login: Login) -> None:
    facilitator = login("u3")
    meeting = start(facilitator)
    mid = meeting["id"]
    joiner = login("u2")
    joiner.post(f"/api/meetings/{mid}/join")
    observer = login("u5")
    observer.post(f"/api/meetings/{mid}/join")
    assert facilitator.get(f"/api/meetings/{mid}/summary").status_code == 409  # not ended yet
    to_conclude(facilitator, mid)
    facilitator.put(f"/api/meetings/{mid}/rating", json={"rating": 8})
    joiner.put(f"/api/meetings/{mid}/rating", json={"rating": 9})
    facilitator.post(f"{LEAD}/issues/i3/solve", json={"note": "Rota agreed", "meeting_id": mid})
    facilitator.post(f"{LEAD}/issues/i1/solve", json={"note": "Outside the meeting"})
    todo = facilitator.post(
        f"{LEAD}/issues/i3/todos", json={"title": "Publish rota", "owner_id": "u4", "meeting_id": mid}
    ).json()
    facilitator.post(f"{LEAD}/issues/i4/todos", json={"title": "Not in meeting", "owner_id": "u4"})
    facilitator.post(f"/api/meetings/{mid}/end", json={})

    summary = observer.get(f"/api/meetings/{mid}/summary").json()
    assert summary["scorecard_week"] == "2026-11-02"
    assert summary["issues_solved"] == ["i3"]
    assert summary["todos_created"] == [todo["id"]]
    assert summary["attendee_ids"] == ["u2", "u3", "u5"]
    assert summary["rating"] == 8.5
    assert summary["measurable_status"] == {
        "m1": "off_track", "m2": "on_track", "m3": "off_track", "m4": "on_track", "m5": "off_track",
    }  # fmt: skip

    # Later edits do not change history.
    facilitator.put(f"{LEAD}/measurables/m1/scores/2026-11-02", json={"value": 99})
    facilitator.post(f"{LEAD}/todos/{todo['id']}/complete")
    assert observer.get(f"/api/meetings/{mid}/summary").json() == summary


def test_meeting_events_are_persisted(login: Login, session) -> None:
    from sqlalchemy import text

    facilitator = login("u3")
    meeting = start(facilitator)
    login("u2").post(f"/api/meetings/{meeting['id']}/join")
    facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={})
    facilitator.post(f"/api/meetings/{meeting['id']}/end", json={})
    types = (
        session.execute(text("SELECT type FROM meeting_events WHERE meeting_id = :m ORDER BY id"), {"m": meeting["id"]})
        .scalars()
        .all()
    )
    assert types == ["started", "joined", "advanced", "ended"]


def test_seeded_meeting_summaries_available_via_api(login: Login) -> None:
    client = login("u5")
    mt1 = client.get("/api/meetings/mt1/summary").json()
    assert mt1 == {
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
    mt2 = client.get("/api/meetings/mt2/summary").json()
    assert mt2["scorecard_week"] == "2026-10-26"
    assert mt2["issues_solved"] == ["i6"]
    assert mt2["todos_created"] == ["t30"]
    assert mt2["rating"] == 8.3  # 8.25 rounded half up
    assert mt2["measurable_status"]["m1"] == "off_track"
    state = client.get("/api/meetings/mt2").json()
    assert state["status"] == "ended"
    assert state["average_rating"] == 8.3
    ids = [m["id"] for m in client.get(f"{LEAD}/meetings").json()]
    assert ids == ["mt2", "mt1"]


def test_ratings_on_ended_meeting_are_blocked_by_the_database_too(session) -> None:
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        session.execute(text("UPDATE meeting_ratings SET rating = 1 WHERE meeting_id = 'mt1' AND user_id = 'u1'"))
    session.rollback()
    with pytest.raises(IntegrityError):
        session.execute(
            text("INSERT INTO meeting_ratings (meeting_id, user_id, rating, updated_at) VALUES ('mt1','u4',5,now())")
        )
    session.rollback()


def test_two_active_meetings_for_one_team_rejected_by_database(login: Login, session) -> None:
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    start(login("u3"))
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO meetings (id, team_id, facilitator_id, status, started_at, section_started_at, scorecard_week)"
                " VALUES ('dup','team_lead','u2','active',now(),now(),'2026-11-02')"
            )
        )
    session.rollback()
