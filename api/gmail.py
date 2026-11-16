"""
POST /api/gmail   the email channel: the same bot as the website chat, for Gmail

Called by the Gmail connector (gmail-connector.gs, a Google Apps Script running
in the hotel's Gmail account) for each new guest email:

    POST /api/gmail
    X-Email-Key: <EMAIL_CHANNEL_KEY>
    {"thread_id": "...", "message_id": "...", "from_name": "...", "from_email": "...",
     "subject": "...", "text": "..."}

    -> {"status": "ok", "answer": "...", "handoff": false}
    -> {"status": "processing"}   still working on this message: ask again later

Each Gmail thread is one conversation (thread id "email:<gmail thread id>"), so
the bot remembers the thread, and a guest replying YES to a reservation summary
places the hold exactly as in the website chat.

Each Gmail message is answered once: if the connector times out and asks again,
it gets the same answer back instead of a second, different one.
"""
# Named gmail.py, not email.py: a module called "email" would shadow Python's
# built-in email package, which sending emails depends on.
import hmac
import json
import logging
import os
import re
import sys
from pathlib import Path

# Vercel loads this file by path, so add its folder for the sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import _booking as booking
import _memory as memory
import _rag as rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("email")

app = FastAPI(title="Casa Alon email channel")

EMAIL_CHANNEL_KEY = os.getenv("EMAIL_CHANNEL_KEY", "")
PER_THREAD_PER_HOUR = int(os.getenv("EMAIL_RATE_PER_THREAD_PER_HOUR", "10"))
PER_SENDER_PER_DAY = int(os.getenv("EMAIL_RATE_PER_SENDER_PER_DAY", "30"))
ANSWER_CACHE_SECONDS = 2 * 86400
PROCESSING_SECONDS = 5 * 60  # after this, a stuck "processing" marker can be retried

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
EMAIL_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class EmailRequest(BaseModel):
    thread_id: str
    message_id: str
    from_email: str
    from_name: str = Field(default="", max_length=200)
    subject: str = Field(default="", max_length=300)
    text: str = Field(min_length=1, max_length=6000)


def _rate_allow(key: str, limit: int, window_seconds: int) -> bool:
    r = memory._redis()
    if not r:
        return True
    try:
        full_key = f"casaalon:rate:{key}:{window_seconds}"
        count = r.incr(full_key)
        if count == 1:
            r.expire(full_key, window_seconds)
        return count <= limit
    except Exception:
        log.exception("Rate limiter error for %s, allowing the request", key)
        return True


def _clean_header_text(value: str) -> str:
    # Names and subjects go into a one-line note for the bot: no line breaks or brackets.
    return re.sub(r"\s+", " ", re.sub(r"[\r\n\[\]]+", " ", value)).strip()


@app.post("/api/gmail")
@app.post("/gmail")
def gmail(req: EmailRequest, background: BackgroundTasks, x_email_key: str = Header(default="")):
    if not EMAIL_CHANNEL_KEY:
        raise HTTPException(status_code=503, detail="The email channel is not set up (EMAIL_CHANNEL_KEY)")
    if not hmac.compare_digest(x_email_key, EMAIL_CHANNEL_KEY):
        raise HTTPException(status_code=401, detail="Wrong key")
    if not (ID_PATTERN.match(req.thread_id) and ID_PATTERN.match(req.message_id)):
        raise HTTPException(status_code=400, detail="Invalid thread or message id")
    sender = req.from_email.strip().lower()
    if not EMAIL_PATTERN.match(sender):
        raise HTTPException(status_code=400, detail="Invalid sender address")

    r = memory._redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis is required for the email channel")

    # Answer each Gmail message once, even if the connector asks again.
    done_key = f"casaalon:email_done:{req.message_id}"
    busy_key = f"casaalon:email_busy:{req.message_id}"
    cached = r.get(done_key)
    if cached:
        return json.loads(cached)
    if not r.set(busy_key, "1", nx=True, ex=PROCESSING_SECONDS):
        return {"status": "processing"}

    if not (_rate_allow(f"et:{req.thread_id}", PER_THREAD_PER_HOUR, 3600)
            and _rate_allow(f"es:{sender}", PER_SENDER_PER_DAY, 86400)):
        r.delete(busy_key)
        raise HTTPException(status_code=429, detail="Too many emails from this thread or sender")

    thread = f"email:{req.thread_id}"
    name, subject = _clean_header_text(req.from_name), _clean_header_text(req.subject)
    question = (f"[Email from {name + ' ' if name else ''}<{sender}>, subject: {subject or '(none)'}]\n"
                f"{req.text.strip()}")
    try:
        result = rag.answer(question, thread_id=thread)
    except Exception:
        log.exception("Failed to answer %s", thread)
        r.delete(busy_key)
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable")

    response = {"status": "ok", "answer": result["answer"], "handoff": result["handoff"]}
    r.set(done_key, json.dumps(response), ex=ANSWER_CACHE_SECONDS)
    r.delete(busy_key)
    if result["handoff"]:
        background.add_task(booking.notify_handoff, thread, req.text.strip()[:1000], result["answer"],
                            contact=sender, subject=subject)
    return response
