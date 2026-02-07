"""
CallPilot — Configuration Module
=================================
This module loads ALL environment variables from the .env file and
exposes them as simple Python constants.

WHY centralize config?
  • Every module imports from ONE place (no scattered os.getenv calls).
  • If a key is missing, you catch it here — not deep in a tool call
    during a live demo.
  • Easy to swap between dev/prod by changing a single .env file.

HOW IT WORKS:
  1. python-dotenv reads .env and injects vars into os.environ.
  2. We read them here and expose as module-level constants.
  3. Any file that needs a key just does:
         from app.config import ELEVENLABS_API_KEY
"""

import os
from dotenv import load_dotenv

# Load .env file into environment variables.
# override=False means real env vars (e.g., from Docker) take priority.
load_dotenv(override=False)

# ── ElevenLabs ──────────────────────────────────────────────
# API key authenticates every request to ElevenLabs.
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

# Agent ID identifies which Conversational AI agent to use.
# You'll create this in Phase 3 via the ElevenLabs dashboard.
ELEVENLABS_AGENT_ID: str = os.getenv("ELEVENLABS_AGENT_ID", "")

# Receptionist Agent — handles phone calls to providers.
# Created via: python setup_receptionist.py create
ELEVENLABS_RECEPTIONIST_AGENT_ID: str = os.getenv("ELEVENLABS_RECEPTIONIST_AGENT_ID", "")

# ── Twilio ──────────────────────────────────────────────────
# Account SID + Auth Token = your Twilio credentials (like username/password).
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")

# The phone number Twilio dials FROM (must be a Twilio-purchased number).
TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

# ── Google ──────────────────────────────────────────────────
# Which calendar to check — "primary" = user's main calendar.
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

# API key for Google Maps / Places (non-OAuth, simpler auth).
GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

# ── App Settings ────────────────────────────────────────────
# Server host/port (useful for deployment flexibility).
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

# Public URL for webhook tools (ngrok URL or deployed URL).
# ElevenLabs needs this to reach your /tools/* endpoints.
# Set after starting ngrok: ngrok http 8000
SERVER_URL: str = os.getenv("SERVER_URL", "http://localhost:8000")
