"""
Facebook Messenger webhook: /api/messenger

GET  Meta's one-time check when the webhook is set up (hub.verify_token must
     match FB_VERIFY_TOKEN; we echo hub.challenge back).
POST Messages from guests. We check Meta's signature, hand each message to
     the worker (api/messenger_worker.py), and answer Meta within its
     5-second limit. The worker writes and sends the reply.
"""
# Vercel loads this file by path, so add its folder for the sibling modules.
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

import _booking as booking
import _messenger as fb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("messenger.webhook")

app = FastAPI(title="Casa Alon Messenger webhook")


@app.get("/api/messenger")
@app.get("/messenger")
def verify(request: Request):
    q = request.query_params
    if (q.get("hub.mode") == "subscribe" and fb.VERIFY_TOKEN
            and q.get("hub.verify_token") == fb.VERIFY_TOKEN):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/api/messenger")
@app.post("/messenger")
async def receive(request: Request):
    raw = await request.body()
    if not fb.valid_meta_signature(raw, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    base = booking.public_base_url()
    if not base:
        log.error("PUBLIC_BASE_URL is not set, so the worker can't be reached")
    else:
        for job in fb.jobs_from_webhook(payload):
            fb.dispatch(job, f"{base}/api/messenger_worker")
    # Always acknowledge a correctly signed delivery: a failure here would make
    # Meta retry, and eventually unsubscribe the app from the Page.
    return PlainTextResponse("EVENT_RECEIVED")
