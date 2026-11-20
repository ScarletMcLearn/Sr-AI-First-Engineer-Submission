"""Common route dependencies."""

from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.clock import Clocks
from app.db import get_session
from app.services.common import company_timezone

Db = Annotated[Session, Depends(get_session)]


def get_clocks(request: Request) -> Clocks:
    """The application's clocks (replaceable in tests via ``app.state.clocks``)."""
    clocks: Clocks = request.app.state.clocks
    return clocks


Clk = Annotated[Clocks, Depends(get_clocks)]


def get_tz(session: Db) -> ZoneInfo:
    """Company time zone."""
    return company_timezone(session)


Tz = Annotated[ZoneInfo, Depends(get_tz)]
