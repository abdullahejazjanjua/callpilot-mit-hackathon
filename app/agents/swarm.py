import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from app.tools.calendar_tool import check_availability, get_busy_slots, book_appointment
from app.tools.call_tool import call_to_inquire
from app.tools.distance_tool import calculate_distance
from app.tools.provider_tool import find_providers
from app.events import emit

logger = logging.getLogger("callpilot.swarm")

MAX_PARALLEL_CALLS = 15

DEFAULT_WEIGHTS = {
    "rating": 0.40,
    "distance": 0.30,
    "time": 0.30,
}


def _score_rating(rating: float) -> float:
    return (rating / 5.0) * 100


def _score_distance(distance_km: float) -> float:
    return max(0, 100 - distance_km * 4)


def _score_time(slot_str: str) -> float:
    try:
        slot_time = datetime.fromisoformat(slot_str)
        now = datetime.now()
        hours_away = max(0, (slot_time - now).total_seconds() / 3600)
        return max(0, 100 - hours_away * 1.0)
    except (ValueError, TypeError):
        return 50


def score_provider(
    provider: dict,
    distance_km: float,
    best_slot: str,
    weights: Optional[dict] = None,
) -> float:
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


def _call_single_provider(
    provider: dict,
    date: str,
    service_type: str,
    patient_name: str,
) -> dict:
    provider_name = provider.get("name", "Unknown")
    provider_phone = provider.get("phone", "")

    try:
        result = call_to_inquire(
            provider_phone=provider_phone,
            provider_name=provider_name,
            date=date,
            service_type=service_type,
            patient_name=patient_name,
        )

        return {
            "provider": provider,
            "call_success": result.get("success", False),
            "call_sid": result.get("call_sid", ""),
            "available_slots": [
                s["datetime"] for s in result.get("available_slots", [])
            ],
            "slot_count": result.get("slot_count", 0),
        }
    except Exception as e:
        logger.error(f"[SWARM] Call to {provider_name} failed: {e}")
        return {
            "provider": provider,
            "call_success": False,
            "call_sid": "",
            "available_slots": [],
            "slot_count": 0,
        }


def _calculate_single_distance(provider: dict, user_location: str) -> dict:
    try:
        dist = calculate_distance(
            user_location=user_location,
            provider_address=provider.get("address", ""),
            provider_id=provider.get("id", ""),
            provider_name=provider.get("name", ""),
        )
        return {
            "provider_name": provider.get("name", ""),
            "distance_km": dist["distance_km"],
            "duration_minutes": dist["duration_minutes"],
        }
    except Exception as e:
        logger.error(f"[SWARM] Distance calc failed for {provider.get('name')}: {e}")
        return {
            "provider_name": provider.get("name", ""),
            "distance_km": 10.0,
            "duration_minutes": 15,
        }


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
    Multi-call parallel outreach for autonomous scheduling.
    Simultaneously calls up to 15 providers, scores them, and returns a ranked shortlist.
    """
    logger.info(f"[SWARM] Starting parallel outreach for '{category}' on {date}")
    logger.info(f"[SWARM]    Location: {user_location}")
    logger.info(f"[SWARM]    Min rating: {min_rating}, Auto-book: {auto_book}")
    emit(f"Swarm started: finding {category} on {date}", "info", "swarm")
    emit(f"Location: {user_location}", "system", "swarm")

    decision_trail = []

    # Step 1: Check user's calendar
    logger.info("[SWARM] Step 1: Checking user's calendar...")
    calendar = get_busy_slots(date)
    busy_slots = calendar.get("busy_slots", [])

    decision_trail.append({
        "step": 1,
        "action": "check_calendar",
        "result": f"Found {len(busy_slots)} event(s) on {date}",
        "details": busy_slots,
    })

    logger.info(f"[SWARM]    -> {len(busy_slots)} existing event(s) on {date}")
    emit(f"Calendar check: {len(busy_slots)} existing event(s) on {date}", "info", "calendar")

    # Step 2: Find matching providers
    logger.info(f"[SWARM] Step 2: Finding up to {MAX_PARALLEL_CALLS} providers...")
    provider_result = find_providers(
        category=category,
        location=user_location,
        limit=MAX_PARALLEL_CALLS,
    )

    providers = provider_result.get("providers", [])

    if min_rating > 0:
        providers = [p for p in providers if p.get("rating", 0) >= min_rating]

    decision_trail.append({
        "step": 2,
        "action": "find_providers",
        "result": f"Found {len(providers)} provider(s) in '{category}'",
        "filters": {"date": date, "min_rating": min_rating},
        "source": provider_result.get("source", "unknown"),
    })

    emit(f"Found {len(providers)} provider(s) matching '{category}'", "info", "swarm")

    if not providers:
        logger.warning("[SWARM]    -> No providers found. Swarm complete (empty).")
        emit(f"No {category} found in the area", "error", "swarm")
        return {
            "success": False,
            "message": f"No {category} found in the area (min rating: {min_rating})",
            "ranked_providers": [],
            "best_match": None,
            "booking": None,
            "calls_made": 0,
            "decision_trail": decision_trail,
        }

    logger.info(f"[SWARM]    -> {len(providers)} provider(s) found")

    # Step 3: Parallel outreach — call all providers + calculate distances
    logger.info(f"[SWARM] Step 3: Calling {len(providers)} providers in parallel...")
    emit(f"Calling {len(providers)} providers in parallel...", "warning", "call")

    call_results = {}
    distance_results = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_CALLS) as executor:
        call_futures = {
            executor.submit(
                _call_single_provider, provider, date, category, patient_name
            ): provider
            for provider in providers
        }

        dist_futures = {
            executor.submit(
                _calculate_single_distance, provider, user_location
            ): provider
            for provider in providers
        }

        for future in as_completed(call_futures):
            provider = call_futures[future]
            result = future.result()
            call_results[provider["name"]] = result
            status = f"{result['slot_count']} slot(s)" if result["call_success"] else "FAILED"
            logger.info(f"[SWARM]    Call {result.get('call_sid', 'N/A')}: {provider['name']} -> {status}")

        for future in as_completed(dist_futures):
            provider = dist_futures[future]
            result = future.result()
            distance_results[provider["name"]] = result

    calls_made = sum(1 for r in call_results.values() if r["call_success"])

    decision_trail.append({
        "step": 3,
        "action": "parallel_outreach",
        "result": f"Called {len(providers)} providers, {calls_made} successful",
        "calls": [
            {
                "provider": name,
                "call_sid": r.get("call_sid", ""),
                "slots_found": r["slot_count"],
                "success": r["call_success"],
            }
            for name, r in call_results.items()
        ],
    })

    logger.info(f"[SWARM]    -> {calls_made}/{len(providers)} calls successful")
    emit(f"Calls complete: {calls_made}/{len(providers)} successful", "success", "call")

    decision_trail.append({
        "step": 4,
        "action": "calculate_distances",
        "result": f"Calculated distances for {len(distance_results)} providers",
        "distances": [
            {"provider": name, "distance_km": r["distance_km"], "travel_min": r["duration_minutes"]}
            for name, r in distance_results.items()
        ],
    })

    # Step 5: Score each provider
    logger.info("[SWARM] Step 5: Scoring all providers...")
    emit("Scoring and ranking providers...", "info", "swarm")
    scored_providers = []

    for provider in providers:
        name = provider["name"]

        cr = call_results.get(name, {})
        if not cr.get("call_success") or cr.get("slot_count", 0) == 0:
            decision_trail.append({
                "step": 5,
                "action": "score_provider",
                "provider": name,
                "result": "SKIPPED — no available slots from call",
            })
            logger.info(f"[SWARM]    x {name}: no slots, skipping")
            continue

        available_slots = cr.get("available_slots", [])

        dr = distance_results.get(name, {"distance_km": 10.0, "duration_minutes": 15})
        distance_km = dr["distance_km"]
        travel_min = dr["duration_minutes"]

        best_slot = None
        compatible_slots = []

        for slot in available_slots:
            avail = check_availability(slot)
            if avail["is_available"]:
                compatible_slots.append(slot)
                if best_slot is None:
                    best_slot = slot

        if not compatible_slots:
            decision_trail.append({
                "step": 5,
                "action": "score_provider",
                "provider": name,
                "result": "SKIPPED — all slots conflict with calendar",
                "slots_checked": len(available_slots),
            })
            logger.info(f"[SWARM]    x {name}: all slots conflict, skipping")
            continue

        provider_score = score_provider(
            provider=provider,
            distance_km=distance_km,
            best_slot=best_slot,
            weights=weights,
        )

        scored_entry = {
            "provider_id": provider.get("id", ""),
            "provider_name": name,
            "phone": provider.get("phone", ""),
            "address": provider.get("address", ""),
            "rating": provider.get("rating", 0.0),
            "distance_km": distance_km,
            "travel_minutes": travel_min,
            "best_slot": best_slot,
            "compatible_slots": compatible_slots,
            "call_sid": cr.get("call_sid", ""),
            "score": provider_score,
            "score_breakdown": {
                "rating_score": round(_score_rating(provider.get("rating", 0)), 1),
                "distance_score": round(_score_distance(distance_km), 1),
                "time_score": round(_score_time(best_slot), 1),
            },
        }

        scored_providers.append(scored_entry)

        decision_trail.append({
            "step": 5,
            "action": "score_provider",
            "provider": name,
            "score": provider_score,
            "distance_km": distance_km,
            "best_slot": best_slot,
            "compatible_slots_count": len(compatible_slots),
        })

        logger.info(
            f"[SWARM]    + {name}: "
            f"score={provider_score}, "
            f"rating={provider.get('rating', 0)}*, "
            f"dist={distance_km}km, "
            f"best_slot={best_slot[11:16] if best_slot else 'N/A'}"
        )

    # Step 6: Rank by score
    scored_providers.sort(key=lambda p: p["score"], reverse=True)

    if not scored_providers:
        logger.warning("[SWARM]    -> No compatible providers after filtering.")
        emit("No compatible providers found after filtering", "error", "swarm")
        return {
            "success": False,
            "message": (
                f"Called {calls_made} provider(s) but no compatible slots found. "
                f"All slots either unavailable or conflict with your calendar."
            ),
            "ranked_providers": [],
            "best_match": None,
            "booking": None,
            "calls_made": calls_made,
            "decision_trail": decision_trail,
        }

    best = scored_providers[0]

    decision_trail.append({
        "step": 6,
        "action": "rank_providers",
        "result": f"Best match: {best['provider_name']} (score: {best['score']})",
        "ranking": [
            {"rank": i + 1, "name": p["provider_name"], "score": p["score"]}
            for i, p in enumerate(scored_providers)
        ],
    })

    logger.info(f"[SWARM] Step 6: Ranking complete -> #1 {best['provider_name']} (score {best['score']})")
    emit(
        f"Ranking complete — #{1} {best['provider_name']} "
        f"(score {best['score']}, {best['rating']}*, {best['distance_km']}km)",
        "success",
        "swarm",
    )

    # Step 7: Auto-book if requested
    booking_result = None

    if auto_book:
        logger.info(f"[SWARM] Step 7: Auto-booking {best['provider_name']} at {best['best_slot']}...")

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
            "step": 7,
            "action": "auto_book",
            "provider": best["provider_name"],
            "slot": best["best_slot"],
            "success": booking_result.get("success", False),
            "message": booking_result.get("message", ""),
        })

        if booking_result.get("success"):
            logger.info(f"[SWARM]    Booked! {booking_result['message']}")
            emit(f"Auto-booked: {best['provider_name']} — {booking_result['message']}", "success", "swarm")
        else:
            logger.warning(f"[SWARM]    Booking failed: {booking_result['message']}")
            emit(f"Booking failed: {booking_result['message']}", "error", "swarm")
    else:
        decision_trail.append({
            "step": 7,
            "action": "present_options",
            "result": "Auto-book disabled — returning ranked list for user choice",
        })

    analysis = {
        "providers_found": len(providers),
        "calls_made": calls_made,
        "providers_with_slots": sum(1 for r in call_results.values() if r["slot_count"] > 0),
        "providers_compatible": len(scored_providers),
        "providers_skipped_no_slots": sum(1 for r in call_results.values() if r["slot_count"] == 0),
        "providers_skipped_conflicts": (
            sum(1 for r in call_results.values() if r["slot_count"] > 0)
            - len(scored_providers)
        ),
        "calendar_conflicts": len(busy_slots),
        "best_match": {
            "name": best["provider_name"],
            "score": best["score"],
            "why": _explain_choice(best, scored_providers),
        },
    }

    logger.info(
        f"[SWARM] Swarm complete — called {calls_made} providers, "
        f"{len(scored_providers)} compatible, best: {best['provider_name']}"
    )

    return {
        "success": True,
        "message": (
            f"Called {calls_made} provider(s) simultaneously. "
            f"Found {len(scored_providers)} compatible option(s) with open slots."
        ),
        "ranked_providers": scored_providers,
        "best_match": best,
        "booking": booking_result,
        "calls_made": calls_made,
        "analysis": analysis,
        "decision_trail": decision_trail,
    }


def _explain_choice(best: dict, all_scored: list) -> str:
    parts = []

    if best["rating"] >= 4.5:
        parts.append(f"highly rated at {best['rating']}*")
    elif best["rating"] >= 4.0:
        parts.append(f"well rated at {best['rating']}*")
    else:
        parts.append(f"rated {best['rating']}*")

    if best["distance_km"] <= 5:
        parts.append(f"very close at {best['distance_km']}km ({best['travel_minutes']} min drive)")
    elif best["distance_km"] <= 15:
        parts.append(f"reasonably close at {best['distance_km']}km ({best['travel_minutes']} min drive)")
    else:
        parts.append(f"{best['distance_km']}km away ({best['travel_minutes']} min drive)")

    slot_time = best["best_slot"][11:16] if best["best_slot"] else "N/A"
    parts.append(f"earliest compatible slot at {slot_time}")

    if len(all_scored) > 1:
        runner_up = all_scored[1]
        score_diff = best["score"] - runner_up["score"]
        if score_diff > 10:
            parts.append(f"significantly ahead of {runner_up['provider_name']} by {score_diff:.0f} points")
        elif score_diff > 0:
            parts.append(f"slightly ahead of {runner_up['provider_name']}")

    explanation = f"{best['provider_name']} was chosen because they are " + ", ".join(parts) + "."
    return explanation
