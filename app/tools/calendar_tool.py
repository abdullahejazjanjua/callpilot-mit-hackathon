import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.models.schemas import (
    AvailabilityResult,
    BookingConfirmation,
    CalendarEvent,
)
from app.config import GOOGLE_CALENDAR_ID

logger = logging.getLogger("callpilot.calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOKEN_FILE = PROJECT_ROOT / "token.json"
DEFAULT_DURATION_MINUTES = 60

_calendar_service = None
_service_initialized = False


def _get_calendar_service():
    """Get an authenticated Google Calendar service, or None for mock fallback."""
    global _calendar_service, _service_initialized

    if _service_initialized:
        return _calendar_service

    _service_initialized = True

    if not TOKEN_FILE.exists():
        logger.info("[CALENDAR] No token.json found — using MOCK calendar.")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("[CALENDAR] Refreshing expired token...")
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
            else:
                logger.warning("[CALENDAR] Token invalid and can't refresh. Using mock data.")
                return None

        _calendar_service = build("calendar", "v3", credentials=creds)
        logger.info("[CALENDAR] Connected to REAL Google Calendar!")
        return _calendar_service

    except Exception as e:
        logger.error(f"[CALENDAR] Failed to connect: {e}. Using mock data.")
        return None


def _is_real():
    return _get_calendar_service() is not None


MOCK_CALENDAR: list[CalendarEvent] = [
    CalendarEvent(title="Brunch with Family", start=datetime(2026, 2, 8, 11, 0), end=datetime(2026, 2, 8, 12, 30)),
    CalendarEvent(title="Team Standup", start=datetime(2026, 2, 9, 9, 0), end=datetime(2026, 2, 9, 9, 30)),
    CalendarEvent(title="Lunch with Sara", start=datetime(2026, 2, 9, 12, 0), end=datetime(2026, 2, 9, 13, 0)),
    CalendarEvent(title="Project Review", start=datetime(2026, 2, 10, 14, 0), end=datetime(2026, 2, 10, 15, 0)),
    CalendarEvent(title="Gym Session", start=datetime(2026, 2, 11, 7, 0), end=datetime(2026, 2, 11, 8, 0)),
    CalendarEvent(title="Dentist Follow-up", start=datetime(2026, 2, 12, 10, 0), end=datetime(2026, 2, 12, 11, 0)),
    CalendarEvent(title="Sprint Retro", start=datetime(2026, 2, 13, 15, 0), end=datetime(2026, 2, 13, 16, 0)),
]


def check_availability(slot: str) -> dict:
    """Check if a specific time slot is free on the user's calendar."""
    try:
        proposed_start = datetime.fromisoformat(slot)
    except ValueError:
        return {
            "slot": slot,
            "is_available": False,
            "conflict_with": "Invalid date format. Use ISO-8601 (e.g., 2026-02-10T14:00:00)",
        }

    proposed_end = proposed_start + timedelta(minutes=DEFAULT_DURATION_MINUTES)
    service = _get_calendar_service()

    if service:
        return _real_check_availability(service, slot, proposed_start, proposed_end)
    else:
        return _mock_check_availability(slot, proposed_start, proposed_end)


def _real_check_availability(service, slot: str, proposed_start: datetime, proposed_end: datetime) -> dict:
    try:
        if proposed_start.tzinfo is None:
            time_min = proposed_start.isoformat() + "Z"
            time_max = proposed_end.isoformat() + "Z"
        else:
            time_min = proposed_start.isoformat()
            time_max = proposed_end.isoformat()

        events_result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if events:
            conflict_event = events[0]
            conflict_name = conflict_event.get("summary", "Busy")
            logger.info(f"[CALENDAR] Slot {slot} conflicts with '{conflict_name}'")
            return AvailabilityResult(
                slot=slot,
                is_available=False,
                conflict_with=conflict_name,
            ).model_dump()
        else:
            logger.info(f"[CALENDAR] Real calendar: slot {slot} is FREE")
            return AvailabilityResult(
                slot=slot,
                is_available=True,
                conflict_with=None,
            ).model_dump()

    except Exception as e:
        logger.error(f"[CALENDAR] Error checking real calendar: {e}")
        return AvailabilityResult(
            slot=slot,
            is_available=True,
            conflict_with=None,
        ).model_dump()


def _mock_check_availability(slot: str, proposed_start: datetime, proposed_end: datetime) -> dict:
    for event in MOCK_CALENDAR:
        if proposed_start < event.end and event.start < proposed_end:
            return AvailabilityResult(
                slot=slot,
                is_available=False,
                conflict_with=event.title,
            ).model_dump()

    return AvailabilityResult(
        slot=slot,
        is_available=True,
        conflict_with=None,
    ).model_dump()


def get_busy_slots(date: str) -> dict:
    """Get all busy time slots for a specific date."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {
            "date": date,
            "busy_slots": [],
            "total_events": 0,
            "error": "Invalid date format. Use YYYY-MM-DD",
        }

    service = _get_calendar_service()

    if service:
        return _real_get_busy_slots(service, date, target_date)
    else:
        return _mock_get_busy_slots(date, target_date)


def _real_get_busy_slots(service, date: str, target_date) -> dict:
    try:
        day_start = datetime.combine(target_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        time_min = day_start.isoformat() + "Z"
        time_max = day_end.isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        busy = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            busy.append({
                "title": event.get("summary", "Busy"),
                "start": start,
                "end": end,
            })

        logger.info(f"[CALENDAR] Real calendar: {len(busy)} event(s) on {date}")

        return {
            "date": date,
            "busy_slots": busy,
            "total_events": len(busy),
            "source": "google_calendar",
        }

    except Exception as e:
        logger.error(f"[CALENDAR] Error reading real calendar: {e}")
        return {
            "date": date,
            "busy_slots": [],
            "total_events": 0,
            "source": "google_calendar",
            "error": f"Failed to read calendar: {str(e)}",
        }


def _mock_get_busy_slots(date: str, target_date) -> dict:
    busy = []
    for event in MOCK_CALENDAR:
        if event.start.date() == target_date:
            busy.append({
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
            })

    return {
        "date": date,
        "busy_slots": busy,
        "total_events": len(busy),
        "source": "mock",
    }


def book_appointment(
    provider_name: str,
    provider_phone: str,
    provider_address: str,
    slot: str,
    provider_id: str = "unknown",
    service_type: str = "appointment",
    patient_name: str = "CallPilot User",
) -> dict:
    """Book an appointment by adding it to the user's calendar."""
    availability = check_availability(slot)
    if not availability["is_available"]:
        return BookingConfirmation(
            success=False,
            provider_name=provider_name,
            provider_phone=provider_phone,
            provider_address=provider_address,
            appointment_time=slot,
            message=f"Cannot book — conflicts with '{availability['conflict_with']}'",
        ).model_dump()

    service = _get_calendar_service()

    if service:
        return _real_book_appointment(
            service, provider_name, provider_phone, provider_address,
            slot, provider_id, service_type, patient_name,
        )
    else:
        return _mock_book_appointment(
            provider_name, provider_phone, provider_address,
            slot, provider_id, service_type, patient_name,
        )


def _real_book_appointment(
    service,
    provider_name: str,
    provider_phone: str,
    provider_address: str,
    slot: str,
    provider_id: str,
    service_type: str,
    patient_name: str,
) -> dict:
    try:
        appointment_start = datetime.fromisoformat(slot)
        appointment_end = appointment_start + timedelta(minutes=DEFAULT_DURATION_MINUTES)

        event_title = f"{service_type.title()} @ {provider_name}"

        event = {
            "summary": event_title,
            "location": provider_address,
            "description": (
                f"Booked by CallPilot AI\n\n"
                f"Provider: {provider_name}\n"
                f"Phone: {provider_phone}\n"
                f"Address: {provider_address}\n"
                f"Service: {service_type}\n"
                f"Patient: {patient_name}\n"
                f"Provider ID: {provider_id}\n"
            ),
            "start": {
                "dateTime": appointment_start.isoformat(),
                "timeZone": "America/Los_Angeles",
            },
            "end": {
                "dateTime": appointment_end.isoformat(),
                "timeZone": "America/Los_Angeles",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                ],
            },
        }

        created_event = (
            service.events()
            .insert(calendarId=GOOGLE_CALENDAR_ID, body=event)
            .execute()
        )

        event_link = created_event.get("htmlLink", "")
        formatted_time = appointment_start.strftime("%A, %B %d at %I:%M %p")

        logger.info(f"[CALENDAR] REAL booking created: {event_title} on {formatted_time}")
        logger.info(f"[CALENDAR]    Google Calendar link: {event_link}")

        return BookingConfirmation(
            success=True,
            provider_name=provider_name,
            provider_phone=provider_phone,
            provider_address=provider_address,
            appointment_time=slot,
            message=(
                f"Appointment booked with {provider_name} on {formatted_time}. "
                f"Address: {provider_address}. Phone: {provider_phone}. "
                f"Added to your Google Calendar!"
            ),
        ).model_dump()

    except Exception as e:
        logger.error(f"[CALENDAR] Failed to create real event: {e}")
        return BookingConfirmation(
            success=False,
            provider_name=provider_name,
            provider_phone=provider_phone,
            provider_address=provider_address,
            appointment_time=slot,
            message=f"Failed to create calendar event: {str(e)}",
        ).model_dump()


def _mock_book_appointment(
    provider_name: str,
    provider_phone: str,
    provider_address: str,
    slot: str,
    provider_id: str,
    service_type: str,
    patient_name: str,
) -> dict:
    appointment_start = datetime.fromisoformat(slot)
    appointment_end = appointment_start + timedelta(minutes=DEFAULT_DURATION_MINUTES)

    new_event = CalendarEvent(
        title=f"{service_type.title()} @ {provider_name}",
        start=appointment_start,
        end=appointment_end,
    )

    MOCK_CALENDAR.append(new_event)

    formatted_time = appointment_start.strftime("%A, %B %d at %I:%M %p")

    return BookingConfirmation(
        success=True,
        provider_name=provider_name,
        provider_phone=provider_phone,
        provider_address=provider_address,
        appointment_time=slot,
        message=(
            f"Appointment booked with {provider_name} on {formatted_time}. "
            f"Address: {provider_address}. Phone: {provider_phone}. "
            f"(Mock calendar — run setup_google_auth.py for real bookings)"
        ),
    ).model_dump()
