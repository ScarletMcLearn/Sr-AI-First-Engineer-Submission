"""Team page endpoints: scorecard, issues, to-dos, rocks."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Response

from app.auth import CurrentPrincipal, require_team_read, require_team_write
from app.routes.deps import Clk, Db, Tz
from app.schemas import (
    ErrorResponse,
    IssueCreateIn,
    IssueOut,
    IssuePatchIn,
    IssueSolveIn,
    MakeIssueOut,
    RocksOut,
    ScorecardOut,
    ScoreIn,
    TodoFromIssueIn,
    TodoOut,
    TodosOut,
)
from app.services import mutations, team_reads

router = APIRouter(
    prefix="/teams/{team_id}", tags=["team"], responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)


@router.get("/scorecard", summary="Measurables by week (last 13 weeks including the current one)")
def get_scorecard(team_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> ScorecardOut:
    """Scores with computed status per cell."""
    require_team_read(session, principal, team_id)
    return team_reads.scorecard(session, team_id, clocks.business.now(), tz)


@router.put(
    "/measurables/{measurable_id}/scores/{week_start}",
    summary="Set a score (last save wins)",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def put_score(
    team_id: str,
    measurable_id: str,
    week_start: date,
    body: ScoreIn,
    principal: CurrentPrincipal,
    session: Db,
    clocks: Clk,
    tz: Tz,
) -> ScorecardOut:
    """Edit a score inline. Returns the refreshed scorecard so clients stay consistent."""
    require_team_write(session, principal, team_id)
    mutations.set_score(
        session,
        principal,
        team_id,
        measurable_id,
        week_start,
        body.value,
        body.expected_version,
        clocks.business.now(),
        tz,
    )
    return team_reads.scorecard(session, team_id, clocks.business.now(), tz)


@router.post(
    "/measurables/{measurable_id}/weeks/{week_start}/issue",
    summary="Make it an Issue (idempotent, duplicate-free)",
    responses={200: {"model": MakeIssueOut}, 201: {"model": MakeIssueOut}, 422: {"model": ErrorResponse}},
)
def make_issue(
    team_id: str,
    measurable_id: str,
    week_start: date,
    response: Response,
    principal: CurrentPrincipal,
    session: Db,
    clocks: Clk,
    tz: Tz,
) -> MakeIssueOut:
    """201 when created, 200 when the existing unsolved Issue is returned."""
    require_team_write(session, principal, team_id)
    result = mutations.make_issue(session, principal, team_id, measurable_id, week_start, clocks.business.now(), tz)
    response.status_code = 201 if result.created else 200
    return result


@router.get("/issues", summary="List Issues (unsolved in Issue order, or solved)")
def list_issues(
    team_id: str, principal: CurrentPrincipal, session: Db, status: Literal["unsolved", "solved"] = "unsolved"
) -> list[IssueOut]:
    """Unsolved Issues are ordered priority 5..1, then oldest first, unprioritised last."""
    require_team_read(session, principal, team_id)
    return team_reads.issues(session, team_id, solved=status == "solved")


@router.post("/issues", status_code=201, summary="Create an Issue", responses={422: {"model": ErrorResponse}})
def create_issue(team_id: str, body: IssueCreateIn, principal: CurrentPrincipal, session: Db, clocks: Clk) -> IssueOut:
    """The creator becomes the owner."""
    require_team_write(session, principal, team_id)
    return mutations.create_issue(
        session, principal, team_id, body.title, body.priority, body.meeting_id, clocks.business.now()
    )


@router.patch("/issues/{issue_id}", summary="Set Issue priority", responses={409: {"model": ErrorResponse}})
def patch_issue(team_id: str, issue_id: str, body: IssuePatchIn, principal: CurrentPrincipal, session: Db) -> IssueOut:
    """Set or clear the priority (1-5)."""
    require_team_write(session, principal, team_id)
    return mutations.set_issue_priority(session, team_id, issue_id, body.priority, body.expected_version)


@router.post(
    "/issues/{issue_id}/solve",
    summary="Solve an Issue (note required)",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def solve_issue(
    team_id: str, issue_id: str, body: IssueSolveIn, principal: CurrentPrincipal, session: Db, clocks: Clk
) -> IssueOut:
    """Mark an Issue solved with a required resolution note."""
    require_team_write(session, principal, team_id)
    return mutations.solve_issue(session, team_id, issue_id, body.note, body.meeting_id, clocks.business.now())


@router.post(
    "/issues/{issue_id}/todos",
    status_code=201,
    summary="Add a To-Do for an Issue",
    responses={422: {"model": ErrorResponse}},
)
def add_todo(
    team_id: str, issue_id: str, body: TodoFromIssueIn, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz
) -> TodoOut:
    """Due seven calendar days from today (company time); owner must be an eligible Admin/Team Member."""
    require_team_write(session, principal, team_id)
    return mutations.create_todo_from_issue(
        session, team_id, issue_id, body.title, body.owner_id, body.meeting_id, clocks.business.now(), tz
    )


@router.get("/todos", summary="To-Dos and last closed week's completion rate")
def list_todos(team_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> TodosOut:
    """Overdue To-Dos are flagged; completion uses the last closed week."""
    require_team_read(session, principal, team_id)
    return team_reads.todos(session, team_id, clocks.business.now(), tz)


@router.post("/todos/{todo_id}/complete", summary="Mark a To-Do done")
def complete_todo(team_id: str, todo_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> TodoOut:
    """Idempotent."""
    require_team_write(session, principal, team_id)
    return mutations.set_todo_done(session, team_id, todo_id, done=True, now=clocks.business.now(), tz=tz)


@router.post("/todos/{todo_id}/undo", summary="Undo a To-Do completion")
def undo_todo(team_id: str, todo_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> TodoOut:
    """Idempotent."""
    require_team_write(session, principal, team_id)
    return mutations.set_todo_done(session, team_id, todo_id, done=False, now=clocks.business.now(), tz=tz)


@router.get("/rocks", summary="Current quarter's Rocks (read-only)")
def list_rocks(team_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> RocksOut:
    """Rocks with computed status, progress and milestones."""
    require_team_read(session, principal, team_id)
    return team_reads.rocks(session, team_id, clocks.business.now(), tz)
