import asyncio
import json
import time
import logging
from typing import AsyncGenerator

logger = logging.getLogger("callpilot.events")


class EventManager:
    """Fan-out event broadcaster for SSE clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        logger.info(f"[EVENTS] New subscriber ({len(self._subscribers)} total)")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)
        logger.info(f"[EVENTS] Subscriber left ({len(self._subscribers)} total)")

    def emit(self, message: str, log_type: str = "info", source: str = "system"):
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
        for q in dead:
            self._subscribers.remove(q)

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
        except asyncio.CancelledError:
            return


event_manager = EventManager()


def emit(message: str, log_type: str = "info", source: str = "system"):
    event_manager.emit(message, log_type, source)
