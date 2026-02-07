#!/usr/bin/env python3
"""
CallPilot — Agent Setup Script
================================
Run this script to create or update your ElevenLabs agent.

USAGE:
  # Create a new agent (first time only):
  python setup_agent.py create --server-url https://YOUR-NGROK-URL.ngrok.io

  # Update existing agent (when ngrok URL changes):
  python setup_agent.py update --server-url https://YOUR-NEW-NGROK-URL.ngrok.io

  # View current agent config:
  python setup_agent.py info

WHAT THIS DOES:
  1. Reads your ELEVENLABS_API_KEY from .env
  2. Builds the agent with system prompt + 7 webhook tools
  3. Points all webhook tools to YOUR server via the --server-url
  4. Creates/updates the agent on ElevenLabs cloud
  5. Prints the agent_id for you to save in .env

PREREQUISITES:
  1. ELEVENLABS_API_KEY set in .env
  2. Your FastAPI server running (uvicorn app.main:app)
  3. ngrok running (ngrok http 8000) — gives you a public URL
"""

import argparse
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, SERVER_URL
from app.agents.call_agent import (
    create_callpilot_agent,
    update_callpilot_agent,
    get_agent_info,
)


def cmd_create(args):
    """Create a new ElevenLabs agent."""
    server_url = args.server_url or SERVER_URL

    if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY == "your_elevenlabs_api_key_here":
        print("❌ ELEVENLABS_API_KEY not set in .env!")
        print("   Get your key from: https://elevenlabs.io/app/settings/api-keys")
        sys.exit(1)

    if server_url == "http://localhost:8000":
        print("⚠️  WARNING: Using localhost as server URL.")
        print("   ElevenLabs can't reach localhost! Use ngrok:")
        print("   1. Run: ngrok http 8000")
        print("   2. Copy the https URL")
        print("   3. Re-run: python setup_agent.py create --server-url https://YOUR-URL.ngrok.io")
        print()
        proceed = input("   Continue anyway (for local testing)? [y/N]: ").strip().lower()
        if proceed != 'y':
            sys.exit(0)

    print(f"\n🛫 Creating CallPilot agent...")
    print(f"   Server URL: {server_url}")
    print(f"   Voice: {args.voice_id}")
    print(f"   LLM: {args.llm_model}")
    print()

    agent_id = create_callpilot_agent(
        server_url=server_url,
        voice_id=args.voice_id,
        llm_model=args.llm_model,
    )

    print()
    print("━" * 55)
    print(f"  📋 NEXT STEP: Add this to your .env file:")
    print(f"     ELEVENLABS_AGENT_ID={agent_id}")
    print("━" * 55)
    print()


def cmd_update(args):
    """Update an existing agent's configuration."""
    server_url = args.server_url or SERVER_URL
    agent_id = args.agent_id or ELEVENLABS_AGENT_ID

    if not ELEVENLABS_API_KEY:
        print("❌ ELEVENLABS_API_KEY not set in .env!")
        sys.exit(1)

    if not agent_id or agent_id == "your_agent_id_here":
        print("❌ No agent_id provided and ELEVENLABS_AGENT_ID not set in .env!")
        print("   Create an agent first: python setup_agent.py create --server-url <URL>")
        sys.exit(1)

    print(f"\n🔄 Updating agent {agent_id}...")
    print(f"   Server URL: {server_url}")
    print()

    update_callpilot_agent(
        server_url=server_url,
        agent_id=agent_id,
        voice_id=args.voice_id,
        llm_model=args.llm_model,
    )
    print()


def cmd_info(args):
    """Show current agent configuration."""
    agent_id = args.agent_id or ELEVENLABS_AGENT_ID

    if not ELEVENLABS_API_KEY:
        print("❌ ELEVENLABS_API_KEY not set in .env!")
        sys.exit(1)

    if not agent_id or agent_id == "your_agent_id_here":
        print("❌ No agent configured yet.")
        print("   Create one: python setup_agent.py create --server-url <URL>")
        sys.exit(1)

    print(f"\n📋 Agent info for: {agent_id}")
    info = get_agent_info(agent_id)
    print(f"   Name: {info.get('name', 'N/A')}")
    print(f"   Agent ID: {info.get('agent_id', 'N/A')}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="CallPilot — Agent Setup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_agent.py create --server-url https://abc123.ngrok.io
  python setup_agent.py update --server-url https://new-url.ngrok.io
  python setup_agent.py info
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── create ──
    create_parser = subparsers.add_parser("create", help="Create a new agent")
    create_parser.add_argument("--server-url", type=str, help="Public URL of your server")
    create_parser.add_argument("--voice-id", type=str, default="JBFqnCBsd6RMkjVDRZzb", help="ElevenLabs voice ID")
    create_parser.add_argument("--llm-model", type=str, default="gpt-4o", help="LLM model")

    # ── update ──
    update_parser = subparsers.add_parser("update", help="Update an existing agent")
    update_parser.add_argument("--server-url", type=str, help="New server URL")
    update_parser.add_argument("--agent-id", type=str, help="Agent ID to update")
    update_parser.add_argument("--voice-id", type=str, default="JBFqnCBsd6RMkjVDRZzb", help="Voice ID")
    update_parser.add_argument("--llm-model", type=str, default="gpt-4o", help="LLM model")

    # ── info ──
    info_parser = subparsers.add_parser("info", help="View agent configuration")
    info_parser.add_argument("--agent-id", type=str, help="Agent ID to query")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
