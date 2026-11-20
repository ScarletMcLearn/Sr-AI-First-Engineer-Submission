"""Seeded-user login, current user and team listing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app import models
from app.auth import SESSION_COOKIE, CurrentPrincipal, accessible_team_ids, require_team_read, sign_session
from app.config import Settings, get_settings
from app.errors import not_found
from app.routes.deps import Db
from app.schemas import LoginIn, MeOut, TeamDetailOut, TeamOut, UserOut, UserRef

router = APIRouter(tags=["identity"])


def _user_out(u: models.User) -> UserOut:
    return UserOut(id=u.id, name=u.name, email=u.email, role=u.role)


@router.get("/users", summary="List seeded users (for the user switcher)")
def list_users(session: Db) -> list[UserOut]:
    """Public list of seeded users; the simplified login model has no passwords."""
    return [_user_out(u) for u in session.scalars(select(models.User).order_by(models.User.id))]


@router.post("/auth/login", summary="Sign in as a seeded user")
def login(
    body: LoginIn, response: Response, session: Db, settings: Annotated[Settings, Depends(get_settings)]
) -> MeOut:
    """Set the signed session cookie. Unknown users get 404."""
    user = session.get(models.User, body.user_id)
    if user is None:
        raise not_found("Unknown user")
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(user.id, settings.session_secret),
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 12,
    )
    team_ids = _teams_for(session, user)
    return MeOut(user=_user_out(user), teams=team_ids)


def _teams_for(session: Db, user: models.User) -> list[TeamOut]:
    if user.role == "admin":
        stmt = select(models.Team).order_by(models.Team.name)
    else:
        stmt = (
            select(models.Team)
            .join(models.TeamMembership, models.TeamMembership.team_id == models.Team.id)
            .where(models.TeamMembership.user_id == user.id)
            .order_by(models.Team.name)
        )
    return [TeamOut(id=t.id, name=t.name) for t in session.scalars(stmt)]


@router.post("/auth/logout", status_code=204, summary="Sign out")
def logout(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", summary="Current user and accessible teams")
def me(principal: CurrentPrincipal, session: Db) -> MeOut:
    """Return the authenticated user with their teams (every team for Admins)."""
    return MeOut(user=_user_out(principal.user), teams=_teams_for(session, principal.user))


@router.get("/teams", summary="Teams the current user can access")
def list_teams(principal: CurrentPrincipal, session: Db) -> list[TeamOut]:
    """Teams visible to the user: all for Admins, memberships otherwise."""
    ids = accessible_team_ids(session, principal)
    teams = {t.id: t for t in session.scalars(select(models.Team).where(models.Team.id.in_(ids)))}
    return sorted((TeamOut(id=t.id, name=t.name) for t in teams.values()), key=lambda t: t.name)


@router.get("/teams/{team_id}", summary="Team with roster and eligible owners")
def get_team(team_id: str, principal: CurrentPrincipal, session: Db) -> TeamDetailOut:
    """Team details. 403 if the user cannot access the team."""
    team = require_team_read(session, principal, team_id)
    members = list(
        session.scalars(
            select(models.User)
            .join(models.TeamMembership, models.TeamMembership.user_id == models.User.id)
            .where(models.TeamMembership.team_id == team_id)
            .order_by(models.User.name)
        )
    )
    admins = list(session.scalars(select(models.User).where(models.User.role == "admin")))
    owners = {u.id: u for u in [*members, *admins] if u.role != "observer"}
    return TeamDetailOut(
        id=team.id,
        name=team.name,
        members=[_user_out(u) for u in members],
        eligible_owners=sorted((UserRef(id=u.id, name=u.name) for u in owners.values()), key=lambda r: r.name),
    )
