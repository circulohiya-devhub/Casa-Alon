# Casa Alon

A landing page for Casa Alon, a boutique hotel concept, with an "Ask Alon"
chatbot built on LangChain.js (RAG over a small knowledge base, using
Gemini for embeddings and chat). Built with Next.js so it deploys to
Vercel with no extra configuration.

Everything here — copy, pricing, address, phone/email, photos, and the
knowledge base — is placeholder content. Treat this as a working
scaffold to replace with your real property details before launch.

## What's placeholder and where to change it

| What | Where |
| --- | --- |
| Hero, rooms, amenities, testimonials copy | `components/*.tsx` |
| Gallery/room "photos" (currently CSS gradients) | `components/Gallery.tsx`, `components/Rooms.tsx` — swap the `style={{ background: ... }}` blocks for `next/image` |
| Address, phone, email | `components/Location.tsx`, `components/CTA.tsx` |
| Chatbot's knowledge | `lib/knowledge.ts` |

## Running locally

```bash
npm install
cp .env.example .env.local   # then fill in the values described below
npm run dev
```

Only `GOOGLE_API_KEY` is required — get one from [Google AI Studio](https://aistudio.google.com/app/apikey). The LangSmith and Upstash Redis variables in `.env.example` are both optional; see below.

## How the chatbot works

`app/api/chat/route.ts` is a standard Next.js API route (Vercel serverless
function, Node runtime — same pattern as your portfolio site's chat
backend). On each message it:

1. Embeds the question and does a similarity search against an in-memory
   vector store (`lib/rag.ts`), built at cold start from the documents in
   `lib/knowledge.ts`.
2. Sends the retrieved chunks plus the recent conversation to
   `gemini-3.8-flash` with a system prompt that tells it to only answer
   from that context, and to point guests to `stay@casaalon.com` for
   anything it doesn't know (bookings included — it's not wired to
   actually create a reservation).
3. Returns the reply to `components/ChatWidget.tsx`, the floating bubble
   in the bottom-right corner.

### LangSmith tracing (optional)

Set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT`
(from [smith.langchain.com](https://smith.langchain.com)) and every chat
turn shows up as a run in your LangSmith dashboard — retrieved context,
prompt, and model response included. The route handler wraps its logic in
`traceable()` from the `langsmith` package for this. Leave these unset and
tracing is just skipped, nothing else changes.

### Persistent chat memory via Upstash Redis (optional)

Set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` (from an
[Upstash](https://upstash.com) Redis database — the REST API credentials,
not the Redis connection string) and each visitor's conversation is saved
server-side, keyed by a session ID the browser generates and stores in
`localStorage`. Reopening the site restores their previous conversation
instead of starting over. History is capped at the last 20 turns and
expires after 7 days (`lib/redis.ts`).

Leave these unset and the chatbot still works — it just falls back to the
original behavior: history lives only in the browser tab's memory and
resets on reload.

### Growing past the placeholder knowledge base

`lib/knowledge.ts` is a flat array of short documents — fine for getting
started, but worth outgrowing deliberately:

- **More content / content that changes often**: replace the static
  array with a loader (e.g. LangChain's Google Docs/Drive loader) that
  pulls from a live doc, the same approach as your hotel-inquiry-rag
  project's knowledge base.
- **Bigger knowledge base**: swap `MemoryVectorStore` in `lib/rag.ts` for
  a persistent store (Vercel's Postgres/pgvector integration, Pinecone,
  Supabase) — nothing else in the route needs to change.
- **Reuse your existing RAG backend instead**: if you'd rather keep using
  the Python/FastAPI RAG service from the hotel-inquiry-rag project
  (so there's one knowledge base and one Hotelogix integration serving
  every channel) rather than running a second LangChain.js pipeline
  here, delete `app/api/chat/route.ts` and `lib/rag.ts`, and point the
  `fetch("/api/chat", ...)` call in `components/ChatWidget.tsx` at that
  service's URL instead.
- **Live rates/availability**: once the Hotelogix API is wired in on
  whichever backend you choose, add a tool/function call so the model
  can check real availability rather than quoting the static rates in
  `lib/knowledge.ts`.
- **Conversation memory across requests**: already wired in — see
  "Persistent chat memory via Upstash Redis" above.

## Deploying

1. Push this project to a new GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Casa Alon landing page"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```
2. In Vercel, "Add New Project" → import the repo. Vercel auto-detects
   Next.js, so the default build settings work as-is.
3. Add the `GOOGLE_API_KEY` environment variable in the Vercel project
   settings (Settings → Environment Variables) before the first deploy,
   or redeploy after adding it.

## Structure

```
app/
  layout.tsx        # fonts + metadata
  page.tsx           # assembles all sections
  globals.css
  api/chat/route.ts  # RAG chat endpoint
components/           # one file per section, plus ChatWidget
lib/
  knowledge.ts        # placeholder knowledge base
  rag.ts              # vector store + retrieval
```
