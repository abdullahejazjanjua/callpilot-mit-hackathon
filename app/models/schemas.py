from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Provider(BaseModel):
    id: str
    name: str
    phone: str
    address: str
    rating: float
    available_slots: list[str] = Field(default_factory=list)


class CalendarEvent(BaseModel):
    title: str
    start: datetime
    end: datetime


class AvailabilityResult(BaseModel):
    slot: str
    is_available: bool
    conflict_with: Optional[str] = None


class DistanceResult(BaseModel):
    provider_id: str
    provider_name: str
    distance_km: float
    duration_minutes: int


class BookingRequest(BaseModel):
    provider_id: str
    slot: str
    service_type: str
    patient_name: str = "CallPilot User"


class BookingConfirmation(BaseModel):
    success: bool
    provider_name: str
    provider_phone: str
    provider_address: str
    appointment_time: str
    message: str


class ScoredProvider(BaseModel):
    provider: Provider
    score: float
    distance_km: Optional[float] = None
    travel_minutes: Optional[int] = None
    earliest_slot: Optional[str] = None
