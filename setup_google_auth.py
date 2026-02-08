#!/usr/bin/env python3
"""Google Calendar OAuth setup — run once to authenticate."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"


def main():
    print("\nCallPilot — Google Calendar Setup\n")

    if not CREDENTIALS_FILE.exists():
        print("credentials.json NOT FOUND in project root!")
        print("Download it from https://console.cloud.google.com")
        print(f"Save it to: {PROJECT_ROOT}")
        return

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Google auth libraries not installed!")
        print("Run: pip install google-api-python-client google-auth-oauthlib")
        return

    creds = None

    if TOKEN_FILE.exists():
        print("Found existing token.json — checking validity...")
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired — refreshing...")
            creds.refresh(Request())
        else:
            print("Opening browser for Google sign-in...\n")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")
    else:
        print("Token is still valid!")

    print("\nVerifying connection...\n")

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
            print("   No upcoming events found")
        else:
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                print(f"   {start[:16]}  —  {event['summary']}")

        print("\nGoogle Calendar is ready!\n")

    except Exception as e:
        print(f"Connection works but couldn't list events: {e}")


if __name__ == "__main__":
    main()
