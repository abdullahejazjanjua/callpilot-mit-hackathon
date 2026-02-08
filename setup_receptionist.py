#!/usr/bin/env python3
"""Setup script for the clinic receptionist ElevenLabs agent."""

import argparse
import sys

import httpx

from app.config import ELEVENLABS_API_KEY

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"

RECEPTIONIST_PROMPT = """
You are a professional clinic receptionist answering the phone.
You work at a medical/dental office and handle appointment confirmations and scheduling inquiries.

## YOUR BEHAVIOR
- Be warm, professional, and helpful
- Greet the caller politely: "Hello, thank you for calling. How may I help you?"
- When someone calls about an appointment, confirm the details
- If they provide appointment details (name, time, service), repeat them back clearly
- End calls politely: "Thank you for calling, have a great day!"

## WHAT YOU CAN DO
- Confirm appointments by repeating the details
- Provide general information about the clinic
- Let the caller know their appointment is confirmed and they should arrive 10 minutes early

## RULES
- Keep responses brief and professional (2-3 sentences max)
- Be natural and conversational, like a real receptionist
- If you don't understand something, ask the caller to repeat
- Always confirm the patient name, date, and time before confirming an appointment
- End the conversation after confirming the appointment details
"""

RECEPTIONIST_FIRST_MESSAGE = "Hello, thank you for calling! How may I help you today?"


def _api_headers() -> dict:
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }


def _build_receptionist_payload(name: str = "CallPilot Receptionist") -> dict:
    return {
        "name": name,
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": RECEPTIONIST_PROMPT,
                    "llm": "gpt-4o-mini",
                    "temperature": 0.6,
                    "tools": [],
                },
                "first_message": RECEPTIONIST_FIRST_MESSAGE,
                "language": "en",
            },
            "tts": {
                "model_id": "eleven_flash_v2",
                "voice_id": "EXAVITQu4vr4xnSDxMaL",
                "optimize_streaming_latency": 3,
            },
        },
    }


def create_receptionist() -> str:
    payload = _build_receptionist_payload()

    print("Creating receptionist agent on ElevenLabs...")
    response = httpx.post(
        f"{ELEVENLABS_API_BASE}/v1/convai/agents/create",
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(f"API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    data = response.json()
    agent_id = data.get("agent_id", "")

    print(f"Receptionist agent created!")
    print(f"   Agent ID: {agent_id}")
    print(f"\nAdd this to your .env file:")
    print(f"   ELEVENLABS_RECEPTIONIST_AGENT_ID={agent_id}\n")

    return agent_id


def update_receptionist(agent_id: str) -> None:
    print(f"Updating receptionist agent {agent_id}...")

    payload = _build_receptionist_payload()

    response = httpx.patch(
        f"{ELEVENLABS_API_BASE}/v1/convai/agents/{agent_id}",
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(f"API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    print(f"Receptionist agent {agent_id} updated!")


def main():
    parser = argparse.ArgumentParser(description="CallPilot Receptionist Agent Setup")
    parser.add_argument("action", choices=["create", "update"])
    parser.add_argument("--agent-id", default=None)
    args = parser.parse_args()

    if not ELEVENLABS_API_KEY:
        print("ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    if args.action == "create":
        create_receptionist()
    elif args.action == "update":
        agent_id = args.agent_id
        if not agent_id:
            from app.config import ELEVENLABS_RECEPTIONIST_AGENT_ID
            agent_id = ELEVENLABS_RECEPTIONIST_AGENT_ID
        if not agent_id:
            print("No agent_id provided. Use --agent-id or set ELEVENLABS_RECEPTIONIST_AGENT_ID in .env")
            sys.exit(1)
        update_receptionist(agent_id)


if __name__ == "__main__":
    main()
