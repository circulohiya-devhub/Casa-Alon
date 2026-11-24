"""
Facebook Messenger worker: /api/messenger_worker

Called by our own webhook (api/messenger.py), directly or through Upstash
QStash, once per guest message. Writes the reply with the same bot as the
website chat and Gmail, and sends it through Messenger.

Safe to call more than once for the same message: each message is answered
once, and messages from one guest are answered in order.
"""
import hmac
import json
import logging
import re
import sys
import time
from pathlib import Path

# Vercel loads this file by path, so add its folder for the sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

import _booking as booking
import _memory as memory
import _messenger as fb
import _rag as rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("messenger.worker")

app = FastAPI(title="Casa Alon Messenger worker")

DONE_SECONDS = 2 * 86400
USER_LOCK_SECONDS = 240   # one message at a time per guest
WAIT_FOR_TURN_SECONDS = 120
SORRY = ("Sorry, I'm having trouble answering right now. A staff member will reply here soon, "
         "or you can call our front desk at " + booking.FRONT_DESK + ".")


def _rate_allow(r, psid: str) -> bool:
    key = f"casaalon:rate:fb:{psid}:3600"
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, 3600)
        return count <= fb.PER_USER_PER_HOUR
    except Exception:
        log.exception("Rate limiter error for %s, allowing the message", psid)
        return True


@app.post("/api/messenger_worker")
@app.post("/messenger_worker")
async def work(request: Request):
    if not fb.configured():
        raise HTTPException(status_code=503, detail="Messenger is not set up")
    try:
        job = json.loads(await request.body())
        psid, mid, text = str(job["psid"]), str(job["mid"]), str(job["text"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid job")
    if not hmac.compare_digest(request.headers.get("x-worker-key", ""), fb.worker_key(mid)):
        raise HTTPException(status_code=401, detail="Wrong key")
    if not (fb.PSID_PATTERN.match(psid) and fb.MID_PATTERN.match(mid)):
        raise HTTPException(status_code=400, detail="Invalid ids")

    r = memory._redis()
    if not r:
        raise HTTPException(status_code=503, detail="Redis is required for Messenger")

    done_key = f"casaalon:fb_done:{mid}"
    if r.get(done_key):
        return {"status": "already answered"}
    # Claim this message, so a retry or a second delivery doesn't answer it twice.
    if not r.set(f"casaalon:fb_busy:{mid}", "1", nx=True, ex=USER_LOCK_SECONDS):
        return {"status": "already in progress"}

    # Answer one guest's messages in order.
    user_lock = f"casaalon:fb_user:{psid}"
    waited = 0.0
    while not r.set(user_lock, mid, nx=True, ex=USER_LOCK_SECONDS):
        if waited >= WAIT_FOR_TURN_SECONDS:
            r.delete(f"casaalon:fb_busy:{mid}")
            return JSONResponse({"status": "busy, retry"}, status_code=503)
        time.sleep(1.5)
        waited += 1.5

    try:
        if fb.is_paused(psid):
            r.set(done_key, "paused", ex=DONE_SECONDS)
            return {"status": "paused: staff are handling this conversation"}
        if not _rate_allow(r, psid):
            r.set(done_key, "rate limited", ex=DONE_SECONDS)
            return {"status": "rate limited"}

        thread = f"facebook:{psid}"
        fb.typing(psid)
        name = fb.guest_name(psid)
        question = f"[Messenger message from {name or 'a guest'}]\n{text}"
        try:
            result = rag.answer(question, thread_id=thread)
        except Exception:
            log.exception("Failed to answer %s", thread)
            fb.send_text(psid, SORRY)
            r.set(done_key, "failed", ex=DONE_SECONDS)
            booking.notify_handoff(thread, re.sub(r"\s+", " ", text)[:1000],
                                   "(The bot could not answer.)", subject=name)
            fb.pause(psid, "the bot could not answer")
            return {"status": "failed, handed to staff"}

        sent = fb.send_text(psid, result["answer"])
        r.set(done_key, "answered" if sent else "send failed", ex=DONE_SECONDS)
        if result["handoff"]:
            fb.pause(psid, "handed off to staff")
            booking.notify_handoff(thread, text[:1000], result["answer"], subject=name)
        return {"status": "answered" if sent else "send failed", "handoff": result["handoff"]}
    finally:
        if r.get(user_lock) == mid:
            r.delete(user_lock)
        r.delete(f"casaalon:fb_busy:{mid}")
