"""
CallPilot — Provider Tool
===========================
This tool helps the AI agent find and filter service providers.

WHAT IT DOES:
  1. find_providers(category)     → Get all providers of a type
  2. get_provider_by_id(id)       → Look up one specific provider
  3. find_available_providers(...) → Filter by date + minimum rating

DATA SOURCE:
  PRIMARY: Mapbox Search Box API when MAPBOX_ACCESS_TOKEN and location are set.
  FALLBACK: app/data/providers.json when API unavailable or no location.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import MAPBOX_ACCESS_TOKEN
from app.models.schemas import Provider

logger = logging.getLogger("callpilot.provider")

# ── Constants ────────────────────────────────────────────────
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "providers.json"
MAPBOX_FORWARD_URL = "https://api.mapbox.com/search/searchbox/v1/forward"

# Category → query string (singular form for search)
CATEGORY_TO_QUERY = {
    "dentists": "dentist",
    "doctors": "doctor",
    "auto_repair": "auto repair",
    "hair_salon": "hair salon",
}


def _mapbox_forward_search(category: str, location: str, limit: int) -> list | None:
    """
    Call Mapbox Search Box API /forward Text Search.

    Returns list of GeoJSON features, or None on error/empty.
    """
    query_term = CATEGORY_TO_QUERY.get(category, category)
    query = f"{query_term} in {location}"
    cap_limit = min(limit, 10)  # Mapbox max is 10

    try:
        response = httpx.get(
            MAPBOX_FORWARD_URL,
            params={
                "q": query,
                "access_token": MAPBOX_ACCESS_TOKEN,
                "limit": cap_limit,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        if not features:
            logger.info("[MAPBOX] No results for query: %s", query)
            return None

        logger.info("[MAPBOX] Found %d results for: %s", len(features), query)
        return features

    except Exception as e:
        logger.warning("[MAPBOX] Forward search error: %s. Falling back to JSON.", e)
        return None


def _mapbox_to_providers(features: list, limit: int) -> list[dict]:
    """
    Map Mapbox GeoJSON features to Provider schema.

    Mapbox does not return phone or rating; set to empty string and 0.
    """
    providers = []
    for feature in features[:limit]:
        props = feature.get("properties", {})
        mapbox_id = props.get("mapbox_id", "")
        name = props.get("name", "")
        full_address = props.get("full_address", "")
        if not full_address:
            addr = props.get("address", "")
            place = props.get("place_formatted", "")
            full_address = f"{addr}, {place}".strip(", ") if addr or place else ""

        provider = {
            "id": mapbox_id,
            "name": name,
            "phone": "+923107696477",
            "address": full_address,
            "rating": 0.0,
            "available_slots": [],
        }
        providers.append(provider)

    return providers


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


def _find_providers_from_json(category: str, data: dict, strip_slots: bool = True) -> dict:
    """Fallback: load providers from JSON. Resolves category and returns result dict."""
    category_lower = category.lower().strip()
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
    if strip_slots:
        for p in providers:
            p.pop("available_slots", None)

    return {
        "category": resolved_category,
        "providers": providers,
        "count": len(providers),
        "source": "json",
    }


def find_providers(
    category: str,
    location: Optional[str] = None,
    limit: int = 5,
    include_slots: bool = False,
) -> dict:
    """
    Find service providers in a category.

    PRIMARY: Mapbox Search Box API when MAPBOX_ACCESS_TOKEN and location are set.
    FALLBACK: providers.json when API unavailable or no location.

    Args:
        category: 'dentists', 'doctors', 'auto_repair', 'hair_salon'
        location: City or address for Mapbox search (e.g. "San Francisco", "Lahore")
        limit: Max number of providers to return (default 5)

    Returns:
        dict with category, providers (list), count, source ('mapbox' or 'json')
    """
    data = _load_providers()
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
    resolved = category_map.get(category.lower().strip(), "dentists")

    # Try Mapbox Search Box API first when token and location available
    if MAPBOX_ACCESS_TOKEN and location and location.strip():
        features = _mapbox_forward_search(resolved, location.strip(), limit)
        if features:
            # Filter to only features that look like real businesses (have a name that isn't just a city)
            poi_features = [
                f for f in features
                if f.get("properties", {}).get("feature_type") == "poi"
                or (f.get("properties", {}).get("name", "").lower() not in location.lower()
                    and len(f.get("properties", {}).get("name", "")) > 2)
            ]
            if len(poi_features) >= 3:
                providers = _mapbox_to_providers(poi_features, limit)
                for p in providers:
                    p.pop("available_slots", None)
                return {
                    "category": resolved,
                    "providers": providers,
                    "count": len(providers),
                    "source": "mapbox",
                }
        logger.info("[MAPBOX] Not enough real business results; falling back to JSON.")

    # Fallback to JSON
    return _find_providers_from_json(category, data, strip_slots=not include_slots)


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
    location: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """
    Find providers filtered by availability date and minimum rating.

    For Mapbox results: available_slots is always empty; date filter
    does not apply (agent must use call_to_inquire). Filter by rating only.
    For JSON results: filter by both date and rating.

    Args:
        category: Service type (e.g., 'dentists')
        date: Filter to slots on this date (YYYY-MM-DD). Only applies to JSON.
        min_rating: Minimum rating (e.g., 4.5)
        location: City/address for Mapbox search (passed to find_providers)
        limit: Max providers (passed to find_providers)
    """
    result = find_providers(
        category=category,
        location=location,
        limit=limit,
        include_slots=True,
    )

    if result["count"] == 0:
        return result

    filtered = []
    from_mapbox = result.get("source") == "mapbox"

    for provider_dict in result["providers"]:
        # Filter by rating
        if provider_dict.get("rating", 0) < min_rating:
            continue

        # For Mapbox: no slots; include all. For JSON: filter by date if specified.
        if not from_mapbox and date:
            slots = provider_dict.get("available_slots", [])
            matching_slots = [s for s in slots if str(s).startswith(date)]
            if not matching_slots:
                continue
            provider_dict = {**provider_dict, "available_slots": matching_slots}

        filtered.append(provider_dict)

    # Sort by rating (highest first)
    filtered.sort(key=lambda p: p.get("rating", 0), reverse=True)

    # Strip available_slots before returning — agent must use call_to_inquire
    for p in filtered:
        p.pop("available_slots", None)

    return {
        "category": result["category"],
        "providers": filtered,
        "count": len(filtered),
        "filters_applied": {
            "date": date,
            "min_rating": min_rating,
        },
        "source": result.get("source", "json"),
    }
