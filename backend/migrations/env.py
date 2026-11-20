"""Alembic environment: migrations are explicit SQL, no autogenerate."""

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    url = context.config.attributes.get("url") or get_settings().database_url
    engine = create_engine(url)
    with engine.begin() as connection:
        context.configure(connection=connection, target_metadata=None)
        context.run_migrations()
    engine.dispose()


run_migrations_online()
