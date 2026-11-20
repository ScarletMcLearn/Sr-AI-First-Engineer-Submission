"""Meeting endpoints and the live event stream."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.auth import SESSION_COOKIE, CurrentPrincipal, load_principal, require_team_read, require_team_write
from app.config import get_settings
from app.db import get_sessionmaker
from app.realtime import Hub
from app.routes.deps import Clk, Db, Tz
from app.schemas import (
    ActiveMeetingOut,
    AdvanceIn,
    EndIn,
    ErrorResponse,
    MeetingListItemOut,
    MeetingStateOut,
    MeetingSummaryOut,
    RatingIn,
)
from app.services import meetings

ERR: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}
team_router = APIRouter(prefix="/teams/{team_id}/meetings", tags=["meetings"], responses=ERR)
router = APIRouter(prefix="/meetings/{meeting_id}", tags=["meetings"], responses=ERR)


@team_router.get("", summary="List a team's meetings (newest first)")
def list_team_meetings(team_id: str, principal: CurrentPrincipal, session: Db) -> list[MeetingListItemOut]:
    """Active and ended meetings."""
    require_team_read(session, principal, team_id)
    return meetings.list_meetings(session, team_id)


@team_router.get("/active", summary="The team's active meeting, if any")
def get_active(team_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk) -> ActiveMeetingOut:
    """``meeting`` is null when no meeting is running."""
    require_team_read(session, principal, team_id)
    return ActiveMeetingOut(meeting=meetings.active_meeting(session, team_id, clocks))


@team_router.post("", status_code=201, summary="Start a meeting (starter becomes facilitator)")
def start_meeting(team_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz) -> MeetingStateOut:
    """Admins and Team Members only; 409 if the team already has an active meeting."""
    require_team_write(session, principal, team_id)
    return meetings.start(session, principal, team_id, clocks, tz)


def _read(session: Db, principal: CurrentPrincipal, meeting_id: str) -> None:
    require_team_read(session, principal, meetings.meeting_team(session, meeting_id))


@router.get("", summary="Authoritative meeting state")
def get_meeting(meeting_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk) -> MeetingStateOut:
    """Current section, server-computed elapsed time, attendees and ratings."""
    _read(session, principal, meeting_id)
    return meetings.get_state(session, meeting_id, clocks)


@router.get("/summary", summary="Summary of an ended meeting")
def get_summary(meeting_id: str, principal: CurrentPrincipal, session: Db) -> MeetingSummaryOut:
    """Persisted snapshot; also available for the seeded meetings."""
    _read(session, principal, meeting_id)
    return meetings.summary(session, meeting_id)


@router.post("/join", summary="Join the meeting (idempotent)")
def join_meeting(meeting_id: str, principal: CurrentPrincipal, session: Db, clocks: Clk) -> MeetingStateOut:
    """Anyone who can read the team may join, including Observers."""
    _read(session, principal, meeting_id)
    return meetings.join(session, principal, meeting_id, clocks)


@router.post("/advance", summary="Advance to the next section (facilitator only)")
def advance_meeting(
    meeting_id: str, body: AdvanceIn, principal: CurrentPrincipal, session: Db, clocks: Clk
) -> MeetingStateOut:
    """Never happens automatically when a timer expires."""
    _read(session, principal, meeting_id)
    return meetings.advance(session, principal, meeting_id, body.expected_version, clocks)


@router.post("/end", summary="End the meeting (facilitator only)")
def end_meeting(
    meeting_id: str, body: EndIn, principal: CurrentPrincipal, session: Db, clocks: Clk, tz: Tz
) -> MeetingStateOut:
    """Allowed from any section; stores the immutable summary snapshot."""
    _read(session, principal, meeting_id)
    return meetings.end(session, principal, meeting_id, body.expected_version, clocks, tz)


@router.put("/rating", summary="Rate the meeting 1-10 (attending Admins/Team Members)")
def rate_meeting(
    meeting_id: str, body: RatingIn, principal: CurrentPrincipal, session: Db, clocks: Clk
) -> MeetingStateOut:
    """Can be changed until the meeting ends."""
    _read(session, principal, meeting_id)
    return meetings.rate(session, principal, meeting_id, body.rating, clocks)


def _sse(event: str, data: object, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _authorize_stream(meeting_id: str, token: str | None) -> str:
    """Short-lived session: authenticate, authorize, return the team id (no connection held while streaming)."""
    with get_sessionmaker()() as session:
        principal = load_principal(session, token, get_settings().session_secret)
        team_id = meetings.meeting_team(session, meeting_id)
        require_team_read(session, principal, team_id)
        return team_id


def _load_state_json(request: Request, meeting_id: str) -> dict[str, object] | None:
    with get_sessionmaker()() as session:
        try:
            state = meetings.get_state(session, meeting_id, request.app.state.clocks)
        except Exception:  # noqa: BLE001 - meeting deleted mid-stream: client resyncs and gets a proper 404
            return None
        return state.model_dump(mode="json")


@router.get(
    "/events",
    summary="Live meeting events (Server-Sent Events)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_events(
    meeting_id: str,
    request: Request,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> StreamingResponse:
    """Stream live events.

    The first event is always the full authoritative ``state`` (so reconnects self-heal); later events
    are ``state`` (meeting changed), ``data_changed`` (scorecard/issues/to-dos changed) or ``resync``.
    """
    team_id = await run_in_threadpool(_authorize_stream, meeting_id, token)
    hub: Hub = request.app.state.hub
    sub = hub.subscribe(meeting_id, team_id)  # subscribe first so nothing is missed between snapshot and stream

    async def body() -> AsyncIterator[str]:
        try:
            yield "retry: 1000\n\n"
            initial = await run_in_threadpool(_load_state_json, request, meeting_id)
            if initial is None:
                return
            yield _sse("state", initial, int(str(initial["version"])))
            while True:
                try:
                    message = await asyncio.wait_for(sub.queue.get(), timeout=15)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield ": ping\n\n"
                    continue
                if message["event"] == "resync":
                    fresh = await run_in_threadpool(_load_state_json, request, meeting_id)
                    if fresh is not None:
                        yield _sse("state", fresh, int(str(fresh["version"])))
                        yield _sse("data_changed", {"resource": "all"})
                    continue
                data = message["data"]
                event_id = int(data["version"]) if message["event"] == "state" else None
                yield _sse(message["event"], data, event_id)
        finally:
            hub.unsubscribe(sub)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
