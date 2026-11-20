"""Meeting-summary consistency under real PostgreSQL concurrency.

A meeting-attributed mutation (create To-Do, solve Issue) takes ``FOR SHARE`` on the meeting row;
``meetings.end`` takes ``FOR UPDATE`` on it before snapshotting. These tests drive both interleavings
deterministically: a hook pauses one transaction *while it holds its lock*, the test waits (bounded)
until PostgreSQL reports the other transaction blocked on a lock, then releases the first. No sleep
decides the outcome (the 10 ms poll interval only paces the bounded wait).
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models
from app.auth import Principal
from app.clock import Clocks
from app.db import get_sessionmaker
from app.errors import AppError
from app.services import meetings, mutations
from app.services.common import company_timezone

pytestmark = [pytest.mark.concurrency]
TEAM = "team_lead"
WAIT = 15.0


@dataclass
class Gate:
    """Pauses the hooked transaction until released; both waits are bounded."""

    reached: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)

    def hold(self) -> None:
        self.reached.set()
        assert self.release.wait(WAIT), "gate was never released"


@dataclass
class Outcome:
    value: Any = None
    error: BaseException | None = None


def principal_for(session: Session, user_id: str) -> Principal:
    user = session.get_one(models.User, user_id)
    teams = frozenset(
        session.scalars(select(models.TeamMembership.team_id).where(models.TeamMembership.user_id == user_id))
    )
    return Principal(user=user, team_ids=teams)


def run_in_thread(fn: Callable[[Session], Any]) -> tuple[threading.Thread, Outcome]:
    outcome = Outcome()

    def target() -> None:
        with get_sessionmaker()() as s:
            try:
                outcome.value = fn(s)
            except BaseException as exc:  # noqa: BLE001 - surfaced to the test thread
                outcome.error = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, outcome


def wait_until_blocked(session: Session, query_fragment: str) -> None:
    """Bounded poll: another backend running ``query_fragment`` is waiting on a lock."""
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        blocked = session.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                " AND pid <> pg_backend_pid() AND query ILIKE :frag"
            ),
            {"frag": f"%{query_fragment}%"},
        ).scalar_one()
        session.rollback()
        if blocked:
            return
        time.sleep(0.01)
    pytest.fail(f"no backend blocked on a lock for {query_fragment!r}")


def start_meeting(clocks: Clocks) -> str:
    with get_sessionmaker()() as s:
        return meetings.start(s, principal_for(s, "u3"), TEAM, clocks, company_timezone(s)).id


def do_end(meeting_id: str, clocks: Clocks) -> Callable[[Session], Any]:
    def run(s: Session) -> Any:
        return meetings.end(s, principal_for(s, "u3"), meeting_id, None, clocks, company_timezone(s))

    return run


def do_todo(meeting_id: str, clocks: Clocks) -> Callable[[Session], Any]:
    def run(s: Session) -> Any:
        return mutations.create_todo_from_issue(
            s, TEAM, "i3", "Race to-do", "u4", meeting_id, clocks.business.now(), company_timezone(s)
        )

    return run


def do_solve(meeting_id: str, clocks: Clocks) -> Callable[[Session], Any]:
    def run(s: Session) -> Any:
        return mutations.solve_issue(s, TEAM, "i3", "Race note", meeting_id, clocks.business.now())

    return run


def do_issue(meeting_id: str, clocks: Clocks) -> Callable[[Session], Any]:
    def run(s: Session) -> Any:
        return mutations.create_issue(
            s, principal_for(s, "u3"), TEAM, "Race issue", None, meeting_id, clocks.business.now()
        )

    return run


MUTATIONS = {"todo": do_todo, "solve": do_solve, "issue": do_issue}


@contextmanager
def hook(target: Any, name: str, gate: Gate) -> Iterator[None]:
    """Pause inside ``target.name`` (the original still runs afterwards), holding the caller's locks."""
    original = getattr(target, name)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        gate.hold()
        return original(*args, **kwargs)

    setattr(target, name, wrapper)
    try:
        yield
    finally:
        setattr(target, name, original)


def persisted(session: Session, meeting_id: str) -> tuple[list[str], list[str]]:
    todos = list(session.scalars(text("SELECT id FROM todos WHERE created_in_meeting_id = :m"), {"m": meeting_id}))
    solved = list(session.scalars(text("SELECT id FROM issues WHERE solved_in_meeting_id = :m"), {"m": meeting_id}))
    session.rollback()
    return todos, solved


@pytest.mark.parametrize("kind", ["todo", "solve", "issue"])
def test_mutation_holding_lock_makes_end_wait_and_summary_includes_it(
    clocks: Clocks, session: Session, kind: str
) -> None:
    """Scenario A: the mutation holds the meeting lock first; ``end`` waits, then snapshots it."""
    mid = start_meeting(clocks)
    gate = Gate()
    with hook(mutations, "_changed", gate):  # runs just before the mutation's commit
        mutator, mutated = run_in_thread(MUTATIONS[kind](mid, clocks))
        assert gate.reached.wait(WAIT)
        ender, ended = run_in_thread(do_end(mid, clocks))
        wait_until_blocked(session, "FROM meetings")  # end is queued behind the shared lock
        assert ender.is_alive()
        gate.release.set()
        mutator.join(WAIT)
        ender.join(WAIT)
    assert mutated.error is None, mutated.error
    assert ended.error is None, ended.error
    summary = ended.value.summary
    assert summary is not None
    todos, solved = persisted(session, mid)
    if kind == "todo":
        assert len(todos) == 1
        assert summary.todos_created == todos
    elif kind == "solve":
        assert solved == ["i3"]
        assert summary.issues_solved == ["i3"]
    else:  # an attributed Issue creation is validated, but Issues carry no meeting tag in the summary
        assert todos == []
        assert solved == []
        assert session.execute(text("SELECT count(*) FROM issues WHERE title = 'Race issue'")).scalar_one() == 1
    with get_sessionmaker()() as s:  # the stored snapshot equals what ``end`` returned
        assert meetings.summary(s, mid).model_dump() == summary.model_dump()


@pytest.mark.parametrize("kind", ["todo", "solve", "issue"])
def test_end_holding_lock_rejects_the_mutation_with_conflict(clocks: Clocks, session: Session, kind: str) -> None:
    """Scenario B: ``end`` holds the lock first; the mutation waits, then loses with 409 and writes nothing."""
    mid = start_meeting(clocks)
    gate = Gate()
    with hook(meetings, "_record", gate):  # inside end(): lock held, summary built, not yet committed
        ender, ended = run_in_thread(do_end(mid, clocks))
        assert gate.reached.wait(WAIT)
        mutator, mutated = run_in_thread(MUTATIONS[kind](mid, clocks))
        wait_until_blocked(session, "FROM meetings")  # the mutation is queued behind the update lock
        assert mutator.is_alive()
        gate.release.set()
        ender.join(WAIT)
        mutator.join(WAIT)
    assert ended.error is None, ended.error
    assert isinstance(mutated.error, AppError), mutated.error
    assert (mutated.error.status, mutated.error.code) == (409, "meeting_ended")
    assert persisted(session, mid) == ([], [])
    assert session.execute(text("SELECT count(*) FROM todos WHERE title = 'Race to-do'")).scalar_one() == 0
    assert session.execute(text("SELECT count(*) FROM issues WHERE title = 'Race issue'")).scalar_one() == 0
    assert session.execute(text("SELECT solved_at FROM issues WHERE id = 'i3'")).scalar_one() is None
    summary = ended.value.summary
    assert summary is not None
    assert summary.todos_created == []
    assert summary.issues_solved == []
    with get_sessionmaker()() as s:
        assert meetings.summary(s, mid).model_dump() == summary.model_dump()


def test_attributed_mutations_share_the_lock(clocks: Clocks) -> None:
    """A second attributed mutation validates the meeting while the first still holds its shared lock."""
    mid = start_meeting(clocks)
    gate = Gate()
    with hook(mutations, "_changed", gate):
        first, first_out = run_in_thread(do_todo(mid, clocks))
        assert gate.reached.wait(WAIT)
        with get_sessionmaker()() as s:
            assert mutations._validate_meeting(s, TEAM, mid) == mid
            s.rollback()
        gate.release.set()
        first.join(WAIT)
    assert first_out.error is None, first_out.error


def test_unattributed_mutations_ignore_the_meeting_lock(clocks: Clocks, session: Session) -> None:
    """A mutation without meeting_id is neither blocked by an ending meeting nor part of its summary."""
    mid = start_meeting(clocks)
    gate = Gate()
    with hook(meetings, "_record", gate):
        ender, ended = run_in_thread(do_end(mid, clocks))
        assert gate.reached.wait(WAIT)
        done, out = run_in_thread(
            lambda s: mutations.solve_issue(s, TEAM, "i3", "Outside", None, clocks.business.now())
        )
        done.join(WAIT)  # completes while end() still holds its lock
        assert not done.is_alive()
        assert out.error is None, out.error
        gate.release.set()
        ender.join(WAIT)
    assert ended.error is None, ended.error
    assert persisted(session, mid) == ([], [])


def test_http_mutations_after_end_are_409_and_leave_no_rows(login: Callable[[str], Any]) -> None:
    facilitator = login("u3")
    mid = facilitator.post(f"/api/teams/{TEAM}/meetings").json()["id"]
    facilitator.post(f"/api/meetings/{mid}/end", json={})
    responses = [
        facilitator.post(
            f"/api/teams/{TEAM}/issues/i3/todos", json={"title": "Late", "owner_id": "u4", "meeting_id": mid}
        ),
        facilitator.post(f"/api/teams/{TEAM}/issues/i3/solve", json={"note": "Late", "meeting_id": mid}),
        facilitator.post(f"/api/teams/{TEAM}/issues", json={"title": "Late issue", "meeting_id": mid}),
    ]
    for response in responses:
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "meeting_ended"
    assert facilitator.get(f"/api/meetings/{mid}/summary").json()["todos_created"] == []
