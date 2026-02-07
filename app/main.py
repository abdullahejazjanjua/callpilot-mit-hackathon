"""
CallPilot — FastAPI Entry Point
================================
This is the "front door" of your application. When you run:

    uvicorn app.main:app --reload

Uvicorn starts THIS file and serves the `app` object below.

WHAT IS FastAPI?
  FastAPI is a modern Python web framework that:
  • Handles HTTP requests (GET, POST, etc.)
  • Supports WebSockets (real-time bidirectional communication)
  • Auto-generates interactive API docs at /docs
  • Uses Python type hints for automatic request validation

ARCHITECTURE — HOW ALL THE PIECES FIT:
  ┌─────────────┐         ┌──────────────┐         ┌─────────────┐
  │   Twilio     │ ──────▶│  FastAPI      │ ──────▶│ ElevenLabs  │
  │ (phone call) │ ◀──────│  (our server) │ ◀──────│ (voice AI)  │
  └─────────────┘         └──────────────┘         └─────────────┘
                                │
                          ┌─────┴──────┐
                          ▼            ▼
                   ┌──────────┐  ┌──────────┐
                   │  /tools  │  │  /agent  │
                   │ endpoints│  │ endpoints│
                   └──────────┘  └──────────┘

ENDPOINTS OVERVIEW:
  GET  /              → Welcome message
  GET  /health        → Server status check
  GET  /docs          → Interactive Swagger API docs

  POST /tools/find-providers      → Search providers by category
  POST /tools/find-available      → Smart search (date + rating filter)
  POST /tools/provider-details    → Look up one provider by ID
  POST /tools/check-calendar      → Check if a time slot is free
  POST /tools/get-busy-slots      → List all events on a date
  POST /tools/book-appointment    → Book and confirm appointment
  POST /tools/calculate-distance  → Travel time/distance calculation

  POST /agent/create  → Create new ElevenLabs agent
  POST /agent/update  → Update agent configuration
  GET  /agent/info    → View agent status & config
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEBUG
from app.routes.tool_routes import router as tool_router
from app.routes.agent_routes import router as agent_router
from app.routes.swarm_routes import router as swarm_router
from app.routes.swarm_routes import webhook_router as swarm_webhook_router
from app.routes.call_routes import router as call_router

# ── Logging Configuration ───────────────────────────────────
# Set up logging so we can see tool calls in the terminal.
# Format: "2026-02-08 14:30:00 - callpilot.tools - INFO - [TOOL CALL] ..."
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Create the FastAPI application ──────────────────────────
app = FastAPI(
    title="CallPilot",
    description=(
        "Agentic Voice AI for Autonomous Appointment Scheduling.\n\n"
        "Powered by ElevenLabs Conversational AI + Twilio.\n\n"
        "## How it works\n"
        "1. **Create an agent** via `/agent/create` with your ngrok URL\n"
        "2. ElevenLabs voice AI handles conversations\n"
        "3. When the AI needs data, it calls the `/tools/*` endpoints\n"
        "4. Results flow back into the conversation in real-time"
    ),
    version="0.1.0",
    debug=DEBUG,
)

# ── CORS Middleware ─────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) controls which websites
# can call your API. For a hackathon, we allow everything ("*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ───────────────────────────────────────
# This is where we "plug in" the route files.
# app.include_router() takes a router and adds all its endpoints
# to the main app. After this, /tools/* and /agent/* are live.
app.include_router(tool_router)
app.include_router(agent_router)
app.include_router(swarm_router)
app.include_router(swarm_webhook_router)  # /tools/swarm-schedule webhook
app.include_router(call_router)             # /call/* phone call routes


# ── Core Endpoints ──────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Returns server status. Use this to verify the app is alive."""
    return {
        "status": "ok",
        "service": "CallPilot",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    """Welcome message with navigation links."""
    return {
        "message": "Welcome to CallPilot 🛫",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "tools": {
                "find_providers": "POST /tools/find-providers",
                "find_available": "POST /tools/find-available",
                "provider_details": "POST /tools/provider-details",
                "check_calendar": "POST /tools/check-calendar",
                "get_busy_slots": "POST /tools/get-busy-slots",
                "book_appointment": "POST /tools/book-appointment",
                "calculate_distance": "POST /tools/calculate-distance",
            },
            "agent": {
                "create": "POST /agent/create",
                "update": "POST /agent/update",
                "info": "GET /agent/info",
            },
            "swarm": {
                "schedule": "POST /swarm/schedule",
                "webhook": "POST /tools/swarm-schedule",
            },
            "calls": {
                "call_to_inquire": "POST /tools/call-to-inquire (call to ask about slots)",
                "call_provider": "POST /tools/call-provider (call to confirm booking)",
                "outbound": "POST /call/outbound",
                "twiml": "POST /call/twiml",
                "media_stream": "WS /call/media-stream",
                "status": "POST /call/status",
                "active": "GET /call/active",
            },
        },
    }


# ── Startup Event ──────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print()
    print("=" * 55)
    print("  🛫 CallPilot is starting up...")
    print("=" * 55)
    print("  📖 API Docs:    http://localhost:8000/docs")
    print("  ❤️  Health:      http://localhost:8000/health")
    print("  🔧 Tool Routes: http://localhost:8000/tools/...")
    print("  🤖 Agent Mgmt:  http://localhost:8000/agent/...")
    print("  🐝 Swarm Mode:  http://localhost:8000/swarm/...")
    print("  📞 Phone Calls: http://localhost:8000/call/...")
    print("=" * 55)

    # Show integration status
    from app.routes.call_routes import CALL_INTEGRATION_STATUS

    print("  Integration Status:")
    print(f"    📞 Phone Calls:    {CALL_INTEGRATION_STATUS}")
    print("=" * 55)
    print()
