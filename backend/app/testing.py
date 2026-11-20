"""Test-support: safe database reset. Never available against a non-test database."""

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.seed import seed_database

SAFE_SUFFIXES = ("_test", "_e2e")
KEEP_TABLES = ("alembic_version",)


def assert_safe_database(database_url: str) -> None:
    """Refuse to wipe anything that is not an isolated test/e2e database."""
    name = make_url(database_url).database or ""
    if not name.endswith(SAFE_SUFFIXES):
        msg = f"refusing to reset database {name!r}: only names ending in {SAFE_SUFFIXES} are allowed"
        raise RuntimeError(msg)


def reset_and_seed(session: Session, database_url: str) -> None:
    """Truncate every application table and reload the seed (test databases only)."""
    assert_safe_database(database_url)
    tables = session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> ALL(:keep)"),
        {"keep": list(KEEP_TABLES)},
    ).scalars()
    names = ", ".join(f'"{t}"' for t in tables)
    session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    session.commit()
    seed_database(session)
