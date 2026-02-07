#!/usr/bin/env python3
"""
CallPilot — Google Calendar OAuth Setup
==========================================
Run this script ONCE to authenticate with Google Calendar.

WHAT IT DOES:
  1. Reads your credentials.json (downloaded from Google Cloud Console)
  2. Opens a browser window for you to log in and grant Calendar access
  3. Saves the access token to token.json (used by the app at runtime)

PREREQUISITES:
  1. Go to https://console.cloud.google.com
  2. Create a new project (or use an existing one)
  3. Enable the "Google Calendar API":
     → APIs & Services → Library → search "Google Calendar API" → Enable
  4. Create OAuth 2.0 credentials:
     → APIs & Services → Credentials → Create Credentials → OAuth Client ID
     → Application type: "Desktop App"
     → Download the JSON file
  5. Save it as "credentials.json" in this project's root directory
  6. Run this script: python setup_google_auth.py

AFTER SETUP:
  The app will automatically use your real Google Calendar for:
  • Checking availability (real events)
  • Booking appointments (creates real calendar events)
  • Getting busy slots (reads your actual schedule)
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"


def main():
    print()
    print("=" * 55)
    print("  🛫 CallPilot — Google Calendar Setup")
    print("=" * 55)
    print()

    # Check for credentials.json
    if not CREDENTIALS_FILE.exists():
        print("❌ credentials.json NOT FOUND in project root!")
        print()
        print("  To get it:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Create/select a project")
        print("  3. Enable 'Google Calendar API'")
        print("     → APIs & Services → Library → Google Calendar API → Enable")
        print("  4. Create OAuth 2.0 credentials")
        print("     → APIs & Services → Credentials → Create Credentials")
        print("     → OAuth Client ID → Application type: Desktop App")
        print("  5. Download the JSON file")
        print("  6. Save it as 'credentials.json' in this directory:")
        print(f"     {PROJECT_ROOT}")
        print()
        return

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ Google auth libraries not installed!")
        print("   Run: pip install google-api-python-client google-auth-oauthlib")
        return

    creds = None

    # Check for existing token
    if TOKEN_FILE.exists():
        print("📄 Found existing token.json — checking validity...")
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Token expired — refreshing...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google sign-in...")
            print("   (If browser doesn't open, copy the URL from the terminal)")
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the token
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        print(f"✅ Token saved to {TOKEN_FILE}")
    else:
        print("✅ Token is still valid!")

    # Verify by listing upcoming events
    print()
    print("🔍 Verifying connection by listing your next 5 events...")
    print()

    try:
        from googleapiclient.discovery import build
        from datetime import datetime, timezone

        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=5,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            print("   📭 No upcoming events found (calendar might be empty)")
        else:
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                print(f"   📅 {start[:16]}  —  {event['summary']}")

        print()
        print("=" * 55)
        print("  ✅ Google Calendar is ready!")
        print("  🛫 CallPilot will now use your REAL calendar.")
        print("=" * 55)
        print()

    except Exception as e:
        print(f"⚠️  Connection works but couldn't list events: {e}")
        print("   (This is OK — the token is still valid)")


if __name__ == "__main__":
    main()
