"""
CallPilot — Pydantic Schemas
==============================
These models define the SHAPE of data flowing through CallPilot.

WHY PYDANTIC?
  • Type safety — catches bad data BEFORE it causes runtime errors.
  • Auto-documentation — FastAPI uses these to generate API docs.
  • Serialization — .model_dump() converts to dict, .model_dump_json() to JSON.

HOW THEY'RE USED:
  1. A tool function declares its return type as a schema.
  2. FastAPI uses schemas for request/response validation on API routes.
  3. The ElevenLabs agent gets structured data back (not random dicts).

EXAMPLE FLOW:
  User says: "Find me a dentist"
  → Agent calls find_service_providers(category="dentists")
  → Tool returns List[Provider]  ← this schema
  → Agent reads structured data and responds intelligently
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Provider Schema ─────────────────────────────────────────
# Represents a single service provider (dentist, doctor, etc.)
# Maps directly to entries in providers.json.

class Provider(BaseModel):
    """A service provider that can be booked."""

    id: str = Field(
        description="Unique provider ID (e.g., 'd1', 'doc2')"
    )
    name: str = Field(
        description="Business name (e.g., 'Bright Smile Dental')"
    )
    phone: str = Field(
        description="Phone number in E.164 format (e.g., '+15551001001')"
    )
    address: str = Field(
        description="Full street address"
    )
    rating: float = Field(
        description="Google rating (1.0 - 5.0)"
    )
    available_slots: list[str] = Field(
        default_factory=list,
        description="ISO-8601 datetime strings of open appointment slots"
    )


# ── Calendar Event Schema ───────────────────────────────────
# Represents a single event on the user's calendar.
# Used to check for conflicts when booking.

class CalendarEvent(BaseModel):
    """An existing event on the user's calendar."""

    title: str = Field(
        description="Event name (e.g., 'Team Standup', 'Lunch with Sara')"
    )
    start: datetime = Field(
        description="Event start time"
    )
    end: datetime = Field(
        description="Event end time"
    )


# ── Availability Result ─────────────────────────────────────
# What the calendar tool returns after checking a time slot.

class AvailabilityResult(BaseModel):
    """Result of checking whether a time slot is free."""

    slot: str = Field(
        description="The time slot that was checked (ISO-8601)"
    )
    is_available: bool = Field(
        description="True if the slot is free on the user's calendar"
    )
    conflict_with: Optional[str] = Field(
        default=None,
        description="Name of conflicting event, if any"
    )


# ── Distance Result ─────────────────────────────────────────
# Travel time/distance between user and a provider.

class DistanceResult(BaseModel):
    """Travel information between user location and a provider."""

    provider_id: str = Field(
        description="ID of the provider"
    )
    provider_name: str = Field(
        description="Name of the provider"
    )
    distance_km: float = Field(
        description="Distance in kilometers"
    )
    duration_minutes: int = Field(
        description="Estimated travel time in minutes"
    )


# ── Booking Request ─────────────────────────────────────────
# What the user (or agent) sends to book an appointment.

class BookingRequest(BaseModel):
    """Request to book an appointment with a provider."""

    provider_id: str = Field(
        description="ID of the provider to book with"
    )
    slot: str = Field(
        description="Desired time slot (ISO-8601)"
    )
    service_type: str = Field(
        description="Type of service (e.g., 'dentists', 'doctors')"
    )
    patient_name: str = Field(
        default="CallPilot User",
        description="Name for the appointment"
    )


# ── Booking Confirmation ────────────────────────────────────
# What comes back after a successful booking.

class BookingConfirmation(BaseModel):
    """Confirmation details after booking an appointment."""

    success: bool = Field(
        description="Whether the booking was successful"
    )
    provider_name: str = Field(
        description="Name of the booked provider"
    )
    provider_phone: str = Field(
        description="Provider's phone number"
    )
    provider_address: str = Field(
        description="Provider's address"
    )
    appointment_time: str = Field(
        description="Confirmed appointment time (ISO-8601)"
    )
    message: str = Field(
        description="Human-readable confirmation message"
    )


# ── Scored Provider (for ranking) ────────────────────────────
# Used in Swarm Mode (Phase 6) to rank providers by a composite score.

class ScoredProvider(BaseModel):
    """A provider with a computed match score for ranking."""

    provider: Provider = Field(
        description="The provider details"
    )
    score: float = Field(
        description="Composite score (0-100) based on rating, distance, availability"
    )
    distance_km: Optional[float] = Field(
        default=None,
        description="Distance from user in km"
    )
    travel_minutes: Optional[int] = Field(
        default=None,
        description="Travel time in minutes"
    )
    earliest_slot: Optional[str] = Field(
        default=None,
        description="Earliest available slot"
    )
