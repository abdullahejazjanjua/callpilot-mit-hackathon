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

router = APIRouter(prefix="/agent", tags=["Agent Management"])


class CreateAgentRequest(BaseModel):
    server_url: str
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"
    llm_model: Optional[str] = "gpt-4o"


class UpdateAgentRequest(BaseModel):
    server_url: str
    agent_id: Optional[str] = None
    voice_id: Optional[str] = "JBFqnCBsd6RMkjVDRZzb"
    llm_model: Optional[str] = "gpt-4o"


@router.post("/create")
async def create_agent(request: CreateAgentRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ELEVENLABS_API_KEY not set in .env file.")

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
            "message": f"Agent created! Save this agent_id to your .env file: ELEVENLABS_AGENT_ID={agent_id}",
            "server_url": request.server_url,
        }

    except Exception as e:
        logger.error(f"[AGENT] Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.post("/update")
async def update_agent(request: UpdateAgentRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ELEVENLABS_API_KEY not set in .env")

    agent_id = request.agent_id or ELEVENLABS_AGENT_ID
    if not agent_id:
        raise HTTPException(status_code=400, detail="No agent_id provided and ELEVENLABS_AGENT_ID not set in .env")

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
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ELEVENLABS_API_KEY not set in .env")

    agent_id = ELEVENLABS_AGENT_ID
    if not agent_id:
        return {
            "status": "not_configured",
            "message": "No ELEVENLABS_AGENT_ID set in .env. Create an agent first via POST /agent/create",
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


@router.get("/signed-url")
async def get_signed_url():
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=400, detail="ELEVENLABS_API_KEY not set in .env")

    agent_id = ELEVENLABS_AGENT_ID
    if not agent_id:
        raise HTTPException(status_code=400, detail="ELEVENLABS_AGENT_ID not set in .env.")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={agent_id}",
                headers={"xi-api-key": ELEVENLABS_API_KEY},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return {"signed_url": data.get("signed_url", "")}

    except httpx.HTTPStatusError as e:
        logger.error(f"[AGENT] Failed to get signed URL: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail=f"ElevenLabs API error: {e.response.text}")
    except Exception as e:
        logger.error(f"[AGENT] Failed to get signed URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ngrok-url")
async def detect_ngrok_url():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:4040/api/tunnels", timeout=3)
            tunnels = response.json().get("tunnels", [])

            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    return {
                        "ngrok_url": tunnel["public_url"],
                        "status": "active",
                    }

            if tunnels:
                return {
                    "ngrok_url": tunnels[0].get("public_url", ""),
                    "status": "active",
                }

            return {"status": "no_tunnels", "message": "ngrok is running but no tunnels found"}

    except Exception:
        return {
            "status": "not_running",
            "message": "ngrok is not running. Start it with: ngrok http 8000",
        }
