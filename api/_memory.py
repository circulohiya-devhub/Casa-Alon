"""
Cross-request state for the chat, backed by Redis (Upstash).

On a single long-running server, rag.py could keep conversation history and
the "reservation prepared, waiting for YES" state in plain Python
dictionaries, because the same process handles every message. On Vercel,
nothing guarantees that: a guest's "YES" a minute after seeing a reservation
summary can land on a different serverless instance than the one that
prepared it. So everything that needs to survive between two separate guest
messages lives here instead, in Redis.

What does NOT need to be here: the Google Doc knowledge base cache, the
Hotelogix access-key cache, and the PMS search-result cache (see _kb.py and
_pms.py) are all pure efficiency optimizations. Losing them on a cold start
just means one extra re-fetch or re-login, never a wrong answer or a bad
booking, so they're left as simple in-process caches.

If no Redis credentials are found (see _redis() below for the two naming
conventions checked), every function here degrades to "no memory":
conversation history won't persist between messages and reservations can
still be prepared and confirmed within a single exchange, but not across a
long gap. That's enough to run and test the bot; set the Redis env vars for
real guest traffic.
"""
import json
import logging
import os
import time

log = logging.getLogger("memory")

HISTORY_TTL_SECONDS = 60 * 60 * 24       # 24 hours, matches the widget's own history TTL
PENDING_TTL_SECONDS = 60 * 20            # a little past PENDING_MINUTES, as a backstop
BOOKED_AT_TTL_SECONDS = 60 * 60 * 24     # only need "within the last 24h"
MAX_HISTORY_TURNS = 20                   # stored turns (user+assistant pairs count as 2)

_client = None
_client_checked = False


def _redis():
    """
    Checks two naming conventions, in order:
      1. UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN — the canonical
         Upstash names, set if you created the database directly at
         console.upstash.com.
      2. KV_REST_API_URL / KV_REST_API_TOKEN — Vercel's own legacy "KV"
         naming, which is what the Vercel Storage tab / Marketplace
         integration actually injects when you connect an Upstash database
         that way, even though the database itself is plain Upstash Redis.
    """
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    if not (url and token):
        log.warning(
            "No Redis credentials found (checked UPSTASH_REDIS_REST_URL/TOKEN and "
            "KV_REST_API_URL/TOKEN) — chat memory will not persist between messages"
        )
        return None
    from upstash_redis import Redis
    _client = Redis(url=url, token=token)
    return _client


def _key(kind: str, thread_id: str) -> str:
    return f"casaalon:{kind}:{thread_id}"


# ------------------------------------------------------------------
# Conversation history: list of {"role": "user"|"assistant", "content": str}
# ------------------------------------------------------------------
def load_history(thread_id: str) -> list[dict]:
    r = _redis()
    if not r:
        return []
    try:
        raw = r.get(_key("history", thread_id))
        return json.loads(raw) if raw else []
    except Exception:
        log.exception("Redis load_history failed for %s", thread_id)
        return []


def save_history(thread_id: str, turns: list[dict]) -> None:
    r = _redis()
    if not r:
        return
    try:
        trimmed = turns[-MAX_HISTORY_TURNS:]
        r.set(_key("history", thread_id), json.dumps(trimmed), ex=HISTORY_TTL_SECONDS)
    except Exception:
        log.exception("Redis save_history failed for %s", thread_id)


# ------------------------------------------------------------------
# Turn counter + the guest's literal last message (prepare/confirm guard)
# ------------------------------------------------------------------
def next_turn(thread_id: str) -> int:
    r = _redis()
    if not r:
        return 1
    try:
        n = r.incr(_key("turn", thread_id))
        r.expire(_key("turn", thread_id), HISTORY_TTL_SECONDS)
        return int(n)
    except Exception:
        log.exception("Redis next_turn failed for %s", thread_id)
        return 1


def get_turn(thread_id: str) -> int:
    r = _redis()
    if not r:
        return 1
    try:
        n = r.get(_key("turn", thread_id))
        return int(n) if n else 0
    except Exception:
        log.exception("Redis get_turn failed for %s", thread_id)
        return 0


def set_last_message(thread_id: str, text: str) -> None:
    r = _redis()
    if not r:
        return
    try:
        r.set(_key("last_message", thread_id), text, ex=HISTORY_TTL_SECONDS)
    except Exception:
        log.exception("Redis set_last_message failed for %s", thread_id)


def get_last_message(thread_id: str) -> str:
    r = _redis()
    if not r:
        return ""
    try:
        return r.get(_key("last_message", thread_id)) or ""
    except Exception:
        log.exception("Redis get_last_message failed for %s", thread_id)
        return ""


# ------------------------------------------------------------------
# Pending reservation: prepared, waiting for the guest's YES
# ------------------------------------------------------------------
def set_pending(thread_id: str, data: dict) -> None:
    r = _redis()
    if not r:
        return
    try:
        r.set(_key("pending", thread_id), json.dumps(data, default=str), ex=PENDING_TTL_SECONDS)
    except Exception:
        log.exception("Redis set_pending failed for %s", thread_id)


def get_pending(thread_id: str) -> dict | None:
    r = _redis()
    if not r:
        return None
    try:
        raw = r.get(_key("pending", thread_id))
        return json.loads(raw) if raw else None
    except Exception:
        log.exception("Redis get_pending failed for %s", thread_id)
        return None


def clear_pending(thread_id: str) -> None:
    r = _redis()
    if not r:
        return
    try:
        r.delete(_key("pending", thread_id))
    except Exception:
        log.exception("Redis clear_pending failed for %s", thread_id)


# ------------------------------------------------------------------
# Bookings made in the last 24h, for the daily-per-guest limit
# ------------------------------------------------------------------
def recent_booking_count(thread_id: str) -> int:
    r = _redis()
    if not r:
        return 0
    try:
        raw = r.get(_key("booked_at", thread_id))
        timestamps = json.loads(raw) if raw else []
        cutoff = time.time() - 86400
        return len([t for t in timestamps if t > cutoff])
    except Exception:
        log.exception("Redis recent_booking_count failed for %s", thread_id)
        return 0


def record_booking(thread_id: str) -> None:
    r = _redis()
    if not r:
        return
    try:
        raw = r.get(_key("booked_at", thread_id))
        timestamps = json.loads(raw) if raw else []
        cutoff = time.time() - 86400
        timestamps = [t for t in timestamps if t > cutoff] + [time.time()]
        r.set(_key("booked_at", thread_id), json.dumps(timestamps), ex=BOOKED_AT_TTL_SECONDS)
    except Exception:
        log.exception("Redis record_booking failed for %s", thread_id)
