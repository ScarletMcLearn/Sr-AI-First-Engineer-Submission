"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.clock import Clocks, FrozenClock, SystemClock
from app.config import Settings, get_settings
from app.db import get_engine, get_sessionmaker
from app.errors import install_error_handlers
from app.realtime import Hub
from app.routes import identity, meetings, team
from app.services import meetings as meeting_service
from app.testing import assert_safe_database, reset_and_seed


def create_app(settings: Settings | None = None, clocks: Clocks | None = None) -> FastAPI:
    """Build the application. ``clocks`` lets tests inject deterministic time."""
    settings = settings or get_settings()
    clocks = clocks or Clocks(business=FrozenClock(settings.app_now), timer=SystemClock())

    def load_state(meeting_id: str) -> dict[str, Any] | None:
        with get_sessionmaker()() as session:
            try:
                return meeting_service.get_state(session, meeting_id, clocks).model_dump(mode="json")
            except Exception:
                return None

    hub = Hub(settings.database_url, lambda mid: run_in_threadpool(load_state, mid))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        hub.start()
        try:
            yield
        finally:
            await hub.stop()

    app = FastAPI(
        title="Level 10 Meeting API",
        version="1.0.0",
        description="Scorecard, Rocks, To-Dos, Issues and Level 10 meetings. See docs/ARCHITECTURE.md.",
        lifespan=lifespan,
    )
    app.state.clocks = clocks
    app.state.hub = hub
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    api = APIRouter(prefix="/api")
    api.include_router(identity.router)
    api.include_router(team.router)
    api.include_router(meetings.team_router)
    api.include_router(meetings.router)

    @api.get("/health", tags=["ops"], summary="Liveness and database connectivity")
    def health() -> dict[str, str]:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "now": settings.app_now.isoformat().replace("+00:00", "Z")}

    if settings.enable_test_endpoints:
        assert_safe_database(settings.database_url)

        @api.post("/__test__/reset", tags=["test-only"], summary="Reset and reseed the isolated test database")
        def reset() -> dict[str, str]:
            with get_sessionmaker()() as session:
                reset_and_seed(session, settings.database_url)
            return {"status": "reset"}

    app.include_router(api)
    return app


app = create_app()
