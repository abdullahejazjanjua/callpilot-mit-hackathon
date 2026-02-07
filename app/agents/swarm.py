"""
CallPilot — Swarm Orchestrator
================================
The Swarm is what makes CallPilot special.

Instead of the agent going step-by-step (find → check → ask → book),
Swarm Mode does EVERYTHING in one shot:

  ┌────────────────────────────────────────────────────────────────────┐
  │                     SWARM ORCHESTRATOR                             │
  │                                                                    │
  │  User: "I need a dentist on Tuesday near Market St"                │
  │                                                                    │
  │  Step 1: Get user's busy slots for Tuesday                        │
  │          ↓                                                         │
  │  Step 2: Find all dentists with slots on Tuesday                  │
  │          ↓                                                         │
  │  Step 3: Calculate distance to EACH provider                      │
  │          ↓                                                         │
  │  Step 4: For each provider, find non-conflicting slots            │
  │          ↓                                                         │
  │  Step 5: SCORE each provider:                                     │
  │          score = 40% × rating + 30% × proximity + 30% × earliness│
  │          ↓                                                         │
  │  Step 6: Rank by score, pick the best                             │
  │          ↓                                                         │
  │  Step 7: Auto-book (or return ranked list for user choice)        │
  │                                                                    │
  │  Result: "Booked Downtown Dental at 9am — 4.5★, 8km, no conflicts"│
  └────────────────────────────────────────────────────────────────────┘

WHY IS THIS POWERFUL?
  • In a normal system, the user picks from a list. Boring.
  • In CallPilot Swarm, the AI evaluates ALL options intelligently
    and makes the OPTIMAL choice. The user just says what they need.
  • It's like having a human assistant who calls 5 clinics,
    compares them, and books the best one — in under a second.

SCORING ALGORITHM:
  Each provider gets a composite score (0-100):

  rating_score   = (rating / 5.0) × 100          → max 100
  distance_score = max(0, 100 - distance_km × 4) → closer = higher
  time_score     = max(0, 100 - hours_away × 10)  → sooner = higher

  final_score = (0.40 × rating_score)
              + (0.30 × distance_score)
              + (0.30 × time_score)

  Weights are tunable — a user who values quality over proximity
  could shift to 60% rating, 20% distance, 20% time.
"""

import logging
from datetime import datetime
from typing import Optional

from app.tools.calendar_tool import check_availability, get_busy_slots
from app.tools.provider_tool import find_available_providers
from app.tools.distance_tool import calculate_distance
from app.tools.calendar_tool import book_appointment

logger = logging.getLogger("callpilot.swarm")


# ── Scoring Weights ──────────────────────────────────────
# These control how the swarm ranks providers.
# They should add up to 1.0.

DEFAULT_WEIGHTS = {
    "rating": 0.40,     # Quality matters most
    "distance": 0.30,   # Convenience is next
    "time": 0.30,       # Earliness is a tiebreaker
}


def _score_rating(rating: float) -> float:
    """
    Convert a 1-5 star rating to a 0-100 score.

    5.0 → 100, 4.0 → 80, 3.0 → 60, etc.
    """
    return (rating / 5.0) * 100


def _score_distance(distance_km: float) -> float:
    """
    Convert distance to a proximity score (0-100).

    0 km → 100 (perfect), 25 km → 0 (too far)
    Every km reduces the score by 4 points.
    """
    return max(0, 100 - distance_km * 4)


def _score_time(slot_str: str) -> float:
    """
    Score a time slot by how soon it is (0-100).

    Sooner slots get higher scores.
    A slot right now → 100, a slot 10+ hours from now → 0.
    """
    try:
        slot_time = datetime.fromisoformat(slot_str)
        now = datetime.now()
        hours_away = max(0, (slot_time - now).total_seconds() / 3600)
        return max(0, 100 - hours_away * 1.0)  # Lose 1 point per hour
    except (ValueError, TypeError):
        return 50  # Default for unparseable times


def score_provider(
    provider: dict,
    distance_km: float,
    best_slot: str,
    weights: Optional[dict] = None,
) -> float:
    """
    Calculate a composite score for a provider.

    This is the core ranking algorithm that makes Swarm Mode intelligent.

    Args:
        provider: Provider dict with 'rating' key
        distance_km: Distance from user in km
        best_slot: The best (earliest non-conflicting) slot ISO string
        weights: Custom weights (default: 40% rating, 30% distance, 30% time)

    Returns:
        Score between 0 and 100
    """
    w = weights or DEFAULT_WEIGHTS

    r_score = _score_rating(provider.get("rating", 3.0))
    d_score = _score_distance(distance_km)
    t_score = _score_time(best_slot)

    final = (
        w["rating"] * r_score
        + w["distance"] * d_score
        + w["time"] * t_score
    )

    return round(final, 1)


def run_swarm(
    category: str,
    date: str,
    user_location: str = "100 Market St, San Francisco, CA",
    min_rating: float = 0.0,
    auto_book: bool = False,
    patient_name: str = "CallPilot User",
    weights: Optional[dict] = None,
) -> dict:
    """
    🐝 THE SWARM — Autonomous appointment scheduling in one call.

    This function does EVERYTHING:
    1. Checks user's calendar for conflicts
    2. Finds matching providers
    3. Calculates distances
    4. Filters out conflicting slots
    5. Scores and ranks all options
    6. Optionally auto-books the best one

    Args:
        category: Service type (e.g., 'dentists', 'doctors')
        date: Target date (YYYY-MM-DD)
        user_location: User's address for distance calculation
        min_rating: Minimum rating filter (0.0-5.0)
        auto_book: If True, automatically books the #1 ranked provider
        patient_name: Name for the booking
        weights: Custom scoring weights

    Returns:
        dict with: ranked_providers, best_match, booking (if auto_book),
                   analysis summary, and the full decision trail
    """
    logger.info(f"[SWARM] 🐝 Starting swarm for '{category}' on {date}")
    logger.info(f"[SWARM]    Location: {user_location}")
    logger.info(f"[SWARM]    Min rating: {min_rating}, Auto-book: {auto_book}")

    decision_trail = []  # Track every step for transparency

    # ── Step 1: Check user's calendar ─────────────────────
    logger.info("[SWARM] Step 1: Checking user's calendar...")
    calendar = get_busy_slots(date)
    busy_slots = calendar.get("busy_slots", [])

    decision_trail.append({
        "step": 1,
        "action": "check_calendar",
        "result": f"Found {len(busy_slots)} event(s) on {date}",
        "details": busy_slots,
    })

    logger.info(f"[SWARM]    → {len(busy_slots)} existing event(s) on {date}")

    # ── Step 2: Find matching providers ───────────────────
    logger.info("[SWARM] Step 2: Finding available providers...")
    provider_result = find_available_providers(
        category=category,
        date=date,
        min_rating=min_rating,
    )

    providers = provider_result.get("providers", [])
    decision_trail.append({
        "step": 2,
        "action": "find_providers",
        "result": f"Found {len(providers)} provider(s) in '{category}'",
        "filters": {"date": date, "min_rating": min_rating},
    })

    if not providers:
        logger.warning("[SWARM]    → No providers found. Swarm complete (empty).")
        return {
            "success": False,
            "message": f"No {category} found with slots on {date} (min rating: {min_rating})",
            "ranked_providers": [],
            "best_match": None,
            "booking": None,
            "decision_trail": decision_trail,
        }

    logger.info(f"[SWARM]    → {len(providers)} provider(s) found")

    # ── Step 3: Score each provider ───────────────────────
    logger.info("[SWARM] Step 3: Scoring all providers...")
    scored_providers = []

    for provider in providers:
        # 3a. Calculate distance
        dist = calculate_distance(
            user_location=user_location,
            provider_address=provider.get("address", ""),
            provider_id=provider.get("id", ""),
            provider_name=provider.get("name", ""),
        )
        distance_km = dist["distance_km"]
        travel_min = dist["duration_minutes"]

        # 3b. Find the best non-conflicting slot
        available_slots = provider.get("available_slots", [])
        best_slot = None
        compatible_slots = []

        for slot in available_slots:
            avail = check_availability(slot)
            if avail["is_available"]:
                compatible_slots.append(slot)
                if best_slot is None:
                    best_slot = slot

        if not compatible_slots:
            # All slots conflict — skip this provider
            decision_trail.append({
                "step": 3,
                "action": "score_provider",
                "provider": provider["name"],
                "result": "SKIPPED — all slots conflict with calendar",
                "slots_checked": len(available_slots),
            })
            logger.info(f"[SWARM]    ✗ {provider['name']}: all slots conflict, skipping")
            continue

        # 3c. Calculate composite score
        provider_score = score_provider(
            provider=provider,
            distance_km=distance_km,
            best_slot=best_slot,
            weights=weights,
        )

        scored_entry = {
            "provider_id": provider["id"],
            "provider_name": provider["name"],
            "phone": provider["phone"],
            "address": provider["address"],
            "rating": provider["rating"],
            "distance_km": distance_km,
            "travel_minutes": travel_min,
            "best_slot": best_slot,
            "compatible_slots": compatible_slots,
            "score": provider_score,
            "score_breakdown": {
                "rating_score": round(_score_rating(provider["rating"]), 1),
                "distance_score": round(_score_distance(distance_km), 1),
                "time_score": round(_score_time(best_slot), 1),
            },
        }

        scored_providers.append(scored_entry)

        decision_trail.append({
            "step": 3,
            "action": "score_provider",
            "provider": provider["name"],
            "score": provider_score,
            "distance_km": distance_km,
            "best_slot": best_slot,
            "compatible_slots_count": len(compatible_slots),
        })

        logger.info(
            f"[SWARM]    ✓ {provider['name']}: "
            f"score={provider_score}, "
            f"rating={provider['rating']}★, "
            f"dist={distance_km}km, "
            f"best_slot={best_slot[11:16] if best_slot else 'N/A'}"
        )

    # ── Step 4: Rank by score ─────────────────────────────
    scored_providers.sort(key=lambda p: p["score"], reverse=True)

    if not scored_providers:
        logger.warning("[SWARM]    → All providers have conflicting slots.")
        return {
            "success": False,
            "message": f"Found {len(providers)} provider(s) but all slots conflict with your calendar",
            "ranked_providers": [],
            "best_match": None,
            "booking": None,
            "decision_trail": decision_trail,
        }

    best = scored_providers[0]

    decision_trail.append({
        "step": 4,
        "action": "rank_providers",
        "result": f"Best match: {best['provider_name']} (score: {best['score']})",
        "ranking": [
            {"rank": i + 1, "name": p["provider_name"], "score": p["score"]}
            for i, p in enumerate(scored_providers)
        ],
    })

    logger.info(f"[SWARM] Step 4: Ranking complete → #{1} {best['provider_name']} (score {best['score']})")

    # ── Step 5: Auto-book if requested ────────────────────
    booking_result = None

    if auto_book:
        logger.info(f"[SWARM] Step 5: Auto-booking {best['provider_name']} at {best['best_slot']}...")

        booking_result = book_appointment(
            provider_name=best["provider_name"],
            provider_phone=best["phone"],
            provider_address=best["address"],
            slot=best["best_slot"],
            provider_id=best["provider_id"],
            service_type=category,
            patient_name=patient_name,
        )

        decision_trail.append({
            "step": 5,
            "action": "auto_book",
            "provider": best["provider_name"],
            "slot": best["best_slot"],
            "success": booking_result.get("success", False),
            "message": booking_result.get("message", ""),
        })

        if booking_result.get("success"):
            logger.info(f"[SWARM]    ✅ Booked! {booking_result['message']}")
        else:
            logger.warning(f"[SWARM]    ❌ Booking failed: {booking_result['message']}")
    else:
        decision_trail.append({
            "step": 5,
            "action": "present_options",
            "result": "Auto-book disabled — returning ranked list for user choice",
        })

    # ── Build analysis summary ────────────────────────────
    analysis = {
        "providers_evaluated": len(providers),
        "providers_compatible": len(scored_providers),
        "providers_skipped": len(providers) - len(scored_providers),
        "calendar_conflicts": len(busy_slots),
        "best_match": {
            "name": best["provider_name"],
            "score": best["score"],
            "why": _explain_choice(best, scored_providers),
        },
    }

    logger.info(f"[SWARM] 🐝 Swarm complete — evaluated {len(providers)}, "
                f"compatible {len(scored_providers)}, best: {best['provider_name']}")

    return {
        "success": True,
        "message": f"Swarm evaluated {len(providers)} provider(s) and found {len(scored_providers)} compatible option(s)",
        "ranked_providers": scored_providers,
        "best_match": best,
        "booking": booking_result,
        "analysis": analysis,
        "decision_trail": decision_trail,
    }


def _explain_choice(best: dict, all_scored: list) -> str:
    """
    Generate a human-readable explanation of why this provider was chosen.

    This is what the agent reads back to the user:
    "I picked Downtown Dental because they're the closest at 8km,
     rated 4.5 stars, and have a 9am slot that works with your schedule."
    """
    parts = []

    # Rating reasoning
    if best["rating"] >= 4.5:
        parts.append(f"highly rated at {best['rating']}★")
    elif best["rating"] >= 4.0:
        parts.append(f"well rated at {best['rating']}★")
    else:
        parts.append(f"rated {best['rating']}★")

    # Distance reasoning
    if best["distance_km"] <= 5:
        parts.append(f"very close at {best['distance_km']}km ({best['travel_minutes']} min drive)")
    elif best["distance_km"] <= 15:
        parts.append(f"reasonably close at {best['distance_km']}km ({best['travel_minutes']} min drive)")
    else:
        parts.append(f"{best['distance_km']}km away ({best['travel_minutes']} min drive)")

    # Slot reasoning
    slot_time = best["best_slot"][11:16] if best["best_slot"] else "N/A"
    parts.append(f"earliest compatible slot at {slot_time}")

    # Comparison reasoning
    if len(all_scored) > 1:
        runner_up = all_scored[1]
        score_diff = best["score"] - runner_up["score"]
        if score_diff > 10:
            parts.append(f"significantly ahead of {runner_up['provider_name']} by {score_diff:.0f} points")
        elif score_diff > 0:
            parts.append(f"slightly ahead of {runner_up['provider_name']}")

    explanation = f"{best['provider_name']} was chosen because they are " + ", ".join(parts) + "."
    return explanation
