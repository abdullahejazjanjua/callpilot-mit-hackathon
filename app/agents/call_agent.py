from typing import Optional

import httpx

from app.agents.prompts import get_system_prompt, FIRST_MESSAGE
from app.config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"


def _build_webhook_tool(
    name: str,
    description: str,
    server_url: str,
    endpoint: str,
    method: str = "POST",
    properties: Optional[dict] = None,
    required: Optional[list] = None,
) -> dict:
    tool = {
        "type": "webhook",
        "name": name,
        "description": description,
        "api_schema": {
            "url": f"{server_url}{endpoint}",
            "method": method,
        },
    }

    if properties:
        schema_properties = {}
        for prop_name, prop_config in properties.items():
            schema_properties[prop_name] = {
                "type": prop_config["type"],
                "description": prop_config.get("description", ""),
            }

        tool["api_schema"]["request_body_schema"] = {
            "type": "object",
            "properties": schema_properties,
            "required": required or [],
        }

    return tool


def build_tool_definitions(server_url: str) -> list[dict]:
    tools = [
        _build_webhook_tool(
            name="find_providers",
            description=(
                "Search for service providers by category. "
                "Categories: 'dentists', 'doctors', 'auto_repair', 'hair_salon'. "
                "Pass location (e.g. city or address) for real Google Places results; "
                "otherwise uses fallback data. "
                "Returns provider names, ratings, phone numbers, and addresses. "
                "Does NOT return available slots — you must use call_to_inquire to CALL them and get slots."
            ),
            server_url=server_url,
            endpoint="/tools/find-providers",
            properties={
                "category": {
                    "type": "string",
                    "description": "Service category (e.g., 'dentists', 'doctors', 'auto_repair', 'hair_salon')",
                },
                "location": {
                    "type": "string",
                    "description": "City or address for Places search (e.g. 'San Francisco', 'Lahore')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of providers to return (default 5)",
                },
            },
            required=["category"],
        ),
        _build_webhook_tool(
            name="call_to_inquire",
            description=(
                "Call a provider to ask about available appointment slots. "
                "This makes a phone call via Twilio. "
                "Use this AFTER find_providers to discover what slots are available. "
                "Returns the provider's available slots for the requested date, "
                "plus the call SID as proof the call was made. "
                "You MUST call this before presenting any available times to the user."
            ),
            server_url=server_url,
            endpoint="/tools/call-to-inquire",
            properties={
                "provider_phone": {
                    "type": "string",
                    "description": "Provider's phone number in E.164 format (e.g., '+923107696477')",
                },
                "provider_name": {
                    "type": "string",
                    "description": "Provider's business name",
                },
                "date": {
                    "type": "string",
                    "description": "Date to check in YYYY-MM-DD format (e.g., '2026-02-09')",
                },
                "service_type": {
                    "type": "string",
                    "description": "Type of service (e.g., 'dentist', 'doctor')",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient's name (introduced on the call)",
                },
            },
            required=["provider_phone", "provider_name", "date"],
        ),
        _build_webhook_tool(
            name="get_provider_details",
            description=(
                "Look up detailed information about a specific provider by their ID. "
                "Returns full details including name, phone, address, rating, and all available slots."
            ),
            server_url=server_url,
            endpoint="/tools/provider-details",
            properties={
                "provider_id": {
                    "type": "string",
                    "description": "Unique provider ID (e.g., 'd1', 'doc2', 'hs1')",
                },
            },
            required=["provider_id"],
        ),
        _build_webhook_tool(
            name="check_calendar",
            description=(
                "Check if a specific time slot is free on the user's calendar. "
                "ALWAYS call this before confirming any appointment. "
                "Returns whether the slot is available and, if not, what event conflicts."
            ),
            server_url=server_url,
            endpoint="/tools/check-calendar",
            properties={
                "slot": {
                    "type": "string",
                    "description": "Time slot in ISO-8601 format (e.g., '2026-02-10T14:00:00')",
                },
            },
            required=["slot"],
        ),
        _build_webhook_tool(
            name="get_busy_slots",
            description=(
                "Get all busy time slots for a specific date on the user's calendar. "
                "Use this proactively at the start of a conversation to understand "
                "the user's schedule and avoid suggesting conflicting times."
            ),
            server_url=server_url,
            endpoint="/tools/get-busy-slots",
            properties={
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (e.g., '2026-02-10')",
                },
            },
            required=["date"],
        ),
        _build_webhook_tool(
            name="book_appointment",
            description=(
                "Book an appointment with a provider. "
                "ONLY call this after: (1) the user approved the provider, "
                "(2) you verified the slot is free with check_calendar, "
                "(3) the user explicitly confirmed the booking. "
                "Returns confirmation details including provider name, time, and address."
            ),
            server_url=server_url,
            endpoint="/tools/book-appointment",
            properties={
                "provider_id": {
                    "type": "string",
                    "description": "Provider's unique ID",
                },
                "provider_name": {
                    "type": "string",
                    "description": "Provider's business name",
                },
                "provider_phone": {
                    "type": "string",
                    "description": "Provider's phone number",
                },
                "provider_address": {
                    "type": "string",
                    "description": "Provider's address",
                },
                "slot": {
                    "type": "string",
                    "description": "Appointment time in ISO-8601 format",
                },
                "service_type": {
                    "type": "string",
                    "description": "Type of service (e.g., 'dentists')",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient's name for the booking",
                },
            },
            required=["provider_name", "provider_phone", "provider_address", "slot"],
        ),
        _build_webhook_tool(
            name="calculate_distance",
            description=(
                "Calculate the travel distance and estimated time between "
                "the user's location and a provider's address."
            ),
            server_url=server_url,
            endpoint="/tools/calculate-distance",
            properties={
                "user_location": {
                    "type": "string",
                    "description": "User's current address or location",
                },
                "provider_address": {
                    "type": "string",
                    "description": "Provider's address",
                },
                "provider_id": {
                    "type": "string",
                    "description": "Provider's unique ID",
                },
                "provider_name": {
                    "type": "string",
                    "description": "Provider's name",
                },
            },
            required=["user_location", "provider_address"],
        ),
        _build_webhook_tool(
            name="call_provider",
            description=(
                "Call a provider to CONFIRM a booked appointment. "
                "Use this AFTER booking when the user wants to confirm by phone. "
                "This is different from call_to_inquire — this is for CONFIRMATION only."
            ),
            server_url=server_url,
            endpoint="/tools/call-provider",
            properties={
                "provider_phone": {
                    "type": "string",
                    "description": "Provider's phone number in E.164 format (e.g., '+923107696477')",
                },
                "provider_name": {
                    "type": "string",
                    "description": "Provider's business name",
                },
                "appointment_time": {
                    "type": "string",
                    "description": "Appointment time (human-readable, e.g., 'Tuesday February 10 at 2pm')",
                },
                "service_type": {
                    "type": "string",
                    "description": "Type of service (e.g., 'dentist', 'doctor')",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient's name",
                },
            },
            required=["provider_phone", "provider_name", "appointment_time"],
        ),
        _build_webhook_tool(
            name="swarm_schedule",
            description=(
                "SWARM MODE — Autonomous multi-provider scheduling. "
                "Evaluates ALL matching providers at once: "
                "checks the user's calendar, calculates distances, scores each provider "
                "(40% rating + 30% proximity + 30% slot earliness), and returns a ranked list. "
                "Optionally auto-books the top result. "
                "Use this instead of calling find_providers + check_calendar + calculate_distance "
                "one by one — it does everything in one shot."
            ),
            server_url=server_url,
            endpoint="/tools/swarm-schedule",
            properties={
                "category": {
                    "type": "string",
                    "description": "Service type (e.g., 'dentists', 'doctors', 'auto_repair', 'hair_salon')",
                },
                "date": {
                    "type": "string",
                    "description": "Target date in YYYY-MM-DD format",
                },
                "user_location": {
                    "type": "string",
                    "description": "User's address for distance calculation",
                },
                "min_rating": {
                    "type": "number",
                    "description": "Minimum provider rating (0.0-5.0)",
                },
                "auto_book": {
                    "type": "boolean",
                    "description": "If true, automatically book the top-ranked provider",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient name for the booking",
                },
            },
            required=["category", "date"],
        ),
    ]

    return tools


def _build_agent_payload(
    server_url: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    llm_model: str = "gpt-4o",
    name: str = "CallPilot - Appointment Scheduler",
) -> dict:
    tools = build_tool_definitions(server_url)

    return {
        "name": name,
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": get_system_prompt(),
                    "llm": llm_model,
                    "temperature": 0.7,
                    "tools": tools,
                },
                "first_message": FIRST_MESSAGE,
                "language": "en",
            },
            "tts": {
                "model_id": "eleven_flash_v2",
                "voice_id": voice_id,
                "optimize_streaming_latency": 3,
            },
        },
    }


def _api_headers() -> dict:
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }


def create_callpilot_agent(
    server_url: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    llm_model: str = "gpt-4o",
) -> str:
    """Create a CallPilot agent on ElevenLabs and return its agent ID."""
    payload = _build_agent_payload(server_url, voice_id, llm_model)

    response = httpx.post(
        f"{ELEVENLABS_API_BASE}/v1/convai/agents/create",
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(f"API Error ({response.status_code}): {response.text}")
        raise RuntimeError(f"Failed to create agent: {response.status_code} — {response.text}")

    data = response.json()
    agent_id = data.get("agent_id", "")

    print(f"Agent created successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   Save this to your .env file as ELEVENLABS_AGENT_ID")

    return agent_id


def update_callpilot_agent(
    server_url: str,
    agent_id: Optional[str] = None,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    llm_model: str = "gpt-4o",
) -> None:
    """Update an existing CallPilot agent's configuration."""
    agent_id = agent_id or ELEVENLABS_AGENT_ID
    if not agent_id:
        raise ValueError("No agent_id provided and ELEVENLABS_AGENT_ID not set in .env")

    payload = _build_agent_payload(server_url, voice_id, llm_model)

    response = httpx.patch(
        f"{ELEVENLABS_API_BASE}/v1/convai/agents/{agent_id}",
        headers=_api_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(f"API Error ({response.status_code}): {response.text}")
        raise RuntimeError(f"Failed to update agent: {response.status_code} — {response.text}")

    print(f"Agent {agent_id} updated successfully!")
    print(f"   Server URL: {server_url}")


def get_agent_info(agent_id: Optional[str] = None) -> dict:
    """Retrieve current configuration of the CallPilot agent."""
    agent_id = agent_id or ELEVENLABS_AGENT_ID
    if not agent_id:
        raise ValueError("No agent_id provided and ELEVENLABS_AGENT_ID not set in .env")

    response = httpx.get(
        f"{ELEVENLABS_API_BASE}/v1/convai/agents/{agent_id}",
        headers=_api_headers(),
        timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Failed to get agent info: {response.status_code} — {response.text}")

    data = response.json()
    return {
        "agent_id": data.get("agent_id", agent_id),
        "name": data.get("name", "N/A"),
        "conversation_config": data.get("conversation_config", {}),
    }
