"""
CallPilot — Call Routes (Simulated Outbound Calls)
=====================================================
FastAPI routes for simulated phone calls to service providers.
Calls are handled in-memory without any Twilio dependency.

CALL FLOW (Simulated Call-First Architecture):
  1. Agent finds providers (no hardcoded slots)
  2. Agent calls provider via /tools/call-to-inquire
  3. Call is simulated (initiated → ringing → in-progress → completed)
  4. Provider's schedule is looked up and returned as available slots
  5. A realistic transcript of the AI-provider conversation is generated
  6. The user sees the slots and picks one
  7. After booking, agent optionally calls again to confirm

ENDPOINTS:
  POST /call/outbound          → Simulate an outbound call to a provider
  POST /call/twiml             → Legacy endpoint (returns simulation notice)
  WS   /call/media-stream      → Legacy endpoint (closes immediately)
  POST /call/status            → Status update webhook (for compatibility)
  GET  /call/active            → List active/recent calls
  GET  /call/status/{call_sid} → Get specific call status from in-memory tracking
"""

import logging

from fastapi import APIRouter, Query, Request, Response, WebSocket
from pydantic import BaseModel, Field

from app.tools.call_tool import ACTIVE_CALLS, initiate_call

logger = logging.getLogger("callpilot.routes.call")


# ── Router ───────────────────────────────────────────────
router = APIRouter(prefix="/call", tags=["Phone Calls (Simulated)"])


# ── Integration Status ──────────────────────────────────
CALL_INTEGRATION_STATUS = "Simulated (no Twilio)"


# ── Request Models ───────────────────────────────────────

class CallOutboundRequest(BaseModel):
    """Request to initiate a phone call to a provider."""
    provider_phone: str = Field(description="Provider's phone number (E.164: +XXXXXXXXXXX)")
    provider_name: str = Field(description="Provider's business name")
    appointment_time: str = Field(description="Appointment time (human-readable)")
    service_type: str = Field(default="appointment", description="Type of service")
    patient_name: str = Field(default="CallPilot User", description="Patient name")


# ════════════════════════════════════════════════════════
#  CORE ENDPOINTS
# ════════════════════════════════════════════════════════


@router.post("/outbound")
async def call_outbound(request: CallOutboundRequest):
    """
    Simulate an outbound phone call to a provider.

    The call is simulated in-memory with a realistic lifecycle
    and a generated transcript of the AI-provider conversation.
    """
    logger.info(f"[CALL] Simulating outbound call to {request.provider_name} at {request.provider_phone}...")

    result = initiate_call(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        appointment_time=request.appointment_time,
        service_type=request.service_type,
        patient_name=request.patient_name,
    )

    if result.get("success"):
        logger.info(f"[CALL] Simulated call completed: {result['call_sid']}")
    else:
        logger.warning(f"[CALL] Simulated call issue: {result.get('message')}")

    return result


@router.post("/twiml")
async def twiml_webhook(
    request: Request,
    provider_name: str = Query("the clinic"),
    appointment_time: str = Query(""),
    patient_name: str = Query("the patient"),
    service_type: str = Query("appointment"),
    date: str = Query(""),
    call_type: str = Query("inquiry"),
):
    """
    Legacy TwiML endpoint — returns a simulation notice.

    This endpoint previously returned TwiML for Twilio.
    Now returns a simple notice that calls are simulated.
    """
    logger.info(f"[TWIML] Legacy endpoint hit for {provider_name} ({call_type}) — calls are simulated")
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Say>Calls are currently simulated. No live connection.</Say></Response>'
        ),
        media_type="application/xml",
    )


@router.websocket("/media-stream")
async def media_stream_websocket(
    websocket: WebSocket,
    provider_name: str = Query("the clinic"),
    appointment_time: str = Query(""),
    patient_name: str = Query("the patient"),
    service_type: str = Query("appointment"),
    date: str = Query(""),
    call_type: str = Query("inquiry"),
):
    """
    Legacy WebSocket endpoint — immediately closes.

    This endpoint previously bridged Twilio audio to ElevenLabs.
    Now closes immediately since calls are simulated.
    """
    await websocket.accept()
    logger.info(f"[MEDIA STREAM] Legacy WebSocket hit for {provider_name} — calls are simulated, closing.")
    await websocket.close(code=1000, reason="Calls are simulated. No media stream needed.")


@router.post("/status")
async def call_status_webhook(request: Request):
    """
    Status callback webhook (kept for compatibility).

    Accepts status updates and updates in-memory call tracking.
    """
    form_data = await request.form()

    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    duration = form_data.get("CallDuration", "0")

    logger.info(f"[CALL STATUS] Call {call_sid[:16]}... -> {call_status} (duration: {duration}s)")

    # Update tracking
    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = call_status
        if duration != "0":
            ACTIVE_CALLS[call_sid]["duration"] = duration

    return {"status": "received"}


@router.get("/active")
async def list_active_calls():
    """List all active and recent calls (from in-memory tracking)."""
    return {
        "calls": list(ACTIVE_CALLS.values()),
        "total": len(ACTIVE_CALLS),
        "mode": "simulated",
    }


@router.get("/status/{call_sid}")
async def get_single_call_status(call_sid: str):
    """Get the current status of a specific call from in-memory tracking."""
    if call_sid in ACTIVE_CALLS:
        call = ACTIVE_CALLS[call_sid]
        return {
            "success": True,
            "call_sid": call_sid,
            "status": call.get("status", "unknown"),
            "duration": call.get("duration", "0"),
            "to": call.get("to", ""),
            "from_": call.get("from", "+1-CALLPILOT"),
            "simulated": True,
        }

    return {
        "success": False,
        "message": f"Call {call_sid} not found in active calls.",
    }
