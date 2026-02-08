#!/usr/bin/env python3
"""Conversation flow simulator — tests the full appointment booking flow locally."""

import httpx
import json
import sys
import time

BASE_URL = "http://localhost:8000"


def call_tool(endpoint: str, payload: dict, description: str) -> dict:
    print(f"\n{'─' * 60}")
    print(f"Agent: \"{description}\"")
    print(f"   -> POST {endpoint}")
    print(f"   -> Body: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.post(f"{BASE_URL}{endpoint}", json=payload, timeout=10)
        result = response.json()
        print(f"   Status: {response.status_code}")
        for line in json.dumps(result, indent=2).split("\n"):
            print(f"      {line}")
        return result

    except httpx.ConnectError:
        print(f"   Connection failed! Is the server running?")
        sys.exit(1)


def simulate_conversation():
    print("\n" + "=" * 60)
    print("  CALLPILOT — CONVERSATION SIMULATOR")
    print("=" * 60)
    print("\n  Scenario: User wants a dentist appointment this Tuesday")
    print("  Date: Tuesday, February 10, 2026")
    print("  User location: 100 Market St, San Francisco\n")
    time.sleep(0.5)

    # Step 1: Check schedule
    print(f"\n{'=' * 60}")
    print("STEP 1: Check user's schedule for Tuesday")
    print(f"{'=' * 60}")

    busy = call_tool(
        "/tools/get-busy-slots",
        {"date": "2026-02-10"},
        "Let me check what the user has on Tuesday...",
    )

    if busy.get("total_events", 0) > 0:
        print(f"\n   Agent: \"I see you have {busy['total_events']} event(s) on Tuesday.\"")
    else:
        print(f"\n   Agent: \"Your Tuesday looks clear!\"")

    time.sleep(0.5)

    # Step 2: Find providers
    print(f"\n{'=' * 60}")
    print("STEP 2: Find dentists available on Tuesday")
    print(f"{'=' * 60}")

    providers = call_tool(
        "/tools/find-available",
        {"category": "dentists", "date": "2026-02-10", "min_rating": 4.0},
        "Now let me find dentists with slots on Tuesday...",
    )

    count = providers.get("count", 0)
    if count > 0:
        print(f"\n   Agent: \"I found {count} dentist(s) available Tuesday.\"")
    else:
        print(f"\n   Agent: \"Sorry, no dentists available Tuesday.\"")
        return

    time.sleep(0.5)

    # Step 3: Check distances
    print(f"\n{'=' * 60}")
    print("STEP 3: Calculate distance to each provider")
    print(f"{'=' * 60}")

    for p in providers.get("providers", []):
        dist = call_tool(
            "/tools/calculate-distance",
            {
                "user_location": "100 Market St, San Francisco, CA",
                "provider_address": p["address"],
                "provider_id": p["id"],
                "provider_name": p["name"],
            },
            f"How far is {p['name']}?",
        )
        print(f"\n   \"{p['name']} is {dist['distance_km']} km away ({dist['duration_minutes']} min drive)\"")

    time.sleep(0.5)

    # Step 4: Smart slot selection
    print(f"\n{'=' * 60}")
    print("STEP 4: Find a slot with no conflicts")
    print(f"{'=' * 60}")

    chosen = None
    chosen_slot = None

    for p in providers.get("providers", []):
        for slot in p["available_slots"]:
            avail = call_tool(
                "/tools/check-calendar",
                {"slot": slot},
                f"Is {slot[11:16]} free for {p['name']}?",
            )

            if avail["is_available"]:
                print(f"\n   {slot[11:16]} is FREE! Selecting {p['name']}")
                chosen = p
                chosen_slot = slot
                break
            else:
                print(f"\n   {slot[11:16]} conflicts with '{avail['conflict_with']}' — trying next...")

        if chosen:
            break

    if not chosen:
        print(f"\n   Agent: \"Sorry, none of the available slots work with your calendar.\"")
        return

    time.sleep(0.5)

    # Step 5: Book
    print(f"\n{'=' * 60}")
    print(f"STEP 5: Book the appointment at {chosen['name']}, {chosen_slot[11:16]}")
    print(f"{'=' * 60}")

    booking = call_tool(
        "/tools/book-appointment",
        {
            "provider_name": chosen["name"],
            "provider_phone": chosen["phone"],
            "provider_address": chosen["address"],
            "slot": chosen_slot,
            "provider_id": chosen["id"],
            "service_type": "dentists",
            "patient_name": "Hackathon Demo User",
        },
        "Booking the appointment now...",
    )

    if booking["success"]:
        print(f"\n   Agent: \"{booking['message']}\"")
    else:
        print(f"\n   Agent: \"Sorry, booking failed: {booking['message']}\"")

    time.sleep(0.5)

    # Step 6: Verify
    print(f"\n{'=' * 60}")
    print("STEP 6: Verify the appointment is on the calendar")
    print(f"{'=' * 60}")

    verify = call_tool(
        "/tools/get-busy-slots",
        {"date": chosen_slot[:10]},
        "Let me confirm it's on the calendar...",
    )

    print(f"\n   Calendar for {chosen_slot[:10]} now has {verify['total_events']} event(s):")
    for slot in verify.get("busy_slots", []):
        marker = "NEW" if chosen["name"] in slot.get("title", "") else "   "
        print(f"      {marker} {slot['title']} ({slot['start'][11:16]} - {slot['end'][11:16]})")

    print(f"\n{'=' * 60}")
    print("  CONVERSATION SIMULATION COMPLETE")
    print(f"{'=' * 60}\n")
    if booking["success"]:
        print(f"  Booking Summary:")
        print(f"     Provider: {booking['provider_name']}")
        print(f"     Time:     {booking['appointment_time']}")
        print(f"     Address:  {booking['provider_address']}")
        print(f"     Phone:    {booking['provider_phone']}\n")


if __name__ == "__main__":
    simulate_conversation()
