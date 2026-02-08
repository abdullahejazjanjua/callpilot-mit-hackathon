"""
CallPilot — Simulated Call Tool
=================================
This tool SIMULATES outbound phone calls to service providers.
No Twilio dependency — calls are simulated in-memory with realistic
status progression, transcripts, and the same API contract.

WHAT IT DOES:
  1. call_to_inquire()  → Simulates calling a provider to ASK for available slots
  2. initiate_call()    → Simulates calling a provider to CONFIRM a booked appointment
  3. get_call_status()  → Checks the status of a simulated call

HOW THE SIMULATED "CALL-FIRST" FLOW WORKS:
  1. Agent finds providers (names, phones, ratings)
  2. Agent calls a provider via call_to_inquire()
  3. We simulate the call lifecycle (initiated → ringing → answered → completed)
  4. We look up the provider's actual schedule and return the slots
  5. A realistic transcript is generated showing the AI–provider conversation
  6. Agent presents slots to the user, user picks one
  7. Agent books the appointment on Google Calendar
  8. Optionally, agent calls again via initiate_call() to confirm
"""

import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("callpilot.calls")

# ── Active calls tracking ────────────────────────────────
ACTIVE_CALLS: dict = {}  # call_sid → call details


def _generate_call_sid() -> str:
    """Generate a realistic simulated call SID."""
    return f"SIM_{uuid.uuid4().hex[:12]}"


def _generate_simulated_slots(date: str, count: int = 4) -> list[str]:
    """
    Generate realistic simulated appointment slots for a given date.

    Used when a provider (e.g. from Mapbox) has no slot data in providers.json.
    Returns ISO-8601 datetime strings for business-hours slots.
    """
    try:
        base = datetime.strptime(date, "%Y-%m-%d")
    except (ValueError, TypeError):
        base = datetime.now() + timedelta(days=1)
        base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    # Possible appointment times during business hours (9 AM - 5 PM)
    possible_hours = [9, 10, 11, 12, 13, 14, 15, 16]
    possible_minutes = [0, 30]

    all_times = []
    for h in possible_hours:
        for m in possible_minutes:
            all_times.append((h, m))

    # Pick a random subset
    selected = random.sample(all_times, min(count, len(all_times)))
    selected.sort()

    slots = []
    for h, m in selected:
        slot_dt = base.replace(hour=h, minute=m, second=0, microsecond=0)
        slots.append(slot_dt.isoformat())

    return slots


def _simulate_call_lifecycle(call_sid: str) -> None:
    """
    Simulate a call going through its lifecycle stages.
    Updates ACTIVE_CALLS status as it progresses.
    """
    stages = ["initiated", "ringing", "in-progress", "completed"]
    for stage in stages:
        if call_sid in ACTIVE_CALLS:
            ACTIVE_CALLS[call_sid]["status"] = stage
            logger.info(f"[SIM] Call {call_sid[:16]}... status → {stage}")
        time.sleep(0.3)  # Brief delay between stages


def _build_inquiry_transcript(
    provider_name: str,
    patient_name: str,
    service_type: str,
    date: str,
    slot_times: list[str],
) -> list[dict]:
    """Build a realistic simulated transcript for an inquiry call."""
    transcript = [
        {
            "role": "agent",
            "text": (
                f"Hello, I'm calling from CallPilot, an AI scheduling assistant. "
                f"I'm calling on behalf of {patient_name} who would like to schedule "
                f"a {service_type.replace('_', ' ')} appointment on {date}. "
                f"Could you tell me your available appointment slots?"
            ),
        },
        {
            "role": "provider",
            "text": (
                f"Hi, this is {provider_name}. Let me check our schedule for {date}."
            ),
        },
    ]

    if slot_times:
        slots_str = ", ".join(slot_times)
        transcript.append({
            "role": "provider",
            "text": f"We have the following slots available: {slots_str}.",
        })
        transcript.append({
            "role": "agent",
            "text": (
                f"That's great. I'll pass those options along to {patient_name}. "
                f"Thank you for your time!"
            ),
        })
        transcript.append({
            "role": "provider",
            "text": "You're welcome. We look forward to seeing them!",
        })
    else:
        transcript.append({
            "role": "provider",
            "text": f"I'm sorry, we don't have any openings on {date}.",
        })
        transcript.append({
            "role": "agent",
            "text": "I understand. Thank you for checking. Goodbye!",
        })

    return transcript


def _build_confirmation_transcript(
    provider_name: str,
    patient_name: str,
    service_type: str,
    appointment_time: str,
) -> list[dict]:
    """Build a realistic simulated transcript for a confirmation call."""
    return [
        {
            "role": "agent",
            "text": (
                f"Hello, I'm calling from CallPilot, an AI scheduling assistant. "
                f"I'm calling to confirm an appointment for {patient_name} "
                f"at {appointment_time} for a {service_type.replace('_', ' ')} visit. "
                f"Can you confirm this is booked?"
            ),
        },
        {
            "role": "provider",
            "text": (
                f"Hi, this is {provider_name}. Let me verify that... "
                f"Yes, I can confirm {patient_name} is booked for "
                f"{appointment_time}."
            ),
        },
        {
            "role": "agent",
            "text": "Wonderful, thank you for confirming. Have a great day!",
        },
        {
            "role": "provider",
            "text": "Thank you, goodbye!",
        },
    ]


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
    Simulate calling a provider to ask about available appointment slots.

    This is the KEY tool in the call-first flow:
    1. Simulates a phone call to the provider
    2. Looks up the provider's actual schedule
    3. Returns available slots with a simulated transcript
    4. The agent presents the slots to the user

    Args:
        provider_phone: Provider's phone number (E.164 format)
        provider_name: Provider's business name
        date: Date to check (YYYY-MM-DD format)
        service_type: Type of service (e.g., 'dentist', 'doctor')
        patient_name: Patient's name

    Returns:
        dict with: available_slots, call_sid, call_status, provider info
    """
    logger.info(f"[INQUIRE] Simulating call to {provider_name} ({provider_phone}) for slots on {date}")

    # ── 1. Look up the provider's schedule ────────────────
    from app.tools.provider_tool import get_provider_slots
    raw_slots = get_provider_slots(
        provider_phone=provider_phone,
        date=date,
        provider_name=provider_name,
    )

    # If no slots found (e.g. Mapbox provider not in JSON), generate simulated ones
    if not raw_slots:
        logger.info(f"[INQUIRE] No stored slots for {provider_name}. Generating simulated slots.")
        raw_slots = _generate_simulated_slots(date, count=4)

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

    # ── 2. Simulate the phone call ────────────────────────
    call_result = _simulate_inquiry_call(
        provider_phone=provider_phone,
        provider_name=provider_name,
        date=date,
        service_type=service_type,
        patient_name=patient_name,
        slot_times=[s["time"] for s in formatted_slots],
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


def _simulate_inquiry_call(
    provider_phone: str,
    provider_name: str,
    date: str,
    service_type: str,
    patient_name: str,
    slot_times: list[str],
) -> dict:
    """
    Simulate an inquiry call with lifecycle progression and transcript.
    """
    call_sid = _generate_call_sid()

    # Build simulated transcript
    transcript = _build_inquiry_transcript(
        provider_name=provider_name,
        patient_name=patient_name,
        service_type=service_type,
        date=date,
        slot_times=slot_times,
    )

    # Track the call
    ACTIVE_CALLS[call_sid] = {
        "call_sid": call_sid,
        "status": "initiated",
        "type": "inquiry",
        "to": provider_phone,
        "from": "+1-CALLPILOT",
        "provider_name": provider_name,
        "date": date,
        "service_type": service_type,
        "patient_name": patient_name,
        "transcript": transcript,
        "duration": "15",
        "simulated": True,
    }

    logger.info(f"[SIM] Simulating inquiry call to {provider_name}...")

    # Simulate call lifecycle
    _simulate_call_lifecycle(call_sid)

    logger.info(f"[SIM] Inquiry call completed: {call_sid}")
    return {"success": True, "call_sid": call_sid, "status": "completed"}


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
    Simulate an outbound phone call to CONFIRM a booked appointment.

    This is used AFTER the user has booked. The simulated AI calls
    the provider and confirms the appointment details.

    Args:
        provider_phone: Provider's phone number (E.164 format)
        provider_name: Provider's business name
        appointment_time: Appointment time (human readable or ISO-8601)
        service_type: Type of service
        patient_name: Patient's name

    Returns:
        dict with: success, call_sid, status, message
    """
    call_sid = _generate_call_sid()

    # Build simulated transcript
    transcript = _build_confirmation_transcript(
        provider_name=provider_name,
        patient_name=patient_name,
        service_type=service_type,
        appointment_time=appointment_time,
    )

    # Track the call
    ACTIVE_CALLS[call_sid] = {
        "call_sid": call_sid,
        "status": "initiated",
        "type": "confirmation",
        "to": provider_phone,
        "from": "+1-CALLPILOT",
        "provider_name": provider_name,
        "appointment_time": appointment_time,
        "service_type": service_type,
        "patient_name": patient_name,
        "transcript": transcript,
        "duration": "12",
        "simulated": True,
    }

    logger.info(f"[SIM] Simulating confirmation call to {provider_name}...")

    # Simulate call lifecycle
    _simulate_call_lifecycle(call_sid)

    logger.info(f"[SIM] Confirmation call completed: {call_sid}")

    return {
        "success": True,
        "call_sid": call_sid,
        "status": "completed",
        "provider_name": provider_name,
        "provider_phone": provider_phone,
        "message": (
            f"Phone call completed to {provider_name} at {provider_phone} "
            f"to confirm appointment for {patient_name} at {appointment_time}. "
            f"The provider confirmed the booking. Call SID: {call_sid}."
        ),
    }


# ══════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_call_status(call_sid: str) -> dict:
    """Get the current status of a call from in-memory tracking."""
    if call_sid in ACTIVE_CALLS:
        call = ACTIVE_CALLS[call_sid]
        return {
            "success": True,
            "call_sid": call_sid,
            "status": call.get("status", "unknown"),
            "duration": call.get("duration", "0"),
            "direction": "outbound",
            "to": call.get("to", ""),
            "simulated": True,
        }

    return {
        "success": False,
        "message": f"Call {call_sid} not found in active calls.",
    }


def update_call_status(call_sid: str, status: str) -> None:
    """Update the tracked status of a call."""
    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = status
        logger.info(f"[CALL] Call {call_sid[:16]}... status -> {status}")
