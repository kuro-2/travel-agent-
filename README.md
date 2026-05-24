# TravelAI

An AI-powered travel assistant for India. Ask it anything — how to reach a destination, cheap stays with WiFi, train schedules, road routes, weather, or full trip plans. It handles natural, conversational queries and responds with structured, practical answers.

Built with Flask, Supabase, and Llama-3.3-70B via Hugging Face.

---

## Features

- **Conversational AI** — understands natural, multi-part queries like *"I want to go to Kasol for remote work, how do I get there and where should I stay with good WiFi?"*
- **Smart intent routing** — LLM-based classification with rule-based fallback for weather, trains, road routes, place info, trip planning, and general travel queries
- **Work-from-home travel** — knows WiFi quality, mobile coverage, and WFH-friendly stays at popular Indian remote work destinations
- **Weather** — live data via Tomorrow.io, local JSON fallback
- **Train info** — schedules by train number via RapidAPI (Indian Railways), local JSON fallback
- **Road routes** — driving time and distance via OpenRouteService, local JSON fallback
- **Trip planning** — combines transport options, weather, place info, and seasonal advice into one response
- **Google OAuth + email/password auth** — PKCE-based Google sign-in via Supabase, full session management
- **Chat history** — conversations persisted per-session in Supabase (paired user + assistant rows)
- **Dark glassmorphism UI** — responsive chat interface with markdown rendering, typing indicator, and suggestion chips

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0 |
| Auth | Supabase Auth (email/password + Google OAuth PKCE) |
| Database | Supabase (PostgreSQL) |
| LLM | Llama-3.3-70B-Instruct via Hugging Face Inference API (Novita) |
| Weather API | Tomorrow.io |
| Train API | Indian Railways via RapidAPI |
| Road API | OpenRouteService |
| Hosting | Render (primary) |

---

## Project Structure

```
travel-agent-/
├── chat_server.py          # Flask app — all routes and session logic
├── auth.py                 # Email/password auth + Google OAuth PKCE flow
├── db.py                   # Supabase database helpers
├── promptflow_router.py    # Intent classification, data fetching, LLM response
├── weather_api.py          # Weather Blueprint + standalone fetch_weather()
├── rail_api.py             # Rail Blueprint + standalone fetch_train()
├── road_api.py             # Road Blueprint + standalone fetch_route()
│
├── templates/
│   ├── index.html          # Chat UI
│   ├── login.html          # Sign-in page
│   └── register.html       # Registration page
│
├── migrations/
│   ├── 001_create_tables.sql       # chat_sessions, chat_messages (legacy)
│   ├── 002_profiles_table.sql      # profiles table + auth trigger
│   ├── 003_chat_messages_paired.sql # chat_exchanges table (current)
│   └── 004_drop_chat_messages.sql  # drops old chat_messages table
│
├── updated-data-weather.json       # Fallback weather data
├── updated-json-data-for-train.json # Fallback train schedules
├── updated-routes-data.json        # Fallback road routes
├── tourism-data.json               # Place info and best-time data
│
├── requirements.txt
├── render.yaml             # Render deployment config
├── Procfile                # Gunicorn start command
└── .env                    # Local env vars (never commit)
```

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/kuro-2/travel-agent-.git
cd travel-agent-
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Flask
FLASK_SECRET_KEY=your-long-random-secret-key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# LLM (Hugging Face token with Inference API access)
HF_TOKEN=hf_...

# External APIs
RAPIDAPI_KEY=your-rapidapi-key
ORS_API_KEY=your-openrouteservice-key
TOMORROW_API_KEY=your-tomorrow-io-key
```

### 4. Set up the Supabase database

Run the migrations **in order** in your Supabase project:  
**Supabase Dashboard → SQL Editor → New query → paste each file → Run**

```
migrations/001_create_tables.sql
migrations/002_profiles_table.sql
migrations/003_chat_messages_paired.sql
migrations/004_drop_chat_messages.sql
```

> **Important:** Migration 002 fixes a known issue where the `handle_new_user` trigger must reference `NEW.raw_app_meta_data` (not `NEW.app_metadata`). If you see *"Database error saving new user"* on signup, re-run the `CREATE OR REPLACE FUNCTION` block from 002 in the SQL Editor.

### 5. Configure Google OAuth (optional)

1. Create a Google OAuth app at [console.cloud.google.com](https://console.cloud.google.com)
2. Add `https://your-project.supabase.co/auth/v1/callback` as an authorized redirect URI
3. Enable Google as a provider in **Supabase Dashboard → Authentication → Providers**
4. Add `http://localhost:5000/auth/callback` (local) and your production URL to **Supabase → Authentication → URL Configuration → Redirect URLs**

### 6. Run the development server

```bash
python chat_server.py
```

Open [http://localhost:5000](http://localhost:5000).

---

## Deploying to Render

The repo includes `render.yaml` for one-click deployment.

### Steps

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service** → connect your repo
3. Render auto-detects `render.yaml` — build and start commands are pre-configured
4. Go to **Environment** in the Render dashboard and add these variables:

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API |
| `HF_TOKEN` | huggingface.co → Settings → Access Tokens |
| `RAPIDAPI_KEY` | rapidapi.com |
| `ORS_API_KEY` | openrouteservice.org |
| `TOMORROW_API_KEY` | tomorrow.io |

> `FLASK_SECRET_KEY` is auto-generated by Render (`generateValue: true`) — no action needed.

5. Click **Deploy**

> **Free tier note:** Render's free plan spins down after 15 minutes of inactivity. The first request after spin-down takes ~30 seconds to cold-start.

### Update Supabase redirect URLs after deploy

Add your Render URL to **Supabase → Authentication → URL Configuration → Redirect URLs**:
```
https://your-app.onrender.com/auth/callback
```

---

## How It Works

```
User message
     │
     ▼
classify_intent()  ──────────────────────────────────────────────┐
  LLM (Llama-3.3-70B) classifies intent + extracts location/     │
  train number / start+end city                                   │
  Falls back to rule-based classifier if LLM fails               │
     │                                                            │
     ▼                                                            │
Intent routing                                                    │
     ├── weather      → fetch_weather(location)                   │
     ├── train_number → fetch_train(number)                       │
     ├── train_route  → fallback JSON lookup                      │
     ├── road         → fetch_route(start, end)                   │
     ├── place_info   → tourism-data.json                         │
     ├── best_time    → tourism-data.json + seasonal rules        │
     ├── trip_planning→ train + road + weather + place combined   │
     ├── general_travel → if location detected: enrich with       │
     │                    place info + weather, then LLM          │
     └── unknown      → polite decline                            │
                                                                  │
     ▼                                                            │
generate_response()                                               │
  LLM synthesises fetched data + user question into a            │
  conversational, markdown-formatted reply                       │
     │                                                            │
     ▼                                                            │
Flask /chat endpoint returns JSON → rendered in chat UI ◄────────┘
```

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | ✓ | Chat UI |
| `GET` | `/login` | — | Login page |
| `GET` | `/register` | — | Register page |
| `POST` | `/auth/register` | — | Email/password registration |
| `POST` | `/auth/login` | — | Email/password login |
| `POST` | `/auth/logout` | ✓ | Logout + clear session |
| `GET` | `/auth/me` | ✓ | Current user info |
| `GET` | `/auth/google` | — | Start Google OAuth flow |
| `GET` | `/auth/callback` | — | OAuth callback (Supabase redirect) |
| `POST` | `/chat` | ✓ | Send message, get AI response |
| `GET` | `/history` | ✓ | Load chat history for current session |
| `GET` | `/weather` | — | Raw weather data for a location |
| `GET` | `/train-info/<id>` | — | Train schedule by number or name |
| `GET` | `/route` | — | Driving time/distance between two places |

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Yes | Secret for Flask session signing. Use a long random string. |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key (used for auth) |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (bypasses RLS for server-side DB ops) |
| `HF_TOKEN` | Yes | Hugging Face access token with Inference API permissions |
| `RAPIDAPI_KEY` | Yes | RapidAPI key subscribed to Indian Railways API |
| `ORS_API_KEY` | Yes | OpenRouteService API key for road routing |
| `TOMORROW_API_KEY` | Yes | Tomorrow.io API key for weather data |
| `FLASK_ENV` | No | Set to `development` to enable Flask debug mode locally |

---

## License

MIT — free to use, modify, and distribute.
