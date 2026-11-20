"""Test fixtures.

Database isolation: tests run against the dedicated ``l10_test`` database (created by
``docker/postgres-init.sql``); ``assert_safe_database`` refuses any other name. The schema is
rebuilt once per session via the real Alembic migration, and every test starts from a TRUNCATE +
fresh seed load.

Clock strategy: the *business* clock is frozen at the seed's default ``APP_NOW``
(2026-11-11T15:00:00Z) and the *timer* clock is a controllable fake, so meeting timers are
asserted without sleeping.
"""

import os
import socket
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://l10:l10@localhost:5432/l10_test")
os.environ.pop("APP_NOW", None)
os.environ["ENABLE_TEST_ENDPOINTS"] = "false"

from app.cli import migrate
from app.clock import Clocks, FrozenClock
from app.config import DEFAULT_APP_NOW, get_settings
from app.db import get_engine, get_sessionmaker
from app.main import create_app
from app.testing import assert_safe_database, reset_and_seed

TIMER_START = datetime(2026, 11, 11, 15, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Rebuild the schema once using the real migrations."""
    url = get_settings().database_url
    assert_safe_database(url)
    with get_engine().begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    migrate()


@pytest.fixture(autouse=True)
def _fresh_seed(_database: None) -> None:
    """Every test starts from the freshly seeded state."""
    with get_sessionmaker()() as session:
        reset_and_seed(session, get_settings().database_url)


@pytest.fixture
def session() -> Iterator[Session]:
    """A DB session for direct assertions."""
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def clocks() -> Clocks:
    """Frozen business clock + controllable timer clock."""
    return Clocks(business=FrozenClock(DEFAULT_APP_NOW), timer=FrozenClock(TIMER_START))


@pytest.fixture
def app_factory(clocks: Clocks) -> Callable[[], TestClient]:
    """Build independent clients (each with its own cookie jar) for the same app/clocks."""
    app = create_app(get_settings(), clocks)

    def make() -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    return make


@pytest.fixture
def login(app_factory: Callable[[], TestClient]) -> Callable[[str], TestClient]:
    """Return a client signed in as the given seeded user id."""

    def _login(user_id: str) -> TestClient:
        client = app_factory()
        response = client.post("/api/auth/login", json={"user_id": user_id})
        assert response.status_code == 200, response.text
        return client

    return _login


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live_server(clocks: Clocks) -> Iterator[str]:
    """A real uvicorn server (with the LISTEN/NOTIFY hub running) for concurrency and SSE tests."""
    app = create_app(get_settings(), clocks)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            msg = "live server did not start"
            raise RuntimeError(msg)
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)
