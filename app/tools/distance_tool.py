import hashlib
import logging

import httpx

from app.config import GOOGLE_MAPS_API_KEY
from app.models.schemas import DistanceResult

logger = logging.getLogger("callpilot.distance")

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _is_real():
    return bool(GOOGLE_MAPS_API_KEY)


def _real_distance(origin: str, destination: str) -> tuple[float, int]:
    """Get real distance and travel time from Google Maps Distance Matrix API."""
    try:
        response = httpx.get(
            DISTANCE_MATRIX_URL,
            params={
                "origins": origin,
                "destinations": destination,
                "mode": "driving",
                "units": "metric",
                "key": GOOGLE_MAPS_API_KEY,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK":
            logger.warning(f"[DISTANCE] API status: {data.get('status')}")
            return _mock_distance(origin, destination)

        element = data["rows"][0]["elements"][0]

        if element.get("status") != "OK":
            logger.warning(f"[DISTANCE] Element status: {element.get('status')}")
            return _mock_distance(origin, destination)

        distance_km = round(element["distance"]["value"] / 1000, 1)
        duration_minutes = round(element["duration"]["value"] / 60)

        logger.info(
            f"[DISTANCE] Real Google Maps: {origin[:30]}... -> {destination[:30]}... = "
            f"{distance_km} km, {duration_minutes} min"
        )

        return distance_km, duration_minutes

    except Exception as e:
        logger.error(f"[DISTANCE] Google Maps API error: {e}. Falling back to mock.")
        return _mock_distance(origin, destination)


def _mock_distance(origin: str, destination: str) -> tuple[float, int]:
    """Generate a consistent mock distance using hash-based determinism."""
    combined = f"{origin.lower().strip()}|{destination.lower().strip()}"
    hash_hex = hashlib.md5(combined.encode()).hexdigest()[:8]
    hash_int = int(hash_hex, 16)

    distance_km = round(1.0 + (hash_int % 240) / 10.0, 1)
    duration_minutes = max(5, int(distance_km * 2.5) + (hash_int % 10) - 5)

    return distance_km, duration_minutes


def calculate_distance(
    user_location: str,
    provider_address: str,
    provider_id: str = "",
    provider_name: str = "",
) -> dict:
    """Calculate travel distance/time between user and a provider."""
    if _is_real():
        distance_km, duration_minutes = _real_distance(user_location, provider_address)
        source = "google_maps"
    else:
        distance_km, duration_minutes = _mock_distance(user_location, provider_address)
        source = "mock"

    result = DistanceResult(
        provider_id=provider_id or "unknown",
        provider_name=provider_name or provider_address,
        distance_km=distance_km,
        duration_minutes=duration_minutes,
    )

    data = result.model_dump()
    data["source"] = source
    return data


def rank_by_distance(user_location: str, providers: list[dict]) -> dict:
    """Rank a list of providers by their distance from the user."""
    ranked = []

    for provider in providers:
        distance_info = calculate_distance(
            user_location=user_location,
            provider_address=provider.get("address", ""),
            provider_id=provider.get("id", ""),
            provider_name=provider.get("name", ""),
        )
        ranked.append({
            **provider,
            "distance_km": distance_info["distance_km"],
            "travel_minutes": distance_info["duration_minutes"],
        })

    ranked.sort(key=lambda p: p["distance_km"])

    return {
        "user_location": user_location,
        "ranked_providers": ranked,
        "count": len(ranked),
        "closest": ranked[0]["name"] if ranked else None,
        "source": "google_maps" if _is_real() else "mock",
    }
