#!/usr/bin/env python3
"""
CallPilot — Conversation Flow Simulator
==========================================
This script simulates a FULL appointment booking conversation
by calling the same tool endpoints that ElevenLabs would call.

PURPOSE:
  Test the entire flow WITHOUT needing:
  • A live ElevenLabs agent
  • ngrok
  • A real phone call

  It walks through the exact sequence of tool calls the agent
  would make during a real conversation.

USAGE:
  1. Start the server:  uvicorn app.main:app --reload
  2. Run this script:   python test_conversation.py

WHAT IT SIMULATES:
  User: "I need a dentist appointment this Tuesday"

  Agent thinking:
  1. "Let me check what's on their calendar Tuesday"
     → calls get_busy_slots("2026-02-10")

  2. "Now let me find dentists available Tuesday"
     → calls find_available_providers("dentists", "2026-02-10")

  3. "Let me check distances for the top options"
     → calls calculate_distance(...)

  4. "User picked Bright Smile. Is 9am free on their calendar?"
     → calls check_calendar("2026-02-10T09:00:00")

  5. "It's free! Let me book it"
     → calls book_appointment(...)

  6. "Verify it's on the calendar now"
     → calls get_busy_slots("2026-02-10") again
"""

import httpx
import json
import sys
import time

# ── Configuration ─────────────────────────────────────────
BASE_URL = "http://localhost:8000"
DIVIDER = "━" * 60


def call_tool(endpoint: str, payload: dict, description: str) -> dict:
    """
    Call a tool endpoint and display the result.

    Mimics what ElevenLabs does when the agent invokes a tool.
    """
    print(f"\n{'─' * 60}")
    print(f"🤖 Agent thinking: \"{description}\"")
    print(f"   → POST {endpoint}")
    print(f"   → Body: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.post(
            f"{BASE_URL}{endpoint}",
            json=payload,
            timeout=10,
        )
        result = response.json()

        if response.status_code == 200:
            print(f"   ✅ Status: {response.status_code}")
        else:
            print(f"   ❌ Status: {response.status_code}")

        print(f"   📦 Response:")
        # Pretty print, indented
        for line in json.dumps(result, indent=2).split("\n"):
            print(f"      {line}")

        return result

    except httpx.ConnectError:
        print(f"   ❌ Connection failed! Is the server running?")
        print(f"      Start it: uvicorn app.main:app --reload --port 8000")
        sys.exit(1)


def simulate_conversation():
    """Simulate a full appointment booking conversation."""

    print()
    print(DIVIDER)
    print("  🎙️  CALLPILOT — CONVERSATION SIMULATOR")
    print(DIVIDER)
    print()
    print("  Scenario: User wants a dentist appointment this Tuesday")
    print("  Date: Tuesday, February 10, 2026")
    print("  User location: 100 Market St, San Francisco")
    print()
    time.sleep(0.5)

    # ── Step 1: Check user's schedule for Tuesday ───────────
    print(f"\n{'═' * 60}")
    print("📍 STEP 1: Check the user's schedule for Tuesday")
    print(f"{'═' * 60}")

    busy = call_tool(
        "/tools/get-busy-slots",
        {"date": "2026-02-10"},
        "Let me check what the user has on Tuesday...",
    )

    if busy.get("total_events", 0) > 0:
        print(f"\n   💬 Agent would say: \"I see you have {busy['total_events']} event(s) on Tuesday:")
        for slot in busy.get("busy_slots", []):
            print(f"      • {slot['title']} ({slot['start'][:16]} - {slot['end'][:16]})")
        print(f"      I'll make sure to avoid those times.\"")
    else:
        print(f"\n   💬 Agent would say: \"Your Tuesday looks clear!\"")

    time.sleep(0.5)

    # ── Step 2: Find available dentists for Tuesday ─────────
    print(f"\n{'═' * 60}")
    print("📍 STEP 2: Find dentists available on Tuesday")
    print(f"{'═' * 60}")

    providers = call_tool(
        "/tools/find-available",
        {"category": "dentists", "date": "2026-02-10", "min_rating": 4.0},
        "Now let me find dentists with slots on Tuesday...",
    )

    count = providers.get("count", 0)
    if count > 0:
        print(f"\n   💬 Agent would say: \"I found {count} dentist(s) available Tuesday:\"")
        for p in providers.get("providers", []):
            slots = ", ".join([s[11:16] for s in p["available_slots"]])
            print(f"      • {p['name']} (★ {p['rating']}) — slots: {slots}")
    else:
        print(f"\n   💬 Agent would say: \"Sorry, no dentists available Tuesday.\"")
        return

    time.sleep(0.5)

    # ── Step 3: Check distances to top providers ────────────
    print(f"\n{'═' * 60}")
    print("📍 STEP 3: Calculate distance to each provider")
    print(f"{'═' * 60}")

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
        print(f"\n   💬 \"{p['name']} is {dist['distance_km']} km away ({dist['duration_minutes']} min drive)\"")

    time.sleep(0.5)

    # ── Step 4: Smart slot selection — check every slot against calendar ──
    print(f"\n{'═' * 60}")
    print("📍 STEP 4: Smart slot selection — find a slot with no conflicts")
    print(f"{'═' * 60}")

    # Collect all (provider, slot) pairs and check each
    chosen = None
    chosen_slot = None

    for p in providers.get("providers", []):
        for slot in p["available_slots"]:
            print(f"\n   👤 Considering: {p['name']} at {slot[11:16]}...")

            avail = call_tool(
                "/tools/check-calendar",
                {"slot": slot},
                f"Is {slot[11:16]} free on the user's calendar for {p['name']}?",
            )

            if avail["is_available"]:
                print(f"\n   ✅ {slot[11:16]} is FREE! Selecting {p['name']}")
                chosen = p
                chosen_slot = slot
                break
            else:
                print(f"\n   ⚠️  {slot[11:16]} conflicts with '{avail['conflict_with']}' — trying next...")

        if chosen:
            break

    if not chosen:
        print(f"\n   💬 Agent would say: \"Sorry, none of the available slots work with your calendar.\"")
        print(f"\n{'═' * 60}")
        print("  ❌ CONVERSATION ENDED — No compatible slots found")
        print(f"{'═' * 60}")
        return

    print(f"\n   💬 Agent would say: \"I found a free slot! {chosen['name']} at {chosen_slot[11:16]} works perfectly.\"")
    print(f"\n   👤 User says: \"Yes, book it!\"")

    time.sleep(0.5)

    # ── Step 5: Book the appointment ────────────────────────
    print(f"\n{'═' * 60}")
    print(f"📍 STEP 5: Book the appointment at {chosen['name']}, {chosen_slot[11:16]}!")
    print(f"{'═' * 60}")

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
        print(f"\n   💬 Agent would say: \"{booking['message']}\"")
    else:
        print(f"\n   💬 Agent would say: \"Sorry, booking failed: {booking['message']}\"")

    time.sleep(0.5)

    # ── Step 6: Verify booking on calendar ──────────────────
    print(f"\n{'═' * 60}")
    print("📍 STEP 6: Verify the appointment is on the calendar")
    print(f"{'═' * 60}")

    verify = call_tool(
        "/tools/get-busy-slots",
        {"date": chosen_slot[:10]},
        "Let me confirm it's on the calendar...",
    )

    print(f"\n   📅 Calendar for {chosen_slot[:10]} now has {verify['total_events']} event(s):")
    for slot in verify.get("busy_slots", []):
        marker = "🆕" if chosen["name"] in slot.get("title", "") else "  "
        print(f"      {marker} {slot['title']} ({slot['start'][11:16]} - {slot['end'][11:16]})")

    # ── Summary ─────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("  ✅ CONVERSATION SIMULATION COMPLETE")
    print(f"{'═' * 60}")
    print()
    if booking["success"]:
        print("  📋 Booking Summary:")
        print(f"     Provider: {booking['provider_name']}")
        print(f"     Time:     {booking['appointment_time']}")
        print(f"     Address:  {booking['provider_address']}")
        print(f"     Phone:    {booking['provider_phone']}")
    print()
    print("  This is exactly the flow ElevenLabs executes during")
    print("  a real voice conversation — same endpoints, same data.")
    print()
    print(DIVIDER)


if __name__ == "__main__":
    simulate_conversation()
