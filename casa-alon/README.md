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
cp .env.example .env.local   # then add your Google API key
npm run dev
```

Get a `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/app/apikey) — it's used for both the Gemini chat model and the embeddings model in the chatbot.

## How the chatbot works

`app/api/chat/route.ts` is a standard Next.js API route (Vercel serverless
function, Node runtime — same pattern as your portfolio site's chat
backend). On each message it:

1. Embeds the question and does a similarity search against an in-memory
   vector store (`lib/rag.ts`), built at cold start from the documents in
   `lib/knowledge.ts`.
2. Sends the retrieved chunks plus the recent conversation to
   `gemini-1.5-flash` with a system prompt that tells it to only answer
   from that context, and to point guests to `stay@casaalon.com` for
   anything it doesn't know (bookings included — it's not wired to
   actually create a reservation).
3. Returns the reply to `components/ChatWidget.tsx`, the floating bubble
   in the bottom-right corner.

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
- **Conversation memory across requests**: this version is stateless
  between page loads (history only lives in the browser tab). If you
  want persisted conversations, Upstash Redis via Vercel Storage — the
  same service used on the portfolio site — is a natural fit.

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
