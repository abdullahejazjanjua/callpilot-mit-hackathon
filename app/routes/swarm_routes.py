"""
CallPilot — Swarm Routes
===========================
API endpoints for Swarm Mode — autonomous multi-provider scheduling.

ENDPOINTS:
  POST /swarm/schedule     → Full autonomous scheduling (one-shot)
  POST /tools/swarm-schedule → Webhook tool version (called by ElevenLabs)

HOW SWARM MODE WORKS:
  1. User says: "Book me a dentist for Tuesday"
  2. Agent calls the swarm_schedule webhook tool
  3. Swarm orchestrator evaluates ALL providers simultaneously
  4. Returns the ranked list with the #1 recommendation
  5. Agent tells the user the result (or auto-books if configured)

WHY TWO ENDPOINTS?
  /swarm/schedule     → For direct API calls (testing, frontend)
  /tools/swarm-schedule → For ElevenLabs webhook (same logic, webhook format)
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.swarm import run_swarm

logger = logging.getLogger("callpilot.routes.swarm")

router = APIRouter(prefix="/swarm", tags=["🐝 Swarm Mode"])


# ── Request / Response Models ────────────────────────────

class SwarmScheduleRequest(BaseModel):
    """Request to run Swarm Mode autonomous scheduling."""

    category: str = Field(
        description="Service type: 'dentists', 'doctors', 'auto_repair', 'hair_salon'",
        examples=["dentists"],
    )
    date: str = Field(
        description="Target date in YYYY-MM-DD format",
        examples=["2026-02-10"],
    )
    user_location: str = Field(
        default="100 Market St, San Francisco, CA",
        description="User's address for distance calculations",
    )
    min_rating: float = Field(
        default=0.0,
        description="Minimum provider rating (0.0-5.0)",
    )
    auto_book: bool = Field(
        default=False,
        description="If true, automatically books the top-ranked provider",
    )
    patient_name: str = Field(
        default="CallPilot User",
        description="Patient name for the booking",
    )
    rating_weight: Optional[float] = Field(
        default=None,
        description="Custom weight for rating score (0.0-1.0). All weights should sum to 1.0",
    )
    distance_weight: Optional[float] = Field(
        default=None,
        description="Custom weight for distance score (0.0-1.0)",
    )
    time_weight: Optional[float] = Field(
        default=None,
        description="Custom weight for time score (0.0-1.0)",
    )


# ── Endpoints ────────────────────────────────────────────

@router.post("/schedule")
async def swarm_schedule(request: SwarmScheduleRequest):
    """
    🐝 Run Swarm Mode — autonomous appointment scheduling.

    Evaluates ALL matching providers in parallel:
    1. Checks user's calendar for conflicts
    2. Finds providers matching category, date, and rating
    3. Calculates distance from user to each provider
    4. Scores each provider (rating × 40% + proximity × 30% + earliness × 30%)
    5. Ranks by composite score
    6. Optionally auto-books the top result

    Returns the full ranked list with scores, reasoning, and decision trail.
    """
    logger.info(f"[SWARM ROUTE] 🐝 Swarm request: {request.category} on {request.date}")

    # Build custom weights if provided
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


# ── Webhook Tool version (for ElevenLabs) ────────────────
# This is the same logic but wrapped as a webhook tool endpoint
# that ElevenLabs can call during a conversation.

webhook_router = APIRouter(prefix="/tools", tags=["🔧 Tools (Webhook)"])


class SwarmWebhookRequest(BaseModel):
    """Simplified request for ElevenLabs webhook tool."""

    category: str = Field(description="Service type (e.g., 'dentists')")
    date: str = Field(description="Target date YYYY-MM-DD")
    user_location: str = Field(
        default="100 Market St, San Francisco, CA",
        description="User's address",
    )
    min_rating: float = Field(default=0.0, description="Minimum rating")
    auto_book: bool = Field(default=False, description="Auto-book top match")
    patient_name: str = Field(default="CallPilot User", description="Patient name")


@webhook_router.post("/swarm-schedule")
async def swarm_schedule_webhook(request: SwarmWebhookRequest):
    """
    Webhook tool for ElevenLabs agent — runs Swarm Mode.

    The agent calls this when the user wants the AI to find
    and evaluate all options automatically.

    Returns a simplified response optimized for voice readback.
    """
    logger.info(f"[SWARM WEBHOOK] 🐝 Agent triggered swarm: {request.category} on {request.date}")

    result = run_swarm(
        category=request.category,
        date=request.date,
        user_location=request.user_location,
        min_rating=request.min_rating,
        auto_book=request.auto_book,
        patient_name=request.patient_name,
    )

    # Simplify the response for voice readback
    if not result.get("success"):
        return {
            "success": False,
            "message": result.get("message", "No providers found"),
            "options_count": 0,
        }

    ranked = result.get("ranked_providers", [])
    best = result.get("best_match", {})

    # Build voice-friendly summary
    summary_parts = []
    for i, p in enumerate(ranked[:3]):  # Top 3 only for voice
        slot_time = p["best_slot"][11:16] if p.get("best_slot") else "N/A"
        summary_parts.append(
            f"#{i+1}: {p['provider_name']} — "
            f"{p['rating']}★, "
            f"{p['distance_km']}km away, "
            f"slot at {slot_time}, "
            f"score {p['score']}"
        )

    voice_summary = "; ".join(summary_parts)

    response = {
        "success": True,
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

    # If auto-booked, include confirmation
    if result.get("booking"):
        response["booking"] = result["booking"]

    return response
