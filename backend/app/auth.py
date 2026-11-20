"""Authentication and authorization.

Authentication is the assessment's simplified model: the browser picks a seeded user and the
server issues an HMAC-signed, HttpOnly session cookie containing only the user id. Roles and
team memberships are **always loaded from the database** on every request; nothing about
authority is ever read from a request body.

Limitation (by design for the assessment): there are no passwords, so anyone can pick any
seeded user. Production would put a real identity provider behind the same ``current_user``
dependency.
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import forbidden, not_found, unauthorized

SESSION_COOKIE = "l10_session"
WRITER_ROLES = frozenset({"admin", "team_member"})


def sign_session(user_id: str, secret: str) -> str:
    """Return ``<b64 user id>.<hmac>`` for the cookie."""
    payload = base64.urlsafe_b64encode(user_id.encode()).decode()
    mac = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{mac}"


def verify_session(token: str, secret: str) -> str | None:
    """Return the user id if the signature is valid, else ``None``."""
    payload, _, mac = token.partition(".")
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not payload or not hmac.compare_digest(mac, expected):
        return None
    try:
        return base64.urlsafe_b64decode(payload.encode()).decode()
    except ValueError:
        return None


@dataclass(frozen=True)
class Principal:
    """The authenticated user with authority loaded from the database."""

    user: models.User
    team_ids: frozenset[str]

    @property
    def is_admin(self) -> bool:
        """Admins act as team members in every team."""
        return self.user.role == "admin"

    @property
    def can_write(self) -> bool:
        """Admins and Team Members may modify data; Observers may not."""
        return self.user.role in WRITER_ROLES


def load_principal(session: Session, token: str | None, secret: str) -> Principal:
    """Resolve a session token to a user and memberships (401 when absent/invalid)."""
    if token is None:
        raise unauthorized()
    user_id = verify_session(token, secret)
    user = session.get(models.User, user_id) if user_id else None
    if user is None:
        raise unauthorized("Invalid session")
    team_ids = frozenset(
        session.scalars(select(models.TeamMembership.team_id).where(models.TeamMembership.user_id == user.id))
    )
    return Principal(user, team_ids)


def current_principal(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Principal:
    """FastAPI dependency for the authenticated principal."""
    return load_principal(session, token, settings.session_secret)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def accessible_team_ids(session: Session, principal: Principal) -> list[str]:
    """Ids of the teams the principal may read (all teams for Admins)."""
    if principal.is_admin:
        return list(session.scalars(select(models.Team.id).order_by(models.Team.name)))
    return sorted(principal.team_ids)


def require_team_read(session: Session, principal: Principal, team_id: str) -> models.Team:
    """Return the team if the principal may read it; otherwise 403 (404 for admins on unknown ids)."""
    team = session.get(models.Team, team_id)
    if principal.is_admin:
        if team is None:
            raise not_found("Team not found")
        return team
    if team is None or team_id not in principal.team_ids:
        # Same response for unknown and foreign teams: guessing ids reveals nothing.
        raise forbidden("You do not have access to this team")
    return team


def require_team_write(session: Session, principal: Principal, team_id: str) -> models.Team:
    """Return the team if the principal may modify its data."""
    team = require_team_read(session, principal, team_id)
    if not principal.can_write:
        raise forbidden("Observers have read-only access")
    return team
