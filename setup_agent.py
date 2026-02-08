#!/usr/bin/env python3
"""Agent setup script — create, update, or inspect the ElevenLabs agent."""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, SERVER_URL
from app.agents.call_agent import (
    create_callpilot_agent,
    update_callpilot_agent,
    get_agent_info,
)


def cmd_create(args):
    server_url = args.server_url or SERVER_URL

    if not ELEVENLABS_API_KEY or ELEVENLABS_API_KEY == "your_elevenlabs_api_key_here":
        print("ELEVENLABS_API_KEY not set in .env!")
        sys.exit(1)

    if server_url == "http://localhost:8000":
        print("WARNING: Using localhost as server URL.")
        print("ElevenLabs can't reach localhost! Use Cloudflare Tunnel:")
        print("  cloudflared tunnel --url http://localhost:8000")
        proceed = input("Continue anyway? [y/N]: ").strip().lower()
        if proceed != 'y':
            sys.exit(0)

    print(f"\nCreating CallPilot agent...")
    print(f"   Server URL: {server_url}")
    print(f"   Voice: {args.voice_id}")
    print(f"   LLM: {args.llm_model}\n")

    agent_id = create_callpilot_agent(
        server_url=server_url,
        voice_id=args.voice_id,
        llm_model=args.llm_model,
    )

    print(f"\n  Add this to your .env file:")
    print(f"  ELEVENLABS_AGENT_ID={agent_id}\n")


def cmd_update(args):
    server_url = args.server_url or SERVER_URL
    agent_id = args.agent_id or ELEVENLABS_AGENT_ID

    if not ELEVENLABS_API_KEY:
        print("ELEVENLABS_API_KEY not set in .env!")
        sys.exit(1)

    if not agent_id or agent_id == "your_agent_id_here":
        print("No agent_id provided and ELEVENLABS_AGENT_ID not set in .env!")
        sys.exit(1)

    print(f"\nUpdating agent {agent_id}...")
    print(f"   Server URL: {server_url}\n")

    update_callpilot_agent(
        server_url=server_url,
        agent_id=agent_id,
        voice_id=args.voice_id,
        llm_model=args.llm_model,
    )


def cmd_info(args):
    agent_id = args.agent_id or ELEVENLABS_AGENT_ID

    if not ELEVENLABS_API_KEY:
        print("ELEVENLABS_API_KEY not set in .env!")
        sys.exit(1)

    if not agent_id or agent_id == "your_agent_id_here":
        print("No agent configured yet.")
        sys.exit(1)

    print(f"\nAgent info for: {agent_id}")
    info = get_agent_info(agent_id)
    print(f"   Name: {info.get('name', 'N/A')}")
    print(f"   Agent ID: {info.get('agent_id', 'N/A')}\n")


def main():
    parser = argparse.ArgumentParser(description="CallPilot Agent Setup")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    create_parser = subparsers.add_parser("create", help="Create a new agent")
    create_parser.add_argument("--server-url", type=str, help="Public URL of your server")
    create_parser.add_argument("--voice-id", type=str, default="JBFqnCBsd6RMkjVDRZzb")
    create_parser.add_argument("--llm-model", type=str, default="gpt-4o")

    update_parser = subparsers.add_parser("update", help="Update an existing agent")
    update_parser.add_argument("--server-url", type=str, help="New server URL")
    update_parser.add_argument("--agent-id", type=str)
    update_parser.add_argument("--voice-id", type=str, default="JBFqnCBsd6RMkjVDRZzb")
    update_parser.add_argument("--llm-model", type=str, default="gpt-4o")

    info_parser = subparsers.add_parser("info", help="View agent configuration")
    info_parser.add_argument("--agent-id", type=str)

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
