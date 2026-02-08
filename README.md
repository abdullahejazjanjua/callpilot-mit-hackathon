<p align="center">
  <h1 align="center">CallPilot</h1>
  <p align="center">
    <strong>Autonomous Voice AI for Appointment Scheduling</strong>
  </p>
  <p align="center">
    Speak once. Let the AI call, compare, and book for you.
  </p>
  <p align="center">
    <a href="#demos">Demos</a> &bull;
    <a href="#how-it-works">How It Works</a> &bull;
    <a href="#features">Features</a> &bull;
    <a href="#tech-stack">Tech Stack</a> &bull;
    <a href="#getting-started">Getting Started</a> &bull;
    <a href="#api-reference">API Reference</a>
  </p>
</p>

---

> **Disclaimer** &mdash; This project was built during a **MIT Hackathon** and was **vibecoded 99%**. Expect rough edges, creative shortcuts, and the unmistakable energy of a 24-hour sprint. Use at your own risk (and amusement).

---

## The Problem

Scheduling an appointment is a surprisingly painful process. You search for providers, call them one by one, sit on hold, mentally cross-reference your calendar, and repeat until something sticks. A single booking can easily eat **20+ minutes** and multiple phone calls.

## The Solution

**CallPilot** is a voice-first AI agent that handles the *entire* appointment scheduling workflow from a single natural language command. Instead of asking you to choose &mdash; CallPilot **decides, acts, and books**.

> *"I need a dentist tomorrow near Lahore"* &rarr; done in **~30 seconds**.

---

## Demos

### Full Product Demo

https://github.com/user-attachments/assets/demo-video.mov

[demo-video.mov](./demo-video.mov)

### Technical Walkthrough

https://github.com/user-attachments/assets/technical-video-demo.mp4

[technical-video-demo.mp4](./technical-video-demo.mp4)

---

## How It Works

```
 YOU SPEAK                SWARM MODE              CALENDAR CHECK
 ─────────    ───────────────────────    ──────────────────────
 "I need a     Agent contacts up to      Cross-references your
  dentist       15 providers in           Google Calendar for
  tomorrow"     parallel                  conflicts
      │                  │                        │
      ▼                  ▼                        ▼
 DISTANCE CALC           SCORING                AUTO-BOOK
 ──────────────  ─────────────────────  ──────────────────────
 Computes travel  Ranks providers:       Books the #1 match
 time from you    40% rating             and confirms it on
 to each provider 30% proximity          your Google Calendar
                  30% earliness
```

1. **You speak** &mdash; a single natural language command
2. **Swarm mode** &mdash; the agent simultaneously contacts up to 15 providers
3. **Calendar check** &mdash; your Google Calendar is cross-referenced for conflicts
4. **Distance calc** &mdash; travel time from you to each provider is computed
5. **Scoring** &mdash; providers are ranked with a composite score (rating + proximity + earliness)
6. **Auto-book** &mdash; the best match is booked and confirmed on your calendar

---

## Features

| Feature | Description |
|---|---|
| **Swarm Mode** | Calls ALL providers at once, not one at a time |
| **Composite Scoring** | Multi-factor ranking algorithm (rating, distance, time) |
| **Auto-Booking** | No user decision needed &mdash; AI picks the best option |
| **Live Terminal** | Frontend shows real-time backend activity as it happens |
| **Voice-First** | Entire interaction via natural speech, no forms or clicks |
| **Calendar-Aware** | Never double-books; checks real Google Calendar events |
| **Mock Fallbacks** | Every external service has a mock fallback for easy local dev |

---

## Tech Stack

### Backend

- **Python 3** + **FastAPI** &mdash; async web framework
- **ElevenLabs SDK** &mdash; conversational AI & voice (real-time WebSocket)
- **Google Calendar API** &mdash; real calendar integration via OAuth2
- **Google Maps Distance Matrix API** &mdash; travel time computation
- **Mapbox Search Box API** &mdash; provider/POI search
- **Pydantic v2** &mdash; data validation
- **httpx** &mdash; async HTTP client

### Frontend

- **React 18** + **TypeScript** + **Vite**
- **Tailwind CSS** + **shadcn/ui** (Radix primitives)
- **@elevenlabs/react** &mdash; voice SDK integration
- **Server-Sent Events (SSE)** &mdash; real-time streaming terminal

### Infrastructure

- **Uvicorn** &mdash; ASGI server
- **Cloudflare Tunnel** &mdash; public webhook access for ElevenLabs callbacks

---

## Project Structure

```
hackathon/
├── app/                            # Backend
│   ├── main.py                     # FastAPI entry point
│   ├── config.py                   # Environment config
│   ├── events.py                   # SSE event manager
│   ├── agents/
│   │   ├── call_agent.py           # ElevenLabs agent CRUD
│   │   ├── prompts.py              # System prompts
│   │   └── swarm.py                # Swarm orchestrator
│   ├── models/
│   │   └── schemas.py              # Pydantic schemas
│   ├── routes/
│   │   ├── agent_routes.py         # /agent/*
│   │   ├── call_routes.py          # /call/*
│   │   ├── event_routes.py         # /events/*
│   │   ├── swarm_routes.py         # /swarm/*
│   │   └── tool_routes.py          # /tools/* (webhooks)
│   ├── tools/
│   │   ├── calendar_tool.py        # Google Calendar
│   │   ├── call_tool.py            # Simulated calls
│   │   ├── distance_tool.py        # Distance matrix
│   │   ├── provider_tool.py        # Provider search
│   │   └── twilio_bridge.py        # Twilio (optional)
│   └── data/
│       └── providers.json          # Fallback provider data
│
├── callpilot-hub/                  # Frontend (React)
│   ├── src/
│   │   ├── pages/Index.tsx         # Main voice interface
│   │   ├── components/
│   │   │   ├── HeroSection.tsx
│   │   │   ├── MicButton.tsx
│   │   │   └── StatusTerminal.tsx
│   │   └── hooks/
│   │       └── use-event-stream.ts # SSE hook
│   └── ...
│
├── setup_agent.py                  # Agent setup script
├── setup_google_auth.py            # Google OAuth setup
├── requirements.txt                # Python deps
└── .env                            # Environment variables
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ & npm
- An [ElevenLabs](https://elevenlabs.io) API key
- A Google Cloud project with the **Calendar API** enabled
- *(Optional)* Mapbox access token, Google Maps API key, Twilio credentials

### 1. Clone & install backend dependencies

```bash
git clone https://github.com/your-org/callpilot.git
cd callpilot
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
ELEVENLABS_API_KEY=your_key
ELEVENLABS_AGENT_ID=your_agent_id

# Optional
GOOGLE_CALENDAR_ID=primary
GOOGLE_MAPS_API_KEY=your_key
MAPBOX_ACCESS_TOKEN=your_token
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
SERVER_URL=https://your-tunnel.trycloudflare.com
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true
```

### 3. Set up Google Calendar OAuth

```bash
python setup_google_auth.py
```

This creates a `token.json` file for Calendar API access.

### 4. Start a Cloudflare Tunnel (for webhooks)

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the generated URL and set it as `SERVER_URL` in `.env`.

### 5. Create the ElevenLabs agent

```bash
python setup_agent.py create --server-url https://your-tunnel.trycloudflare.com
```

Save the returned `agent_id` to your `.env`.

### 6. Run the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Run the frontend

```bash
cd callpilot-hub
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/swarm/schedule` | Trigger swarm scheduling |
| `POST` | `/tools/find-providers` | Search for providers |
| `POST` | `/tools/call-to-inquire` | Call a provider for slots |
| `POST` | `/tools/check-calendar` | Check slot availability |
| `POST` | `/tools/get-busy-slots` | Get busy time slots |
| `POST` | `/tools/book-appointment` | Book an appointment |
| `POST` | `/tools/calculate-distance` | Calculate travel distance |
| `POST` | `/tools/swarm-schedule` | Swarm mode (webhook) |
| `GET`  | `/events/stream` | SSE stream for real-time updates |
| `POST` | `/agent/create` | Create a new agent |
| `POST` | `/agent/update` | Update agent config |
| `GET`  | `/agent/info` | Get agent info |
| `GET`  | `/agent/signed-url` | Get signed URL for voice session |
| `GET`  | `/health` | Health check |
| `GET`  | `/docs` | Interactive API documentation (Swagger) |

---

## Scoring Algorithm

Providers are ranked using a weighted composite score:

```
score = 0.40 * rating_score + 0.30 * distance_score + 0.30 * time_score
```

| Factor | Weight | Formula |
|---|---|---|
| Rating | 40% | `(rating / 5.0) * 100` |
| Proximity | 30% | `max(0, 100 - distance_km * 4)` |
| Earliness | 30% | `max(0, 100 - hours_away * 1.0)` |

---

## Impact

| Before | After |
|---|---|
| ~20 min of manual calls | ~30 sec voice command |
| 1 provider at a time | 15 providers called simultaneously |
| User picks from a list | AI scores, ranks, and auto-books |
| Passive chatbot | Fully autonomous scheduling agent |

---

<p align="center">
  <sub>Built with sleep deprivation and good vibes at <strong>MIT Hackathon 2026</strong></sub>
</p>
