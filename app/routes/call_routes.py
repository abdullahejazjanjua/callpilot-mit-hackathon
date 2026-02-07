"""
CallPilot — Call Routes (Twilio Outbound Calls with AI Caller)
================================================================
FastAPI routes for phone calls via Twilio, connected to an ElevenLabs
AI caller through a real-time WebSocket bridge.

CALL FLOW (Call-First Architecture):
  1. Agent finds providers (no hardcoded slots)
  2. Agent calls provider via /tools/call-to-inquire
  3. Twilio dials the provider's phone — it RINGS
  4. When answered, Twilio fetches TwiML from /call/twiml
  5. TwiML streams audio to /call/media-stream via WebSocket
  6. Our AI CALLER introduces itself and asks about available slots
  7. Slots are returned to the agent (from the provider's schedule)
  8. The user sees the slots and picks one
  9. After booking, agent optionally calls again to confirm

ENDPOINTS:
  POST /call/outbound          → Initiate an outbound call to a provider
  POST /call/twiml             → Twilio fetches this when call is answered
  WS   /call/media-stream      → WebSocket bridge (Twilio ↔ ElevenLabs)
  POST /call/status            → Twilio status callback webhook
  GET  /call/active            → List active/recent calls
  GET  /call/status/{call_sid} → Get specific call status
"""

import logging
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Query, Request, Response, WebSocket
from pydantic import BaseModel, Field

from app.config import (
    ELEVENLABS_RECEPTIONIST_AGENT_ID,
    SERVER_URL,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
)
from app.tools.twilio_bridge import bridge_twilio_to_elevenlabs

logger = logging.getLogger("callpilot.routes.call")


# ── Router ───────────────────────────────────────────────
router = APIRouter(prefix="/call", tags=["📞 Phone Calls"])


# ── In-memory call tracking ─────────────────────────────
ACTIVE_CALLS: dict = {}  # call_sid → call details


# ── Integration Status ──────────────────────────────────
def get_call_integration_status() -> str:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return "❌ Twilio not configured"
    if not ELEVENLABS_RECEPTIONIST_AGENT_ID:
        return "⚠️ Twilio OK, but receptionist agent not created"
    return "✅ REAL (Twilio + AI Receptionist)"


CALL_INTEGRATION_STATUS = get_call_integration_status()


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
    Initiate an outbound phone call to a provider.

    Twilio dials the provider. When they answer, our AI caller
    introduces itself and communicates with whoever picks up.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "call_sid": None,
            "status": "failed",
            "message": "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in .env",
        }

    if not ELEVENLABS_RECEPTIONIST_AGENT_ID:
        return {
            "success": False,
            "call_sid": None,
            "status": "failed",
            "message": "Caller agent not created. Run: python setup_receptionist.py",
        }

    if not SERVER_URL or SERVER_URL == "http://localhost:8000":
        return {
            "success": False,
            "call_sid": None,
            "status": "failed",
            "message": "SERVER_URL must be a public URL (ngrok). Twilio can't reach localhost.",
        }

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as e:
        return {
            "success": False,
            "call_sid": None,
            "status": "failed",
            "message": f"Failed to create Twilio client: {e}",
        }

    # Build TwiML URL with query parameters for context
    params = urllib.parse.urlencode({
        "provider_name": request.provider_name,
        "appointment_time": request.appointment_time,
        "patient_name": request.patient_name,
        "service_type": request.service_type,
    })
    twiml_url = f"{SERVER_URL}/call/twiml?{params}"

    logger.info(f"[CALL] 📞 Calling {request.provider_name} at {request.provider_phone}...")
    logger.info(f"[CALL]    TwiML URL: {twiml_url}")

    try:
        call = client.calls.create(
            to=request.provider_phone,
            from_=TWILIO_PHONE_NUMBER,
            url=twiml_url,
            status_callback=f"{SERVER_URL}/call/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            timeout=30,
        )

        call_info = {
            "call_sid": call.sid,
            "status": call.status,
            "to": request.provider_phone,
            "from": TWILIO_PHONE_NUMBER,
            "provider_name": request.provider_name,
            "appointment_time": request.appointment_time,
            "patient_name": request.patient_name,
        }
        ACTIVE_CALLS[call.sid] = call_info

        logger.info(f"[CALL] ✅ Call initiated! SID: {call.sid}, Status: {call.status}")

        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "provider_name": request.provider_name,
            "provider_phone": request.provider_phone,
            "message": (
                f"Phone call initiated to {request.provider_name} at {request.provider_phone}. "
                f"When they answer, our AI receptionist will confirm the appointment for "
                f"{request.patient_name} at {request.appointment_time}. "
                f"Call SID: {call.sid}."
            ),
        }

    except Exception as e:
        logger.error(f"[CALL] ❌ Failed to initiate call: {e}")
        return {
            "success": False,
            "call_sid": None,
            "status": "failed",
            "message": f"Failed to call {request.provider_name}: {str(e)}",
        }


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
    Twilio webhook — returns TwiML to connect the call to our WebSocket bridge.

    When Twilio calls a provider and they answer, Twilio fetches this endpoint.
    We return TwiML that tells Twilio to stream the call audio to our
    WebSocket endpoint, where our AI CALLER speaks to whoever picks up.

    call_type can be:
      - "inquiry": AI asks about available appointment slots
      - "confirmation": AI confirms an existing booking
    """
    logger.info(f"[TWIML] 📞 Call answered! Connecting AI caller for {provider_name} ({call_type})")

    # Build the WebSocket URL for Twilio to connect to
    ws_server_url = SERVER_URL.replace("https://", "wss://").replace("http://", "ws://")
    params = urllib.parse.urlencode({
        "provider_name": provider_name,
        "appointment_time": appointment_time,
        "patient_name": patient_name,
        "service_type": service_type,
        "date": date,
        "call_type": call_type,
    })
    stream_url = f"{ws_server_url}/call/media-stream?{params}"

    logger.info(f"[TWIML]    Stream URL: {stream_url}")

    # Return TwiML that connects the call to our WebSocket bridge
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        '<Connect>'
        f'<Stream url="{stream_url}" />'
        '</Connect>'
        '</Response>'
    )

    return Response(content=twiml, media_type="application/xml")


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
    WebSocket endpoint for Twilio Media Streams.

    Twilio connects here when a call is active. We bridge the audio
    to an ElevenLabs Conversational AI agent.

    Two modes:
      - "inquiry": Our AI CALLER asks the provider about available slots
      - "confirmation": Our AI CALLER confirms a booked appointment
    """
    await websocket.accept()
    logger.info(f"[MEDIA STREAM] 🔌 Twilio WebSocket connected for {provider_name} ({call_type})")

    if not ELEVENLABS_RECEPTIONIST_AGENT_ID:
        logger.error("[MEDIA STREAM] No caller agent ID configured!")
        await websocket.close()
        return

    # ── Build the appropriate prompt based on call type ────
    if call_type == "inquiry":
        # Get the provider's slots to include in the prompt
        from app.tools.provider_tool import get_provider_slots
        slots = get_provider_slots(
            provider_phone="",  # Can't easily pass phone via WS params
            date=date,
            provider_name=provider_name,
        )
        slots_text = ", ".join(slots[:6]) if slots else "No slots found"

        from app.agents.prompts import CALLER_INQUIRY_PROMPT
        dynamic_prompt = CALLER_INQUIRY_PROMPT.format(
            provider_name=provider_name,
            service_type=service_type.replace("_", " "),
            date=date or "today",
            patient_name=patient_name,
            available_slots=slots_text,
        )
        first_msg = (
            f"Hello, I'm calling from CallPilot, an AI scheduling assistant. "
            f"I'm calling on behalf of {patient_name} who would like to schedule "
            f"a {service_type.replace('_', ' ')} appointment on {date or 'today'}. "
            f"Could you tell me your available appointment slots?"
        )
    else:
        # Confirmation call
        from app.agents.prompts import CALLER_CONFIRMATION_PROMPT
        dynamic_prompt = CALLER_CONFIRMATION_PROMPT.format(
            provider_name=provider_name,
            service_type=service_type.replace("_", " "),
            appointment_time=appointment_time or "the scheduled time",
            patient_name=patient_name,
        )
        first_msg = (
            f"Hello, I'm calling from CallPilot, an AI scheduling assistant. "
            f"I'm calling to confirm an appointment for {patient_name} "
            f"at {appointment_time or 'the scheduled time'} for a "
            f"{service_type.replace('_', ' ')} visit. Can you confirm this is booked?"
        )

    logger.info(f"[MEDIA STREAM] AI Caller prompt ready ({call_type})")

    # Bridge the call
    result = await bridge_twilio_to_elevenlabs(
        twilio_ws=websocket,
        agent_id=ELEVENLABS_RECEPTIONIST_AGENT_ID,
        system_prompt_override=dynamic_prompt,
        first_message=first_msg,
    )

    logger.info(f"[MEDIA STREAM] Call ended. Conversation: {result.get('conversation_id')}")
    logger.info(f"[MEDIA STREAM] Transcript: {result.get('transcript')}")


@router.post("/status")
async def call_status_webhook(request: Request):
    """
    Twilio status callback webhook.

    Twilio sends POST requests here when a call's status changes
    (initiated, ringing, answered, completed, failed, etc.)
    """
    form_data = await request.form()

    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    duration = form_data.get("CallDuration", "0")

    logger.info(f"[CALL STATUS] 📞 Call {call_sid[:12]}... → {call_status} (duration: {duration}s)")

    # Update tracking
    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = call_status
        if duration != "0":
            ACTIVE_CALLS[call_sid]["duration"] = duration

    return {"status": "received"}


@router.get("/active")
async def list_active_calls():
    """List all active and recent calls."""
    return {
        "calls": list(ACTIVE_CALLS.values()),
        "total": len(ACTIVE_CALLS),
    }


@router.get("/status/{call_sid}")
async def get_single_call_status(call_sid: str):
    """Get the current status of a specific call from Twilio."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return {"success": False, "message": "Twilio not configured"}

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        call = client.calls(call_sid).fetch()
        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "duration": call.duration,
            "to": call.to,
            "from_": call.from_,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
