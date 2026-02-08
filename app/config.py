import os
from dotenv import load_dotenv

load_dotenv(override=False)

# ElevenLabs
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_AGENT_ID: str = os.getenv("ELEVENLABS_AGENT_ID", "")
ELEVENLABS_RECEPTIONIST_AGENT_ID: str = os.getenv("ELEVENLABS_RECEPTIONIST_AGENT_ID", "")

# Twilio
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

# Google
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
MAPBOX_ACCESS_TOKEN: str = os.getenv("MAPBOX_ACCESS_TOKEN", "")

# App
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
SERVER_URL: str = os.getenv("SERVER_URL", "http://localhost:8000")
