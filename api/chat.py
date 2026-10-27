"""
POST /api/chat   {session_id, message} -> {answer, handoff}

Vercel auto-detects the `app` variable below as a Python serverless
function and serves it at /api/chat (this file's path).

Ported from channels/web.py + core.py in the original FastAPI backend:
  - Same request/response shape and session-id validation.
  - Same staff-webhook notification on handoff or a new reservation.
  - Rate limiting is Redis-backed here instead of in-process (see below) —
    everything else about it is unchanged.

One deliberate gap: this only implements the website channel. Facebook,
WhatsApp, and Viber from the original backend aren't ported here — add them
back (likely on separate, persistent hosting, since webhook-based channels
don't need Vercel's request/response model) if/when those go live.
"""
import json
import logging
import os
import re
import sys
from pathlib import Path

# Vercel's Python runtime loads this file directly by path (not as a normal
# package import), so this directory isn't automatically searched for the
# sibling modules below (_rag, _pms, _kb, _memory). Add it to sys.path
# explicitly, before importing any of them.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

import _rag as rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chat")

app = FastAPI(title="Casa Alon Chat")

STAFF_WEBHOOK_URL = os.getenv("STAFF_WEBHOOK_URL", "")
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("WEB_ALLOWED_ORIGINS", "").split(",") if o.strip()]
PER_SESSION_PER_MINUTE = int(os.getenv("WEB_RATE_PER_MINUTE", "8"))
PER_IP_PER_MINUTE = int(os.getenv("WEB_RATE_PER_IP_PER_MINUTE", "30"))
PER_IP_PER_DAY = int(os.getenv("WEB_RATE_PER_IP_PER_DAY", "300"))
MAX_MESSAGE_CHARS = 1000

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")


# ------------------------------------------------------------------
# Rate limiting — Redis-backed (simple fixed-window INCR+EXPIRE), since
# an in-process limiter like the original's wouldn't be shared across
# Vercel's serverless instances. Degrades to "no limiting" if Redis isn't
# configured, same as the rest of _memory.py.
# ------------------------------------------------------------------
def _rate_allow(key: str, limit: int, window_seconds: int) -> bool:
    from _memory import _redis  # reuse the same lazily-initialized client

    r = _redis()
    if not r:
        return True  # no Redis configured — fail open rather than block guests
    try:
        full_key = f"casaalon:rate:{key}:{window_seconds}"
        count = r.incr(full_key)
        if count == 1:
            r.expire(full_key, window_seconds)
        return count <= limit
    except Exception:
        log.exception("Rate limiter error for %s — allowing the request", key)
        return True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True  # non-browser clients; still rate limited
    if not ALLOWED_ORIGINS:
        return True  # not configured — same-origin widget usage needs nothing set
    if origin.rstrip("/") in ALLOWED_ORIGINS:
        return True
    return origin.rstrip("/").endswith(request.headers.get("host", "\0"))


def notify_staff(channel: str, user_id: str, question: str, answer: str,
                 event: str = "handoff", reservation: dict | None = None) -> None:
    log.info("Staff alert (%s): %s:%s", event, channel, user_id)
    if not STAFF_WEBHOOK_URL:
        return
    payload = {
        "event": event, "channel": channel, "user_id": user_id,
        "question": question, "bot_answer": answer, "reservation": reservation,
    }
    try:
        requests.post(
            STAFF_WEBHOOK_URL,
            data=json.dumps(payload, default=str),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except requests.RequestException:
        log.exception("Could not reach STAFF_WEBHOOK_URL")


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatResponse(BaseModel):
    answer: str
    handoff: bool


@app.post("/api/chat", response_model=ChatResponse)
@app.post("/chat", response_model=ChatResponse)  # in case Vercel forwards the sub-path only
def chat(req: ChatRequest, request: Request, background: BackgroundTasks):
    if not _origin_allowed(request):
        raise HTTPException(status_code=403, detail="This website is not allowed to use the chat")
    if not SESSION_ID_PATTERN.match(req.session_id):
        raise HTTPException(status_code=400, detail="Invalid session")

    ip = _client_ip(request)
    if not (
        _rate_allow(f"s:{req.session_id}", PER_SESSION_PER_MINUTE, 60)
        and _rate_allow(f"ip:{ip}", PER_IP_PER_MINUTE, 60)
        and _rate_allow(f"ipday:{ip}", PER_IP_PER_DAY, 86400)
    ):
        raise HTTPException(status_code=429, detail="Too many messages")

    text = req.message.strip()
    try:
        result = rag.answer(text, thread_id=f"web:{req.session_id}")
    except Exception:
        log.exception("Failed to answer web:%s", req.session_id)
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable")

    if result.get("reservation"):
        background.add_task(notify_staff, "web", req.session_id, text, result["answer"],
                            "reservation", result["reservation"])
    if result["handoff"]:
        background.add_task(notify_staff, "web", req.session_id, text, result["answer"])
    return result


@app.get("/api/chat/health")
def health():
    return {"status": "ok"}
