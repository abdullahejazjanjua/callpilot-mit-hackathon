import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import MAPBOX_ACCESS_TOKEN
from app.models.schemas import Provider

logger = logging.getLogger("callpilot.provider")

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "providers.json"
MAPBOX_FORWARD_URL = "https://api.mapbox.com/search/searchbox/v1/forward"

CATEGORY_TO_QUERY = {
    "dentists": "dentist",
    "doctors": "doctor",
    "auto_repair": "auto repair",
    "hair_salon": "hair salon",
}


def _mapbox_forward_search(category: str, location: str, limit: int) -> list | None:
    query_term = CATEGORY_TO_QUERY.get(category, category)
    query = f"{query_term} in {location}"
    cap_limit = min(limit, 10)

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
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def _resolve_category(category: str) -> Optional[str]:
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
    return category_map.get(category.lower().strip())


def _find_providers_from_json(category: str, data: dict, strip_slots: bool = True) -> dict:
    resolved_category = _resolve_category(category)

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
    """Find service providers by category using Mapbox API or JSON fallback."""
    data = _load_providers()
    resolved = _resolve_category(category) or "dentists"

    if MAPBOX_ACCESS_TOKEN and location and location.strip():
        features = _mapbox_forward_search(resolved, location.strip(), limit)
        if features:
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

    return _find_providers_from_json(category, data, strip_slots=not include_slots)


def get_provider_by_id(provider_id: str) -> dict:
    """Look up a specific provider by their unique ID."""
    data = _load_providers()

    for category, providers in data.items():
        for provider in providers:
            if provider["id"] == provider_id:
                result = Provider(**provider).model_dump()
                result.pop("available_slots", None)
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
    """Internal: look up a provider's available slots by phone or name."""
    data = _load_providers()

    for category, providers in data.items():
        for provider in providers:
            phone_match = provider["phone"] == provider_phone
            name_match = (
                provider_name
                and provider_name.lower() in provider["name"].lower()
            )

            if phone_match and (not provider_name or name_match):
                slots = provider.get("available_slots", [])
                if date:
                    slots = [s for s in slots if s.startswith(date)]
                return slots

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
    """Find providers filtered by availability date and minimum rating."""
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
        if provider_dict.get("rating", 0) < min_rating:
            continue

        if not from_mapbox and date:
            slots = provider_dict.get("available_slots", [])
            matching_slots = [s for s in slots if str(s).startswith(date)]
            if not matching_slots:
                continue
            provider_dict = {**provider_dict, "available_slots": matching_slots}

        filtered.append(provider_dict)

    filtered.sort(key=lambda p: p.get("rating", 0), reverse=True)

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
