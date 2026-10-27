# Casa Alon

A landing page for Casa Alon, built with Next.js, with the "Ask Alon" chat
widget connected to the real Casa Alon hotel bot — live Google Doc
knowledge base, live Hotelogix rates/availability, and on-hold reservations
— ported from the original FastAPI backend to run as a Vercel Python
function, so the whole site deploys from one repo.

Landing page copy, pricing shown as placeholder text, the address, and
photos are still placeholder — see "What's placeholder" below. The chatbot
itself is **not** a placeholder; it's the real backend's logic.

## Architecture

```
Browser
  │  loads /widget.js (public/widget.js) via a <script> tag in app/layout.tsx
  │  POST /api/chat  {session_id, message}
  ▼
Vercel Python Function (api/chat.py)
  │
  ├─ api/_rag.py    the LangChain agent + tools (ported from rag.py)
  ├─ api/_pms.py     Hotelogix / mock PMS client (copied from pms.py, unchanged)
  ├─ api/_kb.py      live Google Doc knowledge base (ported from rag.py)
  └─ api/_memory.py  Redis-backed conversation + reservation state
                      (replaces rag.py's in-process dicts — see below)
  │
  ├─ Gemini (chat + embeddings)
  ├─ Hotelogix Web API (PMS_PROVIDER=hotelogix)
  ├─ Google Docs (the live knowledge base doc)
  ├─ Upstash Redis (conversation history, pending reservations, rate limits)
  └─ STAFF_WEBHOOK_URL (optional — e.g. an n8n webhook for handoff/booking alerts)

Next.js app/, components/     the landing page itself — no chat logic here anymore
```

## Why this isn't just the original backend copy-pasted

The original FastAPI backend (`core.py`, `rag.py`) kept conversation history
and the reservation "prepared, waiting for the guest's YES" state in plain
Python dictionaries in server memory. That's correct on a single
long-running server, but **not** on Vercel: nothing guarantees the same
serverless instance handles a guest's "YES" that handled their room
selection a minute earlier. So:

- Conversation history and the reservation flow's state now live in Redis
  (`api/_memory.py`), loaded at the start of each request and saved at the
  end, rather than in module-level dicts.
- Each request gets its own disposable LangGraph thread id for the
  agent's internal tool-calling loop (safe — that loop is entirely
  contained within one request), while the guest's real, stable thread id
  is passed separately for the Redis-backed reservation state, which does
  need to correlate correctly across separate messages.
- `MEMORY_DB_PATH` (the original's optional SQLite file for surviving
  restarts) is dropped — Vercel's filesystem is ephemeral and wouldn't be
  shared across instances anyway, so it offered nothing over Redis here.

Everything else — the system prompt, every tool's logic, the reservation
flow's safeguards (price re-check, 15-minute summary expiry, one booking at
a time, daily limit per guest) — is unchanged from the original.

**Not ported**: Facebook, WhatsApp, and Viber. The original backend's
`channels/` folder handled those via webhooks on a persistent server; this
port only covers the website widget, since that's what's embedded here.
If/when those channels go live, they likely belong on separate, persistent
hosting (Render, Railway, Cloud Run — see the original README) rather than
forcing webhook-based channels into this request/response model, since
nothing about them requires Vercel specifically.

**Rate limiting** is reimplemented here as simple Redis-backed fixed-window
counters (`api/chat.py`), rather than the original's in-process limiter,
for the same reason as above — it wouldn't be shared across instances.

## Environment variables

Set these in Vercel → Settings → Environment Variables (not in a committed
file). At minimum:

- `GOOGLE_API_KEY` — Gemini, for both chat and embeddings
- `GDOC_ID` — the Google Doc id for the knowledge base (must be shared
  "Anyone with the link: Viewer")
- `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` — from your Upstash
  Redis database (create one via Vercel's Storage tab → Marketplace →
  Upstash, which wires these in automatically)

For live Hotelogix rates and reservations: `PMS_PROVIDER=hotelogix` plus
`HOTELOGIX_CONSUMER_KEY`, `HOTELOGIX_CONSUMER_SECRET`, `HOTELOGIX_HOTEL_ID`,
`HOTELOGIX_BASE_URL`, and `BOOKINGS_ENABLED=true` if reservations should be
live (business source, market segment, guest type, etc. must match your
property's Hotelogix setup exactly). Leaving `PMS_PROVIDER` unset defaults
to mock sample data.

Optional: `CHAT_MODEL`, `EMBED_MODEL` (Gemini model names), `LANGSMITH_TRACING` /
`LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` (tracing), `STAFF_WEBHOOK_URL`
(handoff/booking alerts), `WEB_ALLOWED_ORIGINS`, `WEB_RATE_*` (rate limits).

## Deploying

This is one Vercel project with two function types in it — Vercel builds
both automatically:

1. Push to GitHub, import the repo in Vercel as usual.
2. Add the environment variables above.
3. Deploy. The Next.js app builds normally; `api/chat.py` is picked up as a
   separate Python function (Vercel auto-detects the `app` FastAPI
   instance) because it sits in a top-level `/api` directory — same
   convention as e.g. the `limon-portfolio` site's `api/chat.py`.

`vercel.json` sets a 60-second timeout on the chat function, since the
agent's tool-calling loop (Gemini + a live Hotelogix round trip) can take
longer than the platform default. If your plan doesn't allow 60s functions,
lower that number.

## Testing the chatbot

Once deployed, the widget is live on every page via the script tag in
`app/layout.tsx`. You can also call the API directly:

```bash
curl -X POST https://your-site.vercel.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test1234test1234", "message": "Are pets allowed?"}'
```

(`session_id` must be 8–64 characters of letters, digits, or hyphens — the
widget generates one automatically and stores it in `localStorage`.)

## What's placeholder

| What | Where |
| --- | --- |
| Hero, rooms, amenities, testimonials copy | `components/*.tsx` |
| Gallery/room "photos" (currently CSS gradients) | `components/Gallery.tsx`, `components/Rooms.tsx` |
| Address, phone, email shown on the page | `components/Location.tsx`, `components/CTA.tsx` |

The room names/rates in the landing page copy are still the placeholder
ones from early scaffolding (Tide Room, Horizon Room, Driftwood Loft) and
don't match what the chatbot will quote from the live Google Doc / live
Hotelogix rates — worth reconciling before this goes in front of real
guests, so the page and the bot agree on room names.

## Structure

```
app/                   Next.js pages, layout, global styles
components/             One file per landing-page section
public/widget.js        The chat widget (loaded via <script> in layout.tsx)
api/
  chat.py               POST /api/chat — the Vercel Python function
  _rag.py               Agent + tools (ported from the original rag.py)
  _pms.py               Hotelogix / mock PMS client (copied, unchanged)
  _kb.py                Live Google Doc knowledge base
  _memory.py            Redis-backed conversation + reservation state
requirements.txt         Python dependencies for api/chat.py
vercel.json              Function timeout config
```
