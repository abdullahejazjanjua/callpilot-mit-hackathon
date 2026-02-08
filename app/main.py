import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEBUG, SERVER_URL, ELEVENLABS_AGENT_ID, ELEVENLABS_API_KEY
from app.routes.tool_routes import router as tool_router
from app.routes.agent_routes import router as agent_router
from app.routes.swarm_routes import router as swarm_router
from app.routes.swarm_routes import webhook_router as swarm_webhook_router
from app.routes.call_routes import router as call_router
from app.routes.event_routes import router as event_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(
    title="CallPilot",
    description="Agentic Voice AI for Autonomous Appointment Scheduling.",
    version="0.1.0",
    debug=DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tool_router)
app.include_router(agent_router)
app.include_router(swarm_router)
app.include_router(swarm_webhook_router)
app.include_router(call_router)
app.include_router(event_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "CallPilot",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {
        "message": "Welcome to CallPilot",
        "docs": "/docs",
        "health": "/health",
    }


@app.on_event("startup")
async def startup_event():
    from app.routes.call_routes import CALL_INTEGRATION_STATUS

    print()
    print("=" * 55)
    print("  CallPilot is starting up...")
    print("=" * 55)
    print(f"  API Docs:    http://localhost:8000/docs")
    print(f"  Health:      http://localhost:8000/health")
    print(f"  Phone Calls: {CALL_INTEGRATION_STATUS}")
    print("=" * 55)

    if SERVER_URL and ELEVENLABS_AGENT_ID and ELEVENLABS_API_KEY:
        if SERVER_URL != "http://localhost:8000":
            try:
                from app.agents.call_agent import update_callpilot_agent
                update_callpilot_agent(server_url=SERVER_URL, agent_id=ELEVENLABS_AGENT_ID)
                print(f"  Agent auto-updated with SERVER_URL: {SERVER_URL}")
            except Exception as e:
                print(f"  Agent auto-update failed: {e}")
    else:
        print("  Skipping agent auto-update (SERVER_URL or AGENT_ID not set)")
    print("=" * 55)
    print()
