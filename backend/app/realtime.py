"""Server-Sent Events hub fed by PostgreSQL LISTEN/NOTIFY.

Why SSE + REST instead of WebSockets: all meeting traffic is server -> browser (the browser
mutates over normal authenticated REST calls), SSE reconnects automatically, works through
proxies and cookies, and needs no custom protocol. Every connect (and reconnect) begins with a
full authoritative state event, so recovery needs no replay log.

Why LISTEN/NOTIFY: mutations commit to Postgres and ``pg_notify`` fires on commit, so every
backend worker process (each runs this hub) is told about every change regardless of which
worker handled the request. State is never held only in process memory.
"""

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import psycopg
from sqlalchemy.engine import make_url

from app.services.common import NOTIFY_CHANNEL

logger = logging.getLogger("app.realtime")

StateLoader = Callable[[str], Awaitable[dict[str, Any] | None]]
QUEUE_SIZE = 64


@dataclass(eq=False)
class Subscriber:
    """One connected browser."""

    meeting_id: str
    team_id: str
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(QUEUE_SIZE))

    def push(self, message: dict[str, Any]) -> None:
        """Enqueue without blocking; on overflow collapse to a single resync request."""
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait({"event": "resync", "data": {}})


class Hub:
    """Fan-out of database notifications to connected SSE clients in this process.

    A dedicated thread owns the blocking ``LISTEN`` connection (portable across event-loop
    implementations, including Windows' default loop) and hands payloads to the asyncio loop,
    where a single consumer dispatches them in order.
    """

    def __init__(self, database_url: str, load_state: StateLoader) -> None:
        """Create the hub; call :meth:`start` to begin listening."""
        url = make_url(database_url).set(drivername="postgresql")
        self._dsn = url.render_as_string(hide_password=False)
        self._load_state = load_state
        self._subscribers: set[Subscriber] = set()
        self._inbox: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._consumer: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """Start listening (call from within the running event loop)."""
        self._loop = asyncio.get_running_loop()
        self._inbox = asyncio.Queue()
        self._stop.clear()
        self._consumer = asyncio.create_task(self._consume(), name="realtime-dispatch")
        self._thread = threading.Thread(target=self._listen, name="realtime-listener", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        """Stop listening."""
        self._stop.set()
        if self._consumer:
            self._consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer
        if self._thread:
            await asyncio.get_running_loop().run_in_executor(None, self._thread.join, 5)

    def subscribe(self, meeting_id: str, team_id: str) -> Subscriber:
        """Register a client (do this *before* loading its initial state)."""
        sub = Subscriber(meeting_id, team_id)
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        """Remove a client."""
        self._subscribers.discard(sub)

    @property
    def subscriber_count(self) -> int:
        """Number of connected clients (diagnostics/tests)."""
        return len(self._subscribers)

    def _post(self, payload: dict[str, Any] | None) -> None:
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._inbox.put_nowait, payload)

    def _listen(self) -> None:
        while not self._stop.is_set():
            try:
                with psycopg.connect(self._dsn, autocommit=True) as conn:
                    conn.execute(f"LISTEN {NOTIFY_CHANNEL}")
                    self._post(None)  # anything may have happened while we were not listening: resync
                    while not self._stop.is_set():
                        for notification in conn.notifies(timeout=1.0):
                            self._post(json.loads(notification.payload))
            except Exception:
                logger.exception("realtime listener failed; reconnecting")
                self._stop.wait(1)

    async def _consume(self) -> None:
        while True:
            payload = await self._inbox.get()
            try:
                if payload is None:
                    for sub in list(self._subscribers):
                        sub.push({"event": "resync", "data": {}})
                else:
                    await self._dispatch(payload)
            except Exception:
                logger.exception("failed to dispatch realtime event")

    async def _dispatch(self, payload: dict[str, Any]) -> None:
        if payload.get("type") == "meeting":
            targets = [s for s in self._subscribers if s.meeting_id == payload["meeting_id"]]
            if not targets:
                return
            state = await self._load_state(payload["meeting_id"])
            if state is None:
                return
            for sub in targets:
                sub.push({"event": "state", "data": state})
        elif payload.get("type") == "data_changed":
            for sub in list(self._subscribers):
                if sub.team_id == payload["team_id"]:
                    sub.push({"event": "data_changed", "data": {"resource": payload.get("resource")}})
