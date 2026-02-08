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

logger = logging.getLogger("callpilot.tools")

router = APIRouter(prefix="/tools", tags=["Tools (Webhook Endpoints)"])


class FindProvidersRequest(BaseModel):
    category: str
    location: Optional[str] = None
    limit: Optional[int] = 5


class FindAvailableRequest(BaseModel):
    category: str
    date: Optional[str] = None
    min_rating: Optional[float] = 0.0
    location: Optional[str] = None
    limit: Optional[int] = 5


class ProviderDetailsRequest(BaseModel):
    provider_id: str


class CheckCalendarRequest(BaseModel):
    slot: str


class GetBusySlotsRequest(BaseModel):
    date: str


class BookAppointmentRequest(BaseModel):
    provider_id: Optional[str] = "unknown"
    provider_name: str
    provider_phone: str
    provider_address: str
    slot: str
    service_type: Optional[str] = "appointment"
    patient_name: Optional[str] = "CallPilot User"


class CalculateDistanceRequest(BaseModel):
    user_location: str
    provider_address: str
    provider_id: Optional[str] = ""
    provider_name: Optional[str] = ""


class CallToInquireRequest(BaseModel):
    provider_phone: str
    provider_name: str
    date: str
    service_type: Optional[str] = "appointment"
    patient_name: Optional[str] = "CallPilot User"


class CallProviderRequest(BaseModel):
    provider_phone: str
    provider_name: str
    appointment_time: str
    service_type: Optional[str] = "appointment"
    patient_name: Optional[str] = "CallPilot User"


@router.post("/find-providers")
async def tool_find_providers(request: FindProvidersRequest):
    logger.info(f"[TOOL CALL] find_providers(category='{request.category}', location='{request.location}', limit={request.limit})")
    result = find_providers(category=request.category, location=request.location, limit=request.limit or 5)
    logger.info(f"[TOOL RESULT] Found {result['count']} providers in '{request.category}'")
    return result


@router.post("/find-available")
async def tool_find_available(request: FindAvailableRequest):
    logger.info(f"[TOOL CALL] find_available_providers(category='{request.category}', date='{request.date}', min_rating={request.min_rating})")
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
    logger.info(f"[TOOL CALL] get_provider_by_id(provider_id='{request.provider_id}')")
    result = get_provider_by_id(request.provider_id)
    if not result.get("found"):
        logger.warning(f"[TOOL RESULT] Provider '{request.provider_id}' not found")
    else:
        logger.info(f"[TOOL RESULT] Found provider: {result['provider']['name']}")
    return result


@router.post("/check-calendar")
async def tool_check_calendar(request: CheckCalendarRequest):
    logger.info(f"[TOOL CALL] check_availability(slot='{request.slot}')")
    result = check_availability(request.slot)
    status = "FREE" if result["is_available"] else f"BUSY (conflicts with: {result['conflict_with']})"
    logger.info(f"[TOOL RESULT] Slot {request.slot} -> {status}")
    return result


@router.post("/get-busy-slots")
async def tool_get_busy_slots(request: GetBusySlotsRequest):
    logger.info(f"[TOOL CALL] get_busy_slots(date='{request.date}')")
    result = get_busy_slots(request.date)
    logger.info(f"[TOOL RESULT] {result['total_events']} events on {request.date}")
    return result


@router.post("/book-appointment")
async def tool_book_appointment(request: BookAppointmentRequest):
    logger.info(f"[TOOL CALL] book_appointment(provider='{request.provider_name}', slot='{request.slot}')")
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
        logger.info(f"[TOOL RESULT] BOOKED: {result['message']}")
    else:
        logger.warning(f"[TOOL RESULT] FAILED: {result['message']}")
    return result


@router.post("/calculate-distance")
async def tool_calculate_distance(request: CalculateDistanceRequest):
    logger.info(f"[TOOL CALL] calculate_distance(from='{request.user_location}', to='{request.provider_address}')")
    result = calculate_distance(
        user_location=request.user_location,
        provider_address=request.provider_address,
        provider_id=request.provider_id or "",
        provider_name=request.provider_name or "",
    )
    logger.info(f"[TOOL RESULT] Distance: {result['distance_km']} km, Travel: {result['duration_minutes']} min")
    return result


@router.post("/call-to-inquire")
async def tool_call_to_inquire(request: CallToInquireRequest):
    logger.info(f"[TOOL CALL] call_to_inquire(to='{request.provider_phone}', provider='{request.provider_name}', date='{request.date}')")
    from app.tools.call_tool import call_to_inquire
    result = call_to_inquire(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        date=request.date,
        service_type=request.service_type or "appointment",
        patient_name=request.patient_name or "CallPilot User",
    )
    logger.info(f"[TOOL RESULT] Inquiry complete: {result['slot_count']} slots found, call_sid={result.get('call_sid')}")
    return result


@router.post("/call-provider")
async def tool_call_provider(request: CallProviderRequest):
    logger.info(f"[TOOL CALL] call_provider(to='{request.provider_phone}', provider='{request.provider_name}', time='{request.appointment_time}')")
    from app.tools.call_tool import initiate_call
    result = initiate_call(
        provider_phone=request.provider_phone,
        provider_name=request.provider_name,
        appointment_time=request.appointment_time,
        service_type=request.service_type or "appointment",
        patient_name=request.patient_name or "CallPilot User",
    )
    if result.get("success"):
        logger.info(f"[TOOL RESULT] Confirmation call initiated: {result['message']}")
    else:
        logger.warning(f"[TOOL RESULT] Call failed: {result['message']}")
    return result
