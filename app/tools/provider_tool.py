"""
CallPilot — Provider Tool
===========================
This tool helps the AI agent find and filter service providers.

WHAT IT DOES:
  1. find_providers(category)     → Get all providers of a type
  2. get_provider_by_id(id)       → Look up one specific provider
  3. find_available_providers(...) → Filter by date + minimum rating

DATA SOURCE:
  Currently reads from app/data/providers.json (our mock directory).
  In production, this would call Google Places API to find real
  businesses with ratings, hours, and phone numbers.

HOW THE AI USES THIS:
  User says: "I need a dentist appointment this week"
  → Agent calls: find_providers("dentists")
  → Gets back 3 dentists with ratings + available slots
  → Agent picks the best match or asks user for preference
  → Then calls each provider's number via Twilio

KEY DESIGN DECISION — WHY JSON, NOT A DATABASE?
  For a hackathon, a JSON file is:
  • Zero setup (no Postgres, no migrations)
  • Easy to edit and demo (open file, change data, restart)
  • Sufficient for 10-20 providers
  In production, you'd use a database + Google Places API.
"""

import json
from pathlib import Path
from typing import Optional

from app.models.schemas import Provider


# ── Load Provider Data ──────────────────────────────────────
# Path.resolve() gives absolute path, so this works regardless
# of where you run the server from.
#
# We load ONCE at import time (not on every call) for speed.

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "providers.json"


def _load_providers() -> dict:
    """
    Load the provider directory from JSON.

    Returns the full dict: {"dentists": [...], "doctors": [...], ...}

    WHY a function instead of a global?
      So we can reload if the JSON changes (useful during dev).
      In production with a real API, this becomes an API call.
    """
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def find_providers(category: str) -> dict:
    """
    Find all service providers in a given category.

    This is the first tool the agent calls when the user requests
    an appointment. It returns ALL providers in that category
    so the agent can decide which ones to call.

    Args:
        category: Type of service. Must be one of:
                  'dentists', 'doctors', 'auto_repair', 'hair_salon'

    Returns:
        dict with: category, providers (list), count
        If category not found, returns empty list + available categories.

    Example:
        find_providers("dentists")
        → {"category": "dentists", "count": 3, "providers": [...]}
    """
    data = _load_providers()

    # Normalize input: "Dentist" → "dentists", "doctor" → "doctors"
    category_lower = category.lower().strip()

    # Map common variations to our JSON keys
    category_map = {
        "dentist": "dentists",
        "dentists": "dentists",
        "dental": "dentists",
        "doctor": "doctors",
        "doctors": "doctors",
        "physician": "doctors",
        "medical": "doctors",
        "auto": "auto_repair",
        "auto_repair": "auto_repair",
        "car": "auto_repair",
        "car_repair": "auto_repair",
        "mechanic": "auto_repair",
        "hair": "hair_salon",
        "hair_salon": "hair_salon",
        "haircut": "hair_salon",
        "salon": "hair_salon",
        "barber": "hair_salon",
    }

    resolved_category = category_map.get(category_lower)

    if resolved_category is None or resolved_category not in data:
        return {
            "category": category,
            "providers": [],
            "count": 0,
            "error": f"Unknown category '{category}'",
            "available_categories": list(data.keys()),
        }

    providers = [Provider(**p).model_dump() for p in data[resolved_category]]

    # ── Strip available_slots from the response ──────────────
    # The agent must CALL the provider to discover slots.
    # This prevents the agent from reading hardcoded schedules.
    for p in providers:
        p.pop("available_slots", None)

    return {
        "category": resolved_category,
        "providers": providers,
        "count": len(providers),
    }


def get_provider_by_id(provider_id: str) -> dict:
    """
    Look up a specific provider by their unique ID.

    Useful when the agent already knows which provider to book
    and needs their full details (phone, address, slots).

    Args:
        provider_id: Unique ID (e.g., 'd1', 'doc2', 'hs1')

    Returns:
        dict with provider details, or error if not found.
    """
    data = _load_providers()

    # Search across ALL categories
    for category, providers in data.items():
        for provider in providers:
            if provider["id"] == provider_id:
                result = Provider(**provider).model_dump()
                result.pop("available_slots", None)  # Agent must CALL to get slots
                return {
                    "found": True,
                    "category": category,
                    "provider": result,
                }

    return {
        "found": False,
        "error": f"No provider found with ID '{provider_id}'",
    }


def get_provider_slots(
    provider_phone: str,
    date: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> list[str]:
    """
    INTERNAL function — look up a provider's available slots.

    This is called by call_to_inquire() and the swarm orchestrator.
    The agent does NOT have direct access to this function —
    it must use the call_to_inquire tool (which triggers a real phone call).

    Looks up a provider by phone (or name), and optionally filters
    slots to only those on the given date.

    Args:
        provider_phone: Provider's phone number (used for lookup)
        date: Optional date filter (YYYY-MM-DD)
        provider_name: Optional name for more precise matching

    Returns:
        List of ISO-8601 slot strings
    """
    data = _load_providers()

    # Search across ALL categories for matching provider
    for category, providers in data.items():
        for provider in providers:
            # Match by phone number, or by name if phone isn't unique
            phone_match = provider["phone"] == provider_phone
            name_match = (
                provider_name
                and provider_name.lower() in provider["name"].lower()
            )

            if phone_match and (not provider_name or name_match):
                slots = provider.get("available_slots", [])

                # Filter by date if provided
                if date:
                    slots = [s for s in slots if s.startswith(date)]

                return slots

    # If exact match failed, try searching by name only
    if provider_name:
        for category, providers in data.items():
            for provider in providers:
                if provider_name.lower() in provider["name"].lower():
                    slots = provider.get("available_slots", [])
                    if date:
                        slots = [s for s in slots if s.startswith(date)]
                    return slots

    return []


def find_available_providers(
    category: str,
    date: Optional[str] = None,
    min_rating: float = 0.0,
) -> dict:
    """
    Find providers filtered by availability date and minimum rating.

    This is the SMART search — it combines category + date + quality.
    The agent uses this when the user says something like:
      "Find me a highly-rated dentist available tomorrow"

    Args:
        category: Service type (e.g., 'dentists')
        date: Filter to slots on this date (YYYY-MM-DD format).
              If None, returns all available slots.
        min_rating: Minimum Google rating (e.g., 4.5)

    Returns:
        dict with filtered providers, including only matching slots.

    Example:
        find_available_providers("dentists", date="2026-02-10", min_rating=4.5)
        → Only dentists rated ≥4.5 with slots on Feb 10th
    """
    result = find_providers(category)

    if result["count"] == 0:
        return result

    filtered = []

    for provider_dict in result["providers"]:
        # Filter by rating
        if provider_dict["rating"] < min_rating:
            continue

        # Filter slots by date (if specified)
        if date:
            matching_slots = [
                s for s in provider_dict["available_slots"]
                if s.startswith(date)  # "2026-02-10T14:00:00".startswith("2026-02-10")
            ]
            if not matching_slots:
                continue
            # Only show slots on the requested date
            provider_dict = {**provider_dict, "available_slots": matching_slots}

        filtered.append(provider_dict)

    # Sort by rating (highest first)
    filtered.sort(key=lambda p: p["rating"], reverse=True)

    return {
        "category": result["category"],
        "providers": filtered,
        "count": len(filtered),
        "filters_applied": {
            "date": date,
            "min_rating": min_rating,
        },
    }
