"""
CallPilot — Tool Routes (Webhook Endpoints)
=============================================
These are the FastAPI endpoints that ElevenLabs calls when the
voice agent decides to use a tool during a conversation.

HOW ELEVENLABS WEBHOOK TOOLS WORK:
  ┌─────────────────────────────────────────────────────────┐
  │  1. User says: "I need a dentist"                       │
  │  2. Agent LLM thinks: "I should call find_providers"    │
  │  3. ElevenLabs sends HTTP POST to:                      │
  │     https://your-server.com/tools/find-providers        │
  │     Body: {"category": "dentists"}                      │
  │  4. This endpoint runs find_providers("dentists")       │
  │  5. Returns JSON result to ElevenLabs                   │
  │  6. Agent reads result → speaks: "I found 3 dentists.." │
  └─────────────────────────────────────────────────────────┘

WHY A SEPARATE ROUTER?
  FastAPI "routers" let you organize endpoints into groups.
  All tool endpoints share the /tools prefix, so we group them
  in one file. This keeps main.py clean and makes the API
  structure obvious in the docs.

  Router = mini FastAPI app that gets "included" into the main app.

REQUEST FORMAT:
  ElevenLabs sends tool parameters as a JSON POST body.
  FastAPI automatically parses it using Pydantic models.
  If the body is malformed, FastAPI returns a 422 error
  BEFORE our code runs — free input validation!

LOGGING:
  Every tool call is logged with [TOOL CALL] prefix.
  During a live demo, you can watch the terminal to see
  exactly what the agent is doing in real time.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.calendar_tool import (
    book_appointment,
    check_availability,
    get_busy_slots,
)
from app.tools.distance_tool import calculate_distance
from app.tools.provider_tool import (
    find_available_providers,
    find_providers,
    get_provider_by_id,
)
from app.tools.call_tool import ACTIVE_CALLS

# ── Logger Setup ────────────────────────────────────────────
# We use Python's logging module instead of print() because:
# • Logs include timestamps automatically
# • You can set log levels (DEBUG, INFO, WARNING, ERROR)
# • Logs can be routed to files, monitoring tools, etc.
logger = logging.getLogger("callpilot.tools")

# ── Create the Router ───────────────────────────────────────
# prefix="/tools" means all routes in this file start with /tools
# tags=["Tools"] groups them together in the Swagger docs at /docs
router = APIRouter(
    prefix="/tools",
    tags=["Tools (Webhook Endpoints)"],
)


# ════════════════════════════════════════════════════════════
#  REQUEST MODELS
# ════════════════════════════════════════════════════════════
# These Pydantic models define what ElevenLabs sends in the POST body.
# FastAPI uses them for:
#   1. Automatic JSON parsing
#   2. Input validation (wrong type? missing field? → 422 error)
#   3. Documentation in Swagger UI

class FindProvidersRequest(BaseModel):
    """Body for /tools/find-providers"""
    category: str = Field(description="Service category (e.g., 'dentists')")
    location: Optional[str] = Field(default=None, description="City or address for Places search")
    limit: Optional[int] = Field(default=5, description="Max number of providers to return")


class FindAvailableRequest(BaseModel):
    """Body for /tools/find-available"""
    category: str = Field(description="Service category")
    date: Optional[str] = Field(default=None, description="Date filter (YYYY-MM-DD)")
    min_rating: Optional[float] = Field(default=0.0, description="Minimum rating (1.0-5.0)")
    location: Optional[str] = Field(default=None, description="City or address for Places search")
    limit: Optional[int] = Field(default=5, description="Max number of providers to return")


class ProviderDetailsRequest(BaseModel):
    """Body for /tools/provider-details"""
    provider_id: str = Field(description="Provider's unique ID")


class CheckCalendarRequest(BaseModel):
    """Body for /tools/check-calendar"""
    slot: str = Field(description="Time slot in ISO-8601 format")


class GetBusySlotsRequest(BaseModel):
    """Body for /tools/get-busy-slots"""
    date: str = Field(description="Date in YYYY-MM-DD format")


class BookAppointmentRequest(BaseModel):
    """Body for /tools/book-appointment"""
    provider_id: Optional[str] = Field(default="unknown", description="Provider ID")
    provider_name: str = Field(description="Provider's business name")
    provider_phone: str = Field(description="Provider's phone number")
    provider_address: str = Field(description="Provider's address")
    slot: str = Field(description="Appointment time (ISO-8601)")
    service_type: Optional[str] = Field(default="appointment", description="Service category")
    patient_name: Optional[str] = Field(default="CallPilot User", description="Patient name")


class CalculateDistanceRequest(BaseModel):
    """Body for /tools/calculate-distance"""
    user_location: str = Field(description="User's address")
    provider_address: str = Field(description="Provider's address")
    provider_id: Optional[str] = Field(default="", description="Provider ID")
    provider_name: Optional[str] = Field(default="", description="Provider name")


class CallToInquireRequest(BaseModel):
    """Body for /tools/call-to-inquire — call a provider to ask about slots"""
    provider_phone: str = Field(description="Provider's phone number (E.164: +XXXXXXXXXXX)")
    provider_name: str = Field(description="Provider's business name")
    date: str = Field(description="Date to check (YYYY-MM-DD format)")
    service_type: Optional[str] = Field(default="appointment", description="Type of service")
    patient_name: Optional[str] = Field(default="CallPilot User", description="Patient name")


class CallProviderRequest(BaseModel):
    """Body for /tools/call-provider — call to CONFIRM a booking"""
    provider_phone: str = Field(description="Provider's phone number (E.164: +XXXXXXXXXXX)")
    provider_name: str = Field(description="Provider's business name")
    appointment_time: str = Field(description="Appointment time (human-readable or ISO-8601)")
    service_type: Optional[str] = Field(default="appointment", description="Type of service")
    patient_name: Optional[str] = Field(default="CallPilot User", description="Patient name")


# ════════════════════════════════════════════════════════════
#  TOOL ENDPOINTS
# ════════════════════════════════════════════════════════════
# Each endpoint:
#   1. Receives a POST request from ElevenLabs
#   2. Logs the call (so you can watch the agent work in real time)
#   3. Calls the corresponding tool function from Phase 2
#   4. Returns the JSON result

@router.post("/find-providers")
async def tool_find_providers(request: FindProvidersRequest):
    """
    Find service providers by category.

    ElevenLabs calls this when the user mentions a service type.
    Pass location for real Places API results; otherwise uses JSON fallback.
    """
    logger.info(
        f"[TOOL CALL] find_providers(category='{request.category}', "
        f"location='{request.location}', limit={request.limit})"
    )

    result = find_providers(
        category=request.category,
        location=request.location,
        limit=request.limit or 5,
    )

    logger.info(f"[TOOL RESULT] Found {result['count']} providers in '{request.category}'")
    return result


@router.post("/find-available")
async def tool_find_available(request: FindAvailableRequest):
    """
    Smart search: find providers filtered by date and rating.

    ElevenLabs calls this when the user specifies a date or quality preference.
    Example: "Find a highly-rated dentist available tomorrow"
    """
    logger.info(
        f"[TOOL CALL] find_available_providers("
        f"category='{request.category}', "
        f"date='{request.date}', "
        f"min_rating={request.min_rating}, "
        f"location='{request.location}', limit={request.limit})"
    )

    result = find_available_providers(
        category=request.category,
        date=request.date,
        min_rating=request.min_rating or 0.0,
        location=request.location,
        limit=request.limit or 5,
    )

    logger.info(f"[TOOL RESULT] Found {result['count']} available providers")
    return result


@router.post("/provider-details")
async def tool_provider_details(request: ProviderDetailsRequest):
    """
    Look up a specific provider by ID.

    ElevenLabs calls this when it needs full details about a known provider.
    """
    logger.info(f"[TOOL CALL] get_provider_by_id(provider_id='{request.provider_id}')")

    result = get_provider_by_id(request.provider_id)

    if not result.get("found"):
        logger.warning(f"[TOOL RESULT] Provider '{request.provider_id}' not found")
    else:
        logger.info(f"[TOOL RESULT] Found provider: {result['provider']['name']}")

    return result


@router.post("/check-calendar")
async def tool_check_calendar(request: CheckCalendarRequest):
    """
    Check if a time slot is free on the user's calendar.

    This is the MOST CALLED tool. The agent calls it every time a
    potential appointment time is discussed, to prevent double-booking.
    """
    logger.info(f"[TOOL CALL] check_availability(slot='{request.slot}')")

    result = check_availability(request.slot)

    status = "FREE ✅" if result["is_available"] else f"BUSY ❌ (conflicts with: {result['conflict_with']})"
    logger.info(f"[TOOL RESULT] Slot {request.slot} → {status}")

    return result


@router.post("/get-busy-slots")
async def tool_get_busy_slots(request: GetBusySlotsRequest):
    """
    Get all busy time slots for a specific date.

    The agent calls this proactively to understand the user's schedule
    before suggesting appointment times.
    """
    logger.info(f"[TOOL CALL] get_busy_slots(date='{request.date}')")

    result = get_busy_slots(request.date)

    logger.info(f"[TOOL RESULT] {result['total_events']} events on {request.date}")
    return result


@router.post("/book-appointment")
async def tool_book_appointment(request: BookAppointmentRequest):
    """
    Book an appointment with a provider.

    This is the FINAL tool call in a successful flow.
    The agent only calls this after:
    1. User approved the provider
    2. Calendar availability was confirmed
    3. User explicitly said "yes, book it"
    """
    logger.info(
        f"[TOOL CALL] book_appointment("
        f"provider='{request.provider_name}', "
        f"slot='{request.slot}')"
    )

    result = book_appointment(
        provider_name=request.provider_name,
        provider_phone=request.provider_phone,
        provider_address=request.provider_address,
        slot=request.slot,
        provider_id=request.provider_id or "unknown",
        service_type=request.service_type or "appointment",
        patient_name=request.patient_name or "CallPilot User",
    )

    if result["success"]:
        logger.info(f"[TOOL RESULT] ✅ BOOKED: {result['message']}")
    else:
        logger.warning(f"[TOOL RESULT] ❌ FAILED: {result['message']}")

    return result


@router.post("/calculate-distance")
async def tool_calculate_distance(request: CalculateDistanceRequest):
    """
    Calculate travel distance and time between user and provider.

    The agent calls this to help compare providers by proximity.
    """
    logger.info(
        f"[TOOL CALL] calculate_distance("
        f"from='{request.user_location}', "
        f"to='{request.provider_address}')"
    )

    result = calculate_distance(
        user_location=request.user_location,
        provider_address=request.provider_address,
        provider_id=request.provider_id or "",
        provider_name=request.provider_name or "",
    )

    logger.info(
        f"[TOOL RESULT] Distance: {result['distance_km']} km, "
        f"Travel: {result['duration_minutes']} min"
    )

    return result


@router.post("/call-to-inquire")
async def tool_call_to_inquire(request: CallToInquireRequest):
    """
    📞 Call a provider to ASK about available appointment slots.

    This is the CORE tool for the call-first flow:
    1. Twilio dials the provider's phone (YOUR PHONE RINGS)
    2. Our AI caller introduces itself and asks for available slots
    3. The provider's schedule is returned with available slots
    4. Call SID is provided as proof the call was made

    The agent uses this BEFORE booking — to discover what's available.
    """
    logger.info(
        f"[TOOL CALL] 📞 call_to_inquire("
        f"to='{request.provider_phone}', "
        f"provider='{request.provider_name}', "
        f"date='{request.date}')"
    )

    from app.tools.call_tool import call_to_inquire

    result = call_to_inquire(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        date=request.date,
        service_type=request.service_type or "appointment",
        patient_name=request.patient_name or "CallPilot User",
    )

    logger.info(
        f"[TOOL RESULT] 📞 Inquiry complete: "
        f"{result['slot_count']} slots found, "
        f"call_sid={result.get('call_sid')}"
    )

    return result


@router.post("/call-provider")
async def tool_call_provider(request: CallProviderRequest):
    """
    📞 Call a provider to CONFIRM a booked appointment.

    Use this AFTER booking — to call the provider and confirm
    the appointment by phone. The AI introduces the patient
    and confirms the appointment details.
    """
    logger.info(
        f"[TOOL CALL] 📞 call_provider("
        f"to='{request.provider_phone}', "
        f"provider='{request.provider_name}', "
        f"time='{request.appointment_time}')"
    )

    from app.tools.call_tool import initiate_call

    result = initiate_call(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        appointment_time=request.appointment_time,
        service_type=request.service_type or "appointment",
        patient_name=request.patient_name or "CallPilot User",
    )

    if result.get("success"):
        logger.info(f"[TOOL RESULT] 📞 Confirmation call initiated: {result['message']}")
    else:
        logger.warning(f"[TOOL RESULT] 📞 Call failed: {result['message']}")

    return result
