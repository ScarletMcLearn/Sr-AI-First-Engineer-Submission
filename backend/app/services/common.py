"""Shared helpers for services."""

import json
from collections.abc import Iterable
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models
from app.schemas import UserRef

NOTIFY_CHANNEL = "app_events"


def new_id(prefix: str) -> str:
    """Generate an id for a new entity (seed entities keep their original ids)."""
    return f"{prefix}_{uuid4().hex[:12]}"


def company_timezone(session: Session) -> ZoneInfo:
    """The company's business time zone."""
    name = session.scalars(select(models.Company.timezone).limit(1)).first()
    return ZoneInfo(name or "America/Chicago")


def user_refs(session: Session, ids: Iterable[str]) -> dict[str, UserRef]:
    """Load compact user references in one query."""
    wanted = set(ids)
    if not wanted:
        return {}
    rows = session.execute(select(models.User.id, models.User.name).where(models.User.id.in_(wanted)))
    return {uid: UserRef(id=uid, name=name) for uid, name in rows}


def notify(session: Session, payload: dict[str, object]) -> None:
    """Queue a Postgres NOTIFY; it is delivered only if (and when) the transaction commits."""
    session.execute(
        text("SELECT pg_notify(:channel, :payload)"), {"channel": NOTIFY_CHANNEL, "payload": json.dumps(payload)}
    )
