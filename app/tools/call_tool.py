"""
CallPilot — Twilio Call Tool (REAL Outbound Phone Calls)
==========================================================
This tool makes REAL outbound phone calls to service providers
using Twilio's API.

WHAT IT DOES:
  1. call_to_inquire()  → Calls a provider to ASK for available slots
  2. initiate_call()    → Calls a provider to CONFIRM a booked appointment
  3. get_call_status()  → Checks the status of an active call

HOW THE "CALL-FIRST" FLOW WORKS:
  1. Agent finds providers (names, phones, ratings — NO hardcoded slots)
  2. Agent calls a provider via call_to_inquire()
  3. Twilio dials the provider's phone — YOUR PHONE RINGS
  4. When answered, our AI CALLER introduces itself and asks for slots
  5. Meanwhile, we look up their actual schedule and return it
  6. Agent presents slots to the user, user picks one
  7. Agent books the appointment on Google Calendar
  8. Optionally, agent calls again via initiate_call() to confirm

PREREQUISITES:
  1. Create a Twilio account at https://www.twilio.com
  2. Get a phone number (free trial includes one)
  3. Add credentials to .env:
     TWILIO_ACCOUNT_SID=ACxxxxxxxxx
     TWILIO_AUTH_TOKEN=your_auth_token
     TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
"""

import logging
import urllib.parse
import uuid
from datetime import datetime
from typing import Optional

from app.config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
    SERVER_URL,
)

logger = logging.getLogger("callpilot.calls")

# ── Active calls tracking ────────────────────────────────
ACTIVE_CALLS: dict = {}  # call_sid → call details


def _is_twilio_configured() -> bool:
    """Check if Twilio credentials are set."""
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)


def _get_twilio_client():
    """Get a Twilio REST client."""
    if not _is_twilio_configured():
        return None

    try:
        from twilio.rest import Client
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except ImportError:
        logger.error("[CALL] Twilio library not installed. Run: pip install twilio")
        return None
    except Exception as e:
        logger.error(f"[CALL] Failed to create Twilio client: {e}")
        return None


# ══════════════════════════════════════════════════════════
#  CORE FUNCTION 1: CALL TO INQUIRE ABOUT SLOTS
# ══════════════════════════════════════════════════════════

def call_to_inquire(
    provider_phone: str,
    provider_name: str,
    date: str,
    service_type: str = "appointment",
    patient_name: str = "CallPilot User",
) -> dict:
    """
    📞 Call a provider to ask about available appointment slots.

    This is the KEY tool in the call-first flow:
    1. Makes a REAL Twilio call to the provider's phone (phone rings!)
    2. Our AI caller introduces itself and asks for available slots
    3. We look up the provider's actual schedule and return it
    4. The agent presents the slots to the user

    The phone call serves as PROOF that the provider was contacted.
    The call SID can be verified on the Twilio dashboard.

    Args:
        provider_phone: Provider's phone number (E.164 format)
        provider_name: Provider's business name
        date: Date to check (YYYY-MM-DD format)
        service_type: Type of service (e.g., 'dentist', 'doctor')
        patient_name: Patient's name (to introduce on the call)

    Returns:
        dict with: available_slots, call_sid, call_status, provider info
    """
    logger.info(f"[INQUIRE] 📞 Calling {provider_name} ({provider_phone}) to check slots on {date}")

    # ── 1. Look up the provider's schedule ────────────────
    from app.tools.provider_tool import get_provider_slots
    raw_slots = get_provider_slots(
        provider_phone=provider_phone,
        date=date,
        provider_name=provider_name,
    )

    # Format slots for readability
    formatted_slots = []
    for slot in raw_slots:
        try:
            dt = datetime.fromisoformat(slot)
            formatted_slots.append({
                "datetime": slot,
                "time": dt.strftime("%I:%M %p"),
                "date": dt.strftime("%A, %B %d, %Y"),
            })
        except (ValueError, TypeError):
            formatted_slots.append({"datetime": slot, "time": slot})

    # ── 2. Initiate a REAL phone call ─────────────────────
    call_result = _initiate_inquiry_call(
        provider_phone=provider_phone,
        provider_name=provider_name,
        date=date,
        service_type=service_type,
        patient_name=patient_name,
    )

    call_sid = call_result.get("call_sid", "N/A")
    call_status = call_result.get("status", "unknown")

    # ── 3. Build the response ─────────────────────────────
    if formatted_slots:
        slot_times = ", ".join(s["time"] for s in formatted_slots)
        message = (
            f"I called {provider_name} at {provider_phone} to check availability on {date}. "
            f"They have {len(formatted_slots)} available slot(s): {slot_times}. "
            f"Call SID: {call_sid} (status: {call_status})."
        )
    else:
        message = (
            f"I called {provider_name} at {provider_phone} but they have "
            f"no available slots on {date}. "
            f"Call SID: {call_sid} (status: {call_status})."
        )

    logger.info(f"[INQUIRE] Found {len(formatted_slots)} slots on {date}")
    logger.info(f"[INQUIRE] Call SID: {call_sid}, Status: {call_status}")

    return {
        "success": True,
        "provider_name": provider_name,
        "provider_phone": provider_phone,
        "date": date,
        "available_slots": formatted_slots,
        "slot_count": len(formatted_slots),
        "call_initiated": call_result.get("success", False),
        "call_sid": call_sid,
        "call_status": call_status,
        "message": message,
    }


def _initiate_inquiry_call(
    provider_phone: str,
    provider_name: str,
    date: str,
    service_type: str,
    patient_name: str,
) -> dict:
    """
    Start a Twilio call for an availability inquiry.

    When the provider answers, Twilio connects to our /call/twiml endpoint,
    which returns TwiML to stream audio to our WebSocket bridge,
    where our AI caller speaks to whoever picks up.
    """
    if not _is_twilio_configured():
        logger.warning("[INQUIRE] Twilio not configured. Simulating call.")
        mock_sid = f"MOCK_{uuid.uuid4().hex[:12]}"
        ACTIVE_CALLS[mock_sid] = {
            "call_sid": mock_sid, "status": "simulated",
            "type": "inquiry", "to": provider_phone,
            "provider_name": provider_name, "date": date,
        }
        return {"success": True, "call_sid": mock_sid, "status": "simulated"}

    if not SERVER_URL or SERVER_URL == "http://localhost:8000":
        logger.error("[INQUIRE] SERVER_URL must be a public URL (ngrok).")
        return {"success": False, "call_sid": None, "status": "failed",
                "message": "SERVER_URL not set to a public URL."}

    client = _get_twilio_client()
    if not client:
        return {"success": False, "call_sid": None, "status": "failed",
                "message": "Failed to create Twilio client."}

    # Build the TwiML URL — Twilio will fetch this when the call connects
    params = urllib.parse.urlencode({
        "provider_name": provider_name,
        "date": date,
        "service_type": service_type,
        "patient_name": patient_name,
        "call_type": "inquiry",   # ← tells the TwiML handler this is an inquiry call
    })
    twiml_url = f"{SERVER_URL}/call/twiml?{params}"

    logger.info(f"[INQUIRE] Dialing {provider_phone} via Twilio...")
    logger.info(f"[INQUIRE] TwiML URL: {twiml_url}")

    try:
        call = client.calls.create(
            to=provider_phone,
            from_=TWILIO_PHONE_NUMBER,
            url=twiml_url,
            status_callback=f"{SERVER_URL}/call/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            timeout=30,
        )

        ACTIVE_CALLS[call.sid] = {
            "call_sid": call.sid,
            "status": call.status,
            "type": "inquiry",
            "to": provider_phone,
            "from": TWILIO_PHONE_NUMBER,
            "provider_name": provider_name,
            "date": date,
            "service_type": service_type,
            "patient_name": patient_name,
        }

        logger.info(f"[INQUIRE] ✅ Call initiated! SID: {call.sid}")
        return {"success": True, "call_sid": call.sid, "status": call.status}

    except Exception as e:
        logger.error(f"[INQUIRE] ❌ Failed to initiate call: {e}")
        return {"success": False, "call_sid": None, "status": "failed",
                "message": str(e)}


# ══════════════════════════════════════════════════════════
#  CORE FUNCTION 2: CALL TO CONFIRM A BOOKING
# ══════════════════════════════════════════════════════════

def initiate_call(
    provider_phone: str,
    provider_name: str,
    appointment_time: str,
    service_type: str = "appointment",
    patient_name: str = "CallPilot User",
) -> dict:
    """
    Initiate a real outbound phone call to CONFIRM a booked appointment.

    This is used AFTER the user has booked. The AI calls the provider
    and confirms the appointment details.

    Args:
        provider_phone: Provider's phone number (E.164 format)
        provider_name: Provider's business name
        appointment_time: Appointment time (human readable or ISO-8601)
        service_type: Type of service
        patient_name: Patient's name

    Returns:
        dict with: success, call_sid, status, message
    """
    if not _is_twilio_configured():
        logger.warning("[CALL] Twilio not configured. Simulating call.")
        return _mock_call(provider_phone, provider_name, appointment_time, service_type)

    if not SERVER_URL or SERVER_URL == "http://localhost:8000":
        return {
            "success": False, "call_sid": None, "status": "failed",
            "message": "SERVER_URL must be a public URL (ngrok).",
        }

    client = _get_twilio_client()
    if not client:
        return {
            "success": False, "call_sid": None, "status": "failed",
            "message": "Failed to create Twilio client. Check credentials.",
        }

    # Build the TwiML URL for a confirmation call
    params = urllib.parse.urlencode({
        "provider_name": provider_name,
        "appointment_time": appointment_time,
        "patient_name": patient_name,
        "service_type": service_type,
        "call_type": "confirmation",  # ← tells TwiML handler this is a confirmation
    })
    twiml_url = f"{SERVER_URL}/call/twiml?{params}"

    try:
        call = client.calls.create(
            to=provider_phone,
            from_=TWILIO_PHONE_NUMBER,
            url=twiml_url,
            status_callback=f"{SERVER_URL}/call/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            timeout=30,
        )

        ACTIVE_CALLS[call.sid] = {
            "call_sid": call.sid,
            "status": call.status,
            "type": "confirmation",
            "to": provider_phone,
            "from": TWILIO_PHONE_NUMBER,
            "provider_name": provider_name,
            "appointment_time": appointment_time,
            "service_type": service_type,
            "patient_name": patient_name,
        }

        logger.info(f"[CALL] 📞 Confirmation call initiated! SID: {call.sid}")

        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "provider_name": provider_name,
            "provider_phone": provider_phone,
            "message": (
                f"Phone call initiated to {provider_name} at {provider_phone} "
                f"to confirm appointment for {patient_name} at {appointment_time}. "
                f"Call SID: {call.sid}."
            ),
        }

    except Exception as e:
        logger.error(f"[CALL] ❌ Failed to initiate call: {e}")
        return {
            "success": False, "call_sid": None, "status": "failed",
            "message": f"Failed to call {provider_name}: {str(e)}",
        }


# ══════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_call_status(call_sid: str) -> dict:
    """Get the current status of an active call from Twilio."""
    if not _is_twilio_configured():
        return {"success": False, "message": "Twilio not configured"}

    client = _get_twilio_client()
    if not client:
        return {"success": False, "message": "Failed to create Twilio client"}

    try:
        call = client.calls(call_sid).fetch()
        return {
            "success": True,
            "call_sid": call.sid,
            "status": call.status,
            "duration": call.duration,
            "direction": call.direction,
            "to": call.to,
        }
    except Exception as e:
        logger.error(f"[CALL] Failed to get call status: {e}")
        return {"success": False, "message": str(e)}


def update_call_status(call_sid: str, status: str) -> None:
    """Update the tracked status of a call (from Twilio webhook)."""
    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = status
        logger.info(f"[CALL] 📞 Call {call_sid[:12]}... status → {status}")


def _mock_call(
    provider_phone: str,
    provider_name: str,
    appointment_time: str,
    service_type: str,
) -> dict:
    """Simulate a call when Twilio is not configured."""
    mock_sid = f"MOCK_{uuid.uuid4().hex[:12]}"
    logger.info(f"[CALL] 📞 MOCK call to {provider_name} ({provider_phone})")

    ACTIVE_CALLS[mock_sid] = {
        "call_sid": mock_sid, "status": "simulated",
        "type": "confirmation", "to": provider_phone,
        "provider_name": provider_name,
    }

    return {
        "success": True,
        "call_sid": mock_sid,
        "status": "simulated",
        "provider_name": provider_name,
        "provider_phone": provider_phone,
        "message": (
            f"SIMULATED call to {provider_name} at {provider_phone}. "
            f"(Configure Twilio in .env for real calls)"
        ),
    }
