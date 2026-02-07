"""
CallPilot — Twilio ↔ ElevenLabs WebSocket Bridge
====================================================
Bridges Twilio Media Streams to ElevenLabs Conversational AI.

When a Twilio call connects, audio flows like this:

  Caller's Phone ←→ Twilio ←→ [THIS BRIDGE] ←→ ElevenLabs ConvAI Agent
                     mulaw      converts         PCM16
                     8kHz       audio             16kHz
                                format

TWILIO MEDIA STREAMS PROTOCOL:
  Twilio sends/receives JSON messages with base64 mulaw audio at 8kHz:
  → {"event": "media", "media": {"payload": "<base64 mulaw>"}}

ELEVENLABS CONVAI PROTOCOL:
  ElevenLabs sends/receives JSON messages with base64 PCM16 audio:
  → {"user_audio_chunk": "<base64 pcm16>"}
  ← {"type": "audio", "audio_event": {"audio_base_64": "<base64 pcm16>"}}
"""

import asyncio
import audioop
import base64
import json
import logging
from typing import Optional

import websockets
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.config import ELEVENLABS_API_KEY

logger = logging.getLogger("callpilot.bridge")

ELEVENLABS_WS_BASE = "wss://api.elevenlabs.io/v1/convai/conversation"


async def bridge_twilio_to_elevenlabs(
    twilio_ws: WebSocket,
    agent_id: str,
    system_prompt_override: Optional[str] = None,
    first_message: Optional[str] = None,
) -> dict:
    """
    Bridge a Twilio Media Stream WebSocket to an ElevenLabs ConvAI agent.

    This function runs for the duration of the phone call, forwarding
    audio between Twilio and ElevenLabs in real-time.

    Args:
        twilio_ws: The Twilio WebSocket connection (from FastAPI)
        agent_id: ElevenLabs agent ID (receptionist)
        system_prompt_override: Optional override for the agent's system prompt
        first_message: Optional override for the agent's first message

    Returns:
        dict with conversation_id and transcript
    """
    elevenlabs_url = f"{ELEVENLABS_WS_BASE}?agent_id={agent_id}"
    stream_sid: Optional[str] = None
    conversation_id: Optional[str] = None
    transcript: list[dict] = []
    last_interrupt_id = 0

    logger.info(f"[BRIDGE] Connecting to ElevenLabs agent {agent_id}...")

    try:
        async with websockets.connect(
            elevenlabs_url,
            additional_headers={"xi-api-key": ELEVENLABS_API_KEY},
        ) as el_ws:
            logger.info("[BRIDGE] ✅ Connected to ElevenLabs ConvAI!")

            # ── Send conversation initiation ───────────────
            init_data: dict = {
                "type": "conversation_initiation_client_data",
                "custom_llm_extra_body": {},
                "conversation_config_override": {},
            }

            # Override prompt/first_message if provided
            if system_prompt_override or first_message:
                override: dict = {"agent": {}}
                if system_prompt_override:
                    override["agent"]["prompt"] = {"prompt": system_prompt_override}
                if first_message:
                    override["agent"]["first_message"] = first_message
                init_data["conversation_config_override"] = override

            await el_ws.send(json.dumps(init_data))
            logger.info("[BRIDGE] Sent conversation initiation to ElevenLabs")

            # ── Forward Twilio → ElevenLabs ────────────────
            async def twilio_to_elevenlabs():
                nonlocal stream_sid
                try:
                    while True:
                        raw = await twilio_ws.receive_text()
                        data = json.loads(raw)

                        if data["event"] == "start":
                            stream_sid = data["start"]["streamSid"]
                            logger.info(f"[BRIDGE] 📞 Twilio stream started: {stream_sid}")

                        elif data["event"] == "media":
                            # Twilio → mulaw 8kHz → PCM16 16kHz → ElevenLabs
                            mulaw_bytes = base64.b64decode(data["media"]["payload"])
                            # Decode mulaw to PCM16
                            pcm_8k = audioop.ulaw2lin(mulaw_bytes, 2)
                            # Upsample 8kHz → 16kHz
                            pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
                            # Send to ElevenLabs
                            await el_ws.send(json.dumps({
                                "user_audio_chunk": base64.b64encode(pcm_16k).decode()
                            }))

                        elif data["event"] == "stop":
                            logger.info("[BRIDGE] 📞 Twilio stream stopped")
                            break

                except WebSocketDisconnect:
                    logger.info("[BRIDGE] Twilio WebSocket disconnected")
                except Exception as e:
                    logger.error(f"[BRIDGE] Error in twilio_to_elevenlabs: {e}")

            # ── Forward ElevenLabs → Twilio ────────────────
            async def elevenlabs_to_twilio():
                nonlocal conversation_id, last_interrupt_id
                try:
                    async for raw in el_ws:
                        data = json.loads(raw)
                        msg_type = data.get("type", "")

                        if msg_type == "conversation_initiation_metadata":
                            event = data["conversation_initiation_metadata_event"]
                            conversation_id = event["conversation_id"]
                            logger.info(f"[BRIDGE] Conversation ID: {conversation_id}")

                        elif msg_type == "audio":
                            event = data["audio_event"]
                            if int(event["event_id"]) <= last_interrupt_id:
                                continue
                            # ElevenLabs → PCM16 16kHz → mulaw 8kHz → Twilio
                            pcm_16k = base64.b64decode(event["audio_base_64"])
                            # Downsample 16kHz → 8kHz
                            pcm_8k, _ = audioop.ratecv(pcm_16k, 2, 1, 16000, 8000, None)
                            # Encode PCM16 to mulaw
                            mulaw_bytes = audioop.lin2ulaw(pcm_8k, 2)
                            # Send to Twilio
                            if stream_sid:
                                await twilio_ws.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": base64.b64encode(mulaw_bytes).decode()
                                    }
                                })

                        elif msg_type == "agent_response":
                            agent_text = data["agent_response_event"]["agent_response"].strip()
                            transcript.append({"role": "agent", "text": agent_text})
                            logger.info(f"[BRIDGE] 🤖 Receptionist: {agent_text}")

                        elif msg_type == "user_transcript":
                            user_text = data["user_transcription_event"]["user_transcript"].strip()
                            transcript.append({"role": "user", "text": user_text})
                            logger.info(f"[BRIDGE] 👤 Caller: {user_text}")

                        elif msg_type == "interruption":
                            last_interrupt_id = int(data["interruption_event"]["event_id"])

                        elif msg_type == "ping":
                            await el_ws.send(json.dumps({
                                "type": "pong",
                                "event_id": data["ping_event"]["event_id"],
                            }))

                except websockets.exceptions.ConnectionClosed:
                    logger.info("[BRIDGE] ElevenLabs WebSocket closed")
                except Exception as e:
                    logger.error(f"[BRIDGE] Error in elevenlabs_to_twilio: {e}")

            # ── Run both directions concurrently ───────────
            await asyncio.gather(
                twilio_to_elevenlabs(),
                elevenlabs_to_twilio(),
            )

    except Exception as e:
        logger.error(f"[BRIDGE] Failed to connect to ElevenLabs: {e}")

    result = {
        "conversation_id": conversation_id,
        "transcript": transcript,
        "message_count": len(transcript),
    }
    logger.info(f"[BRIDGE] Call ended. {len(transcript)} messages exchanged.")
    return result
