import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("callpilot.calls")

ACTIVE_CALLS: dict = {}


def _generate_call_sid() -> str:
    return f"SIM_{uuid.uuid4().hex[:12]}"


def _generate_simulated_slots(date: str, count: int = 4) -> list[str]:
    """Generate realistic simulated appointment slots for a given date."""
    try:
        base = datetime.strptime(date, "%Y-%m-%d")
    except (ValueError, TypeError):
        base = datetime.now() + timedelta(days=1)
        base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    possible_hours = [9, 10, 11, 12, 13, 14, 15, 16]
    possible_minutes = [0, 30]

    all_times = []
    for h in possible_hours:
        for m in possible_minutes:
            all_times.append((h, m))

    selected = random.sample(all_times, min(count, len(all_times)))
    selected.sort()

    slots = []
    for h, m in selected:
        slot_dt = base.replace(hour=h, minute=m, second=0, microsecond=0)
        slots.append(slot_dt.isoformat())

    return slots


def _simulate_call_lifecycle(call_sid: str) -> None:
    stages = ["initiated", "ringing", "in-progress", "completed"]
    for stage in stages:
        if call_sid in ACTIVE_CALLS:
            ACTIVE_CALLS[call_sid]["status"] = stage
            logger.info(f"[SIM] Call {call_sid[:16]}... status -> {stage}")
        time.sleep(0.3)


def _build_inquiry_transcript(
    provider_name: str,
    patient_name: str,
    service_type: str,
    date: str,
    slot_times: list[str],
) -> list[dict]:
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
            "text": f"Hi, this is {provider_name}. Let me check our schedule for {date}.",
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
            "text": f"That's great. I'll pass those options along to {patient_name}. Thank you for your time!",
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
                f"Yes, I can confirm {patient_name} is booked for {appointment_time}."
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


def call_to_inquire(
    provider_phone: str,
    provider_name: str,
    date: str,
    service_type: str = "appointment",
    patient_name: str = "CallPilot User",
) -> dict:
    """Simulate calling a provider to ask about available appointment slots."""
    logger.info(f"[INQUIRE] Simulating call to {provider_name} ({provider_phone}) for slots on {date}")

    from app.tools.provider_tool import get_provider_slots
    raw_slots = get_provider_slots(
        provider_phone=provider_phone,
        date=date,
        provider_name=provider_name,
    )

    if not raw_slots:
        logger.info(f"[INQUIRE] No stored slots for {provider_name}. Generating simulated slots.")
        raw_slots = _generate_simulated_slots(date, count=4)

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
    call_sid = _generate_call_sid()

    transcript = _build_inquiry_transcript(
        provider_name=provider_name,
        patient_name=patient_name,
        service_type=service_type,
        date=date,
        slot_times=slot_times,
    )

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
    _simulate_call_lifecycle(call_sid)
    logger.info(f"[SIM] Inquiry call completed: {call_sid}")
    return {"success": True, "call_sid": call_sid, "status": "completed"}


def initiate_call(
    provider_phone: str,
    provider_name: str,
    appointment_time: str,
    service_type: str = "appointment",
    patient_name: str = "CallPilot User",
) -> dict:
    """Simulate an outbound phone call to confirm a booked appointment."""
    call_sid = _generate_call_sid()

    transcript = _build_confirmation_transcript(
        provider_name=provider_name,
        patient_name=patient_name,
        service_type=service_type,
        appointment_time=appointment_time,
    )

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


def get_call_status(call_sid: str) -> dict:
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
    if call_sid in ACTIVE_CALLS:
        ACTIVE_CALLS[call_sid]["status"] = status
        logger.info(f"[CALL] Call {call_sid[:16]}... status -> {status}")
