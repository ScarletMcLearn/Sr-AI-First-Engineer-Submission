"""Real concurrency (threads -> real HTTP -> real PostgreSQL) and real-time SSE synchronisation."""

import json
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.concurrency]
LEAD = "/api/teams/team_lead"
PARALLEL = 12


def signed_in(base: str, user_id: str) -> httpx.Client:
    client = httpx.Client(base_url=base, timeout=20)
    assert client.post("/api/auth/login", json={"user_id": user_id}).status_code == 200
    return client


def test_concurrent_make_it_an_issue_creates_exactly_one_issue(live_server: str, session: Session) -> None:
    users = ["u2", "u3", "u4", "u1"] * (PARALLEL // 4)
    clients = [signed_in(live_server, uid) for uid in users]
    barrier = threading.Barrier(len(clients))

    def click(client: httpx.Client) -> httpx.Response:
        barrier.wait()
        return client.post(f"{LEAD}/measurables/m5/weeks/2026-10-19/issue")

    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        responses = list(pool.map(click, clients))

    assert all(r.status_code in {200, 201} for r in responses), [r.text for r in responses if r.status_code >= 400]
    assert sum(r.status_code == 201 for r in responses) == 1  # exactly one creator
    assert len({r.json()["issue"]["id"] for r in responses}) == 1  # everyone got the same Issue
    count = session.execute(
        text(
            "SELECT count(*) FROM issues WHERE source_measurable_id='m5' AND source_week_start='2026-10-19'"
            " AND solved_at IS NULL"
        )
    ).scalar_one()
    assert count == 1
    # Retrying stays safe and returns the same Issue.
    again = clients[0].post(f"{LEAD}/measurables/m5/weeks/2026-10-19/issue")
    assert again.status_code == 200
    assert again.json()["issue"]["id"] == responses[0].json()["issue"]["id"]


def test_make_issue_is_repeatable_over_many_rounds(live_server: str, session: Session) -> None:
    clients = [signed_in(live_server, uid) for uid in ("u2", "u3", "u4", "u1")]
    weeks = ["2026-08-31", "2026-10-05", "2026-10-26", "2026-11-02"]  # m1 off-track weeks (11-02 pre-seeded: i5)
    for week in weeks:
        barrier = threading.Barrier(len(clients))

        def click(client: httpx.Client, week: str = week, barrier: threading.Barrier = barrier) -> httpx.Response:
            barrier.wait()
            return client.post(f"{LEAD}/measurables/m1/weeks/{week}/issue")

        with ThreadPoolExecutor(max_workers=len(clients)) as pool:
            results = list(pool.map(click, clients))
        assert {r.status_code for r in results} <= {200, 201}
        assert len({r.json()["issue"]["id"] for r in results}) == 1
    total = session.execute(
        text("SELECT count(*) FROM issues WHERE source_measurable_id='m1' AND solved_at IS NULL")
    ).scalar_one()
    assert total == len(weeks)


def test_concurrent_meeting_starts_create_one_active_meeting(live_server: str, session: Session) -> None:
    users = ["u2", "u3", "u4", "u1"] * (PARALLEL // 4)
    clients = [signed_in(live_server, uid) for uid in users]
    barrier = threading.Barrier(len(clients))

    def go(client: httpx.Client) -> httpx.Response:
        barrier.wait()
        return client.post(f"{LEAD}/meetings")

    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        responses = list(pool.map(go, clients))
    codes = sorted(r.status_code for r in responses)
    assert codes.count(201) == 1
    assert codes.count(409) == len(clients) - 1
    assert all(r.json()["error"]["code"] == "meeting_already_active" for r in responses if r.status_code == 409)
    active = session.execute(
        text("SELECT count(*) FROM meetings WHERE team_id='team_lead' AND status='active'")
    ).scalar_one()
    assert active == 1


def test_concurrent_advance_requests_with_same_version_apply_once(live_server: str) -> None:
    facilitator = signed_in(live_server, "u3")
    meeting = facilitator.post(f"{LEAD}/meetings").json()
    barrier = threading.Barrier(6)

    def go(_: int) -> httpx.Response:
        barrier.wait()
        return facilitator.post(f"/api/meetings/{meeting['id']}/advance", json={"expected_version": meeting["version"]})

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(go, range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]  # no double-advance
    assert facilitator.get(f"/api/meetings/{meeting['id']}").json()["section_key"] == "ids"


# ---------------------------------------------------------------- real-time


class EventReader:
    """Reads Server-Sent Events from a live meeting stream on a background thread."""

    def __init__(self, base: str, user_id: str, meeting_id: str) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._client = signed_in(base, user_id)
        self._url = f"/api/meetings/{meeting_id}/events"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        with self._client.stream("GET", self._url, timeout=httpx.Timeout(30, read=30)) as response:
            event, data = "message", ""
            for line in response.iter_lines():
                if self._stop.is_set():
                    return
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                elif line == "" and data:
                    with self._cond:
                        self.events.append((event, json.loads(data)))
                        self._cond.notify_all()
                    event, data = "message", ""

    def wait_for(self, predicate: Any, timeout: float = 5.0) -> tuple[str, dict[str, Any]]:
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                for item in self.events:
                    if predicate(item):
                        return item
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    msg = f"no matching event within {timeout}s; got {[(e, d.get('version')) for e, d in self.events]}"
                    raise AssertionError(msg)
                self._cond.wait(remaining)

    def close(self) -> None:
        self._stop.set()
        self._client.close()


@contextmanager
def reader(base: str, user_id: str, meeting_id: str) -> Iterator[EventReader]:
    r = EventReader(base, user_id, meeting_id)
    try:
        yield r
    finally:
        r.close()


@pytest.mark.realtime
def test_second_browser_follows_facilitator_within_a_second(live_server: str) -> None:
    facilitator = signed_in(live_server, "u3")
    meeting = facilitator.post(f"{LEAD}/meetings").json()
    mid = meeting["id"]
    with reader(live_server, "u2", mid) as follower:
        first = follower.wait_for(lambda e: e[0] == "state")
        assert first[1]["section_key"] == "scorecard"  # initial snapshot on connect
        t0 = time.monotonic()
        facilitator.post(f"/api/meetings/{mid}/advance", json={})
        event = follower.wait_for(lambda e: e[0] == "state" and e[1]["section_key"] == "ids", timeout=3)
        assert time.monotonic() - t0 < 1.0  # "within about a second"
        assert event[1]["version"] > first[1]["version"]
        facilitator.post(f"/api/meetings/{mid}/end", json={})
        ended = follower.wait_for(lambda e: e[0] == "state" and e[1]["status"] == "ended", timeout=3)
        assert ended[1]["summary"]["scorecard_week"] == "2026-11-02"


@pytest.mark.realtime
def test_join_and_rating_events_reach_other_attendees(live_server: str) -> None:
    facilitator = signed_in(live_server, "u3")
    mid = facilitator.post(f"{LEAD}/meetings").json()["id"]
    with reader(live_server, "u3", mid) as watcher:
        watcher.wait_for(lambda e: e[0] == "state")
        member = signed_in(live_server, "u2")
        member.post(f"/api/meetings/{mid}/join")
        joined = watcher.wait_for(lambda e: e[0] == "state" and len(e[1]["attendees"]) == 2, timeout=3)
        assert {a["user"]["id"] for a in joined[1]["attendees"]} == {"u3", "u2"}
        for _ in range(2):
            facilitator.post(f"/api/meetings/{mid}/advance", json={})
        member.put(f"/api/meetings/{mid}/rating", json={"rating": 7})
        rated = watcher.wait_for(lambda e: e[0] == "state" and e[1]["average_rating"] == 7.0, timeout=3)
        assert rated[1]["average_rating"] == 7.0


@pytest.mark.realtime
def test_data_changes_are_pushed_so_clients_can_refetch(live_server: str) -> None:
    facilitator = signed_in(live_server, "u3")
    mid = facilitator.post(f"{LEAD}/meetings").json()["id"]
    with reader(live_server, "u2", mid) as follower:
        follower.wait_for(lambda e: e[0] == "state")
        facilitator.post(f"{LEAD}/issues/i3/solve", json={"note": "done", "meeting_id": mid})
        changed = follower.wait_for(lambda e: e[0] == "data_changed" and e[1]["resource"] == "issues", timeout=3)
        assert changed[0] == "data_changed"


@pytest.mark.realtime
def test_reconnect_receives_current_authoritative_state(live_server: str) -> None:
    facilitator = signed_in(live_server, "u3")
    mid = facilitator.post(f"{LEAD}/meetings").json()["id"]
    with reader(live_server, "u2", mid) as before:
        before.wait_for(lambda e: e[0] == "state")
    # "Disconnected": changes happen while the follower is away.
    facilitator.post(f"/api/meetings/{mid}/advance", json={})
    facilitator.post(f"/api/meetings/{mid}/advance", json={})
    with reader(live_server, "u2", mid) as after:  # reconnect
        snapshot = after.wait_for(lambda e: e[0] == "state")
        assert snapshot[1]["section_key"] == "conclude"
        assert snapshot[1]["version"] > before.events[0][1]["version"]


@pytest.mark.realtime
def test_stream_requires_authentication_and_team_access(live_server: str) -> None:
    mid = signed_in(live_server, "u3").post(f"{LEAD}/meetings").json()["id"]
    anon = httpx.Client(base_url=live_server, timeout=10)
    assert anon.get(f"/api/meetings/{mid}/events").status_code == 401
    assert signed_in(live_server, "u8").get(f"/api/meetings/{mid}/events").status_code == 403
