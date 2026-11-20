"""Clock abstraction.

Two clocks with different jobs:

* ``business`` - the application's "now" used for every business rule and for stamping
  business records (weeks, due dates, overdue, created/solved times). It is read from
  ``APP_NOW`` and is frozen, so results are deterministic and reproducible.
* ``timer`` - real UTC wall time, used only to *measure elapsed time* (meeting section
  timers and meeting start/end instants). A frozen clock cannot measure elapsed time.

Neither clock ever comes from a browser.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Source of the current instant (timezone-aware UTC)."""

    def now(self) -> datetime:
        """Return the current instant."""
        ...


class FrozenClock:
    """Clock that always returns the same instant until advanced explicitly."""

    def __init__(self, instant: datetime) -> None:
        """Freeze at ``instant``."""
        self._instant = instant

    def now(self) -> datetime:
        """Return the frozen instant."""
        return self._instant

    def advance(self, delta: timedelta) -> None:
        """Move the clock forward (tests and demos)."""
        self._instant += delta


class SystemClock:
    """Real wall clock in UTC."""

    def now(self) -> datetime:
        """Return the real current instant."""
        return datetime.now(UTC)


@dataclass
class Clocks:
    """The pair of clocks used by the application."""

    business: Clock
    timer: Clock
