"""
CallPilot — Distance Tool (REAL Google Maps + Mock Fallback)
==============================================================
This tool calculates real travel distance and time using the
Google Maps Distance Matrix API when an API key is available.

REAL MODE (GOOGLE_MAPS_API_KEY set):
  • Calls Google Maps Distance Matrix API
  • Returns actual driving distance (km) and travel time (minutes)

MOCK MODE (no API key):
  • Uses hash-based deterministic fake distances
  • Consistent results for demos

HOW TO ENABLE REAL MODE:
  1. Go to https://console.cloud.google.com
  2. Enable "Distance Matrix API"
  3. Create an API key (APIs & Services → Credentials → Create → API Key)
  4. Add to .env: GOOGLE_MAPS_API_KEY=your_key_here
  5. Restart the server
"""

import hashlib
import logging

import httpx

from app.config import GOOGLE_MAPS_API_KEY
from app.models.schemas import DistanceResult

logger = logging.getLogger("callpilot.distance")

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


def _is_real():
    """Check if real Google Maps API is available."""
    return bool(GOOGLE_MAPS_API_KEY)


# ══════════════════════════════════════════════════════════════
#  REAL: Google Maps Distance Matrix API
# ══════════════════════════════════════════════════════════════

def _real_distance(origin: str, destination: str) -> tuple[float, int]:
    """
    Get real distance and travel time from Google Maps Distance Matrix API.

    API docs: https://developers.google.com/maps/documentation/distance-matrix

    Args:
        origin: Starting address
        destination: Ending address

    Returns:
        Tuple of (distance_km, duration_minutes)
    """
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

        # distance.value is in meters, duration.value is in seconds
        distance_km = round(element["distance"]["value"] / 1000, 1)
        duration_minutes = round(element["duration"]["value"] / 60)

        logger.info(
            f"[DISTANCE] 🗺️ Real Google Maps: {origin[:30]}... → {destination[:30]}... = "
            f"{distance_km} km, {duration_minutes} min"
        )

        return distance_km, duration_minutes

    except Exception as e:
        logger.error(f"[DISTANCE] Google Maps API error: {e}. Falling back to mock.")
        return _mock_distance(origin, destination)


# ══════════════════════════════════════════════════════════════
#  MOCK: Hash-based deterministic distances
# ══════════════════════════════════════════════════════════════

def _mock_distance(origin: str, destination: str) -> tuple[float, int]:
    """
    Generate a consistent mock distance between two addresses.

    Uses MD5 hashing for deterministic results:
    same inputs → same output (important for demos).
    """
    combined = f"{origin.lower().strip()}|{destination.lower().strip()}"
    hash_hex = hashlib.md5(combined.encode()).hexdigest()[:8]
    hash_int = int(hash_hex, 16)

    distance_km = round(1.0 + (hash_int % 240) / 10.0, 1)
    duration_minutes = max(5, int(distance_km * 2.5) + (hash_int % 10) - 5)

    return distance_km, duration_minutes


# ══════════════════════════════════════════════════════════════
#  PUBLIC API (used by routes and swarm)
# ══════════════════════════════════════════════════════════════

def calculate_distance(
    user_location: str,
    provider_address: str,
    provider_id: str = "",
    provider_name: str = "",
) -> dict:
    """
    Calculate travel distance/time between user and a provider.

    Automatically uses Google Maps API if available, falls back to mock.

    Args:
        user_location: User's current address or location
        provider_address: Provider's address
        provider_id: Provider's unique ID (for reference)
        provider_name: Provider's name (for reference)

    Returns:
        dict with: provider_id, provider_name, distance_km, duration_minutes, source
    """
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
    """
    Rank a list of providers by their distance from the user.

    Uses real Google Maps distances when available.

    Args:
        user_location: User's address
        providers: List of provider dicts (must have 'address', 'id', 'name')

    Returns:
        dict with: user_location, ranked_providers (sorted by distance), source
    """
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
