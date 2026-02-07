"""
CallPilot — Agent Management Routes
=====================================
These endpoints let you create, update, and inspect the ElevenLabs
Conversational AI agent from the API (instead of running scripts manually).

WHY API ENDPOINTS?
  During a hackathon demo, you want to be able to:
  • Create the agent with one button click (not a terminal command)
  • Update the agent if you change the prompt or tools
  • Check the agent status to verify it's configured correctly

  These endpoints also make it easy to show the judges how
  the agent is configured — just hit /agent/info in the browser.

ENDPOINTS:
  POST /agent/create    → Create a new CallPilot agent
  POST /agent/update    → Update an existing agent's config
  GET  /agent/info      → View current agent configuration
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.call_agent import (
    create_callpilot_agent,
    get_agent_info,
    update_callpilot_agent,
)
from app.config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID

logger = logging.getLogger("callpilot.agent")

router = APIRouter(
    prefix="/agent",
    tags=["Agent Management"],
)


# ── Request Models ──────────────────────────────────────────

class CreateAgentRequest(BaseModel):
    """Request body to create a new agent."""
    server_url: str = Field(
        description=(
            "Public URL of your FastAPI server. "
            "ElevenLabs needs to reach your /tools/* endpoints, "
            "so this must be a public URL (e.g., from ngrok). "
            "Example: 'https://abc123.ngrok.io'"
        )
    )
    voice_id: Optional[str] = Field(
        default="JBFqnCBsd6RMkjVDRZzb",
        description="ElevenLabs voice ID. Default: 'George' (professional male)",
    )
    llm_model: Optional[str] = Field(
        default="gpt-4o",
        description="LLM model for the agent. Options: gpt-4o, gpt-4o-mini, claude-3-5-sonnet",
    )


class UpdateAgentRequest(BaseModel):
    """Request body to update an existing agent."""
    server_url: str = Field(description="New public URL for webhook tools")
    agent_id: Optional[str] = Field(
        default=None,
        description="Agent ID to update. Defaults to ELEVENLABS_AGENT_ID from .env",
    )
    voice_id: Optional[str] = Field(
        default="JBFqnCBsd6RMkjVDRZzb",
        description="ElevenLabs voice ID",
    )
    llm_model: Optional[str] = Field(
        default="gpt-4o",
        description="LLM model name",
    )


# ── Endpoints ───────────────────────────────────────────────

@router.post("/create")
async def create_agent(request: CreateAgentRequest):
    """
    Create a new CallPilot agent on ElevenLabs.

    This is a ONE-TIME setup. After creating the agent:
    1. Copy the returned agent_id
    2. Paste it into your .env file as ELEVENLABS_AGENT_ID
    3. Restart the server

    The agent will be configured with:
    - The CallPilot system prompt (personality + rules)
    - All 7 webhook tools pointing to {server_url}/tools/*
    - The selected voice and LLM model
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="ELEVENLABS_API_KEY not set in .env file. Get your key from https://elevenlabs.io/app/settings/api-keys",
        )

    logger.info(f"[AGENT] Creating new agent with server_url={request.server_url}")

    try:
        agent_id = create_callpilot_agent(
            server_url=request.server_url,
            voice_id=request.voice_id or "JBFqnCBsd6RMkjVDRZzb",
            llm_model=request.llm_model or "gpt-4o",
        )

        return {
            "success": True,
            "agent_id": agent_id,
            "message": (
                f"Agent created! Save this agent_id to your .env file: "
                f"ELEVENLABS_AGENT_ID={agent_id}"
            ),
            "server_url": request.server_url,
            "next_steps": [
                f"1. Add ELEVENLABS_AGENT_ID={agent_id} to your .env file",
                "2. Restart the server",
                "3. Test the agent at https://elevenlabs.io/app/conversational-ai",
            ],
        }

    except Exception as e:
        logger.error(f"[AGENT] Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.post("/update")
async def update_agent(request: UpdateAgentRequest):
    """
    Update an existing CallPilot agent's configuration.

    Use this when you:
    - Change the system prompt
    - Get a new ngrok URL (they change on restart)
    - Switch the voice or LLM model
    - Modify tool definitions

    You DON'T need to create a new agent — just update!
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="ELEVENLABS_API_KEY not set in .env",
        )

    agent_id = request.agent_id or ELEVENLABS_AGENT_ID
    if not agent_id:
        raise HTTPException(
            status_code=400,
            detail="No agent_id provided and ELEVENLABS_AGENT_ID not set in .env",
        )

    logger.info(f"[AGENT] Updating agent {agent_id} with server_url={request.server_url}")

    try:
        update_callpilot_agent(
            server_url=request.server_url,
            agent_id=agent_id,
            voice_id=request.voice_id or "JBFqnCBsd6RMkjVDRZzb",
            llm_model=request.llm_model or "gpt-4o",
        )

        return {
            "success": True,
            "agent_id": agent_id,
            "message": f"Agent {agent_id} updated successfully",
            "server_url": request.server_url,
        }

    except Exception as e:
        logger.error(f"[AGENT] Failed to update agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@router.get("/info")
async def agent_info():
    """
    Get current configuration of the CallPilot agent.

    Shows: agent name, system prompt, tools, voice, and LLM model.
    Useful for debugging and verifying the agent is set up correctly.
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="ELEVENLABS_API_KEY not set in .env",
        )

    agent_id = ELEVENLABS_AGENT_ID
    if not agent_id:
        return {
            "status": "not_configured",
            "message": (
                "No ELEVENLABS_AGENT_ID set in .env. "
                "Create an agent first via POST /agent/create"
            ),
        }

    try:
        info = get_agent_info(agent_id)
        return {
            "status": "configured",
            "agent_id": agent_id,
            "info": info,
        }

    except Exception as e:
        logger.error(f"[AGENT] Failed to get agent info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent info: {str(e)}")


@router.get("/ngrok-url")
async def detect_ngrok_url():
    """
    Auto-detect the running ngrok tunnel URL.

    ngrok exposes a local API at http://localhost:4040/api/tunnels
    that lists all active tunnels. This endpoint reads that and
    returns the public HTTPS URL.

    Use this to quickly grab your ngrok URL without copy-pasting.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:4040/api/tunnels", timeout=3)
            tunnels = response.json().get("tunnels", [])

            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    return {
                        "ngrok_url": tunnel["public_url"],
                        "status": "active",
                        "message": f"Use this as your server_url: {tunnel['public_url']}",
                    }

            if tunnels:
                return {
                    "ngrok_url": tunnels[0].get("public_url", ""),
                    "status": "active",
                    "message": "Found tunnel (non-HTTPS)",
                }

            return {"status": "no_tunnels", "message": "ngrok is running but no tunnels found"}

    except Exception:
        return {
            "status": "not_running",
            "message": (
                "ngrok is not running. Start it with: ngrok http 8000\n"
                "Then re-visit this endpoint to auto-detect the URL."
            ),
        }
