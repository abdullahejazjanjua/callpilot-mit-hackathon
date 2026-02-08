import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.swarm import run_swarm

logger = logging.getLogger("callpilot.routes.swarm")

router = APIRouter(prefix="/swarm", tags=["Swarm Mode"])


class SwarmScheduleRequest(BaseModel):
    category: str = Field(examples=["dentists"])
    date: str = Field(examples=["2026-02-10"])
    user_location: str = "100 Market St, San Francisco, CA"
    min_rating: float = 0.0
    auto_book: bool = False
    patient_name: str = "CallPilot User"
    rating_weight: Optional[float] = None
    distance_weight: Optional[float] = None
    time_weight: Optional[float] = None


@router.post("/schedule")
async def swarm_schedule(request: SwarmScheduleRequest):
    logger.info(f"[SWARM ROUTE] Swarm request: {request.category} on {request.date}")

    weights = None
    if request.rating_weight is not None:
        weights = {
            "rating": request.rating_weight,
            "distance": request.distance_weight or 0.30,
            "time": request.time_weight or 0.30,
        }

    result = run_swarm(
        category=request.category,
        date=request.date,
        user_location=request.user_location,
        min_rating=request.min_rating,
        auto_book=request.auto_book,
        patient_name=request.patient_name,
        weights=weights,
    )

    return result


webhook_router = APIRouter(prefix="/tools", tags=["Tools (Webhook)"])


class SwarmWebhookRequest(BaseModel):
    category: str
    date: str
    user_location: str = "100 Market St, San Francisco, CA"
    min_rating: float = 0.0
    auto_book: bool = False
    patient_name: str = "CallPilot User"


@webhook_router.post("/swarm-schedule")
async def swarm_schedule_webhook(request: SwarmWebhookRequest):
    logger.info(f"[SWARM WEBHOOK] Agent triggered swarm: {request.category} on {request.date}")

    result = run_swarm(
        category=request.category,
        date=request.date,
        user_location=request.user_location,
        min_rating=request.min_rating,
        auto_book=request.auto_book,
        patient_name=request.patient_name,
    )

    if not result.get("success"):
        return {
            "success": False,
            "message": result.get("message", "No providers found"),
            "calls_made": result.get("calls_made", 0),
            "options_count": 0,
        }

    ranked = result.get("ranked_providers", [])
    best = result.get("best_match", {})

    summary_parts = []
    for i, p in enumerate(ranked[:3]):
        slot_time = p["best_slot"][11:16] if p.get("best_slot") else "N/A"
        summary_parts.append(
            f"#{i+1}: {p['provider_name']} — "
            f"{p['rating']}*, "
            f"{p['distance_km']}km away, "
            f"slot at {slot_time}, "
            f"score {p['score']}"
        )

    voice_summary = "; ".join(summary_parts)

    response = {
        "success": True,
        "calls_made": result.get("calls_made", 0),
        "options_count": len(ranked),
        "voice_summary": voice_summary,
        "recommendation": {
            "name": best.get("provider_name"),
            "rating": best.get("rating"),
            "distance_km": best.get("distance_km"),
            "travel_minutes": best.get("travel_minutes"),
            "best_slot": best.get("best_slot"),
            "score": best.get("score"),
            "phone": best.get("phone"),
            "address": best.get("address"),
        },
        "why": result.get("analysis", {}).get("best_match", {}).get("why", ""),
        "all_options": [
            {
                "rank": i + 1,
                "name": p["provider_name"],
                "rating": p["rating"],
                "distance_km": p["distance_km"],
                "best_slot": p["best_slot"],
                "score": p["score"],
            }
            for i, p in enumerate(ranked)
        ],
    }

    if result.get("booking"):
        response["booking"] = result["booking"]

    return response
