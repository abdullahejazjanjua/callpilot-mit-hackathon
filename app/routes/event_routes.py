"""
CallPilot — Event Stream Routes (SSE)
=======================================
Server-Sent Events endpoint for real-time frontend updates.

The frontend StatusTerminal connects to /events/stream and receives
live log entries as they happen in the backend.

ENDPOINT:
  GET /events/stream → SSE stream of log events
"""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.events import event_manager

logger = logging.getLogger("callpilot.events")

router = APIRouter(prefix="/events", tags=["Events (SSE)"])


@router.get("/stream")
async def event_stream(request: Request):
    """
    SSE endpoint — streams real-time log events to the frontend.

    Connect with EventSource:
        const es = new EventSource('http://localhost:8000/events/stream');
        es.onmessage = (e) => console.log(JSON.parse(e.data));

    Each event is JSON:
        { "timestamp": "14:32:01", "type": "info", "message": "...", "source": "swarm" }
    """
    q = event_manager.subscribe()

    async def generate():
        import json
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except (asyncio.CancelledError, GeneratorExit):
                    break
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            event_manager.unsubscribe(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
