"""
CallPilot — Event Broadcasting System
=======================================
Real-time event broadcasting for the frontend StatusTerminal.

Uses asyncio queues to fan-out events to all connected SSE clients.
Any part of the backend can call `emit(...)` to push a log entry
to every connected frontend.

ARCHITECTURE:
  ┌────────────┐     emit()     ┌───────────────┐     SSE      ┌──────────┐
  │  Swarm /   │ ──────────────▶│  EventManager  │ ──────────▶│ Frontend │
  │  Tools     │                │  (fan-out)     │             │ Terminal │
  └────────────┘                └───────────────┘             └──────────┘
"""

import asyncio
import json
import time
import logging
from typing import AsyncGenerator

logger = logging.getLogger("callpilot.events")

# ── Global Event Manager ─────────────────────────────────


class EventManager:
    """Fan-out event broadcaster for SSE clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        logger.info(f"[EVENTS] New subscriber ({len(self._subscribers)} total)")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber queue."""
        if q in self._subscribers:
            self._subscribers.remove(q)
        logger.info(f"[EVENTS] Subscriber left ({len(self._subscribers)} total)")

    def emit(
        self,
        message: str,
        log_type: str = "info",
        source: str = "system",
    ):
        """
        Push an event to all subscribers.

        Args:
            message: Human-readable log message
            log_type: One of 'info', 'success', 'warning', 'error', 'system'
            source: Origin label ('swarm', 'calendar', 'call', 'agent', 'system')
        """
        event = {
            "timestamp": time.strftime("%H:%M:%S"),
            "type": log_type,
            "message": message,
            "source": source,
        }
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        # Clean up dead subscribers
        for q in dead:
            self._subscribers.remove(q)

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted events from a subscriber queue."""
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            # Send keepalive comment
            yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return


# Singleton
event_manager = EventManager()


def emit(message: str, log_type: str = "info", source: str = "system"):
    """Convenience shortcut — call from anywhere in the backend."""
    event_manager.emit(message, log_type, source)
