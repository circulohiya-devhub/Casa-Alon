"""
Facebook Messenger channel: shared code for the webhook (api/messenger.py) and
the worker that writes the replies (api/messenger_worker.py).

Why two endpoints: Meta expects the webhook to answer within 5 seconds, or it
retries and, after an hour of failures, unsubscribes the app from the Page.
The bot can take up to a minute (placing a hold), so the webhook only checks
Meta's signature and hands each message to the worker, then answers Meta
straight away. The worker runs as its own request, up to its time limit.

How the hand-off happens:
  - Default: the webhook calls the worker URL itself and doesn't wait for the
    reply. No extra service needed.
  - If QSTASH_TOKEN is set: through Upstash QStash, a queue that calls the
    worker and retries on failure. Use this if replies ever go missing.

Each guest is one conversation, thread id "facebook:<page-scoped user id>".
"""
import hashlib
import hmac
import json
import logging
import os
import re
import time

import requests

import _memory as memory

log = logging.getLogger("messenger")

PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
APP_SECRET = os.getenv("FB_APP_SECRET", "")
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "")
GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

# When a staff member replies from the Page inbox, or a guest is handed off,
# the bot stays quiet in that conversation for this long.
STAFF_PAUSE_HOURS = float(os.getenv("MESSENGER_STAFF_PAUSE_HOURS", "12"))
PER_USER_PER_HOUR = int(os.getenv("MESSENGER_RATE_PER_USER_PER_HOUR", "30"))

QSTASH_TOKEN = os.getenv("QSTASH_TOKEN", "")
QSTASH_URL = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")

# Marks the bot's own messages, so their echoes aren't mistaken for staff replies.
BOT_METADATA = "casa-alon-bot"
MAX_TEXT = 2000  # Messenger's limit per message
PSID_PATTERN = re.compile(r"^\d{5,30}$")
MID_PATTERN = re.compile(r"^[A-Za-z0-9_.:=+/-]{1,300}$")


def configured() -> bool:
    return bool(PAGE_ACCESS_TOKEN and APP_SECRET and VERIFY_TOKEN)


# ------------------------------------------------------------------
# Signatures
# ------------------------------------------------------------------
def valid_meta_signature(raw_body: bytes, header: str) -> bool:
    """X-Hub-Signature-256: "sha256=" + HMAC-SHA256 of the raw body with the App Secret."""
    if not (APP_SECRET and header and header.startswith("sha256=")):
        return False
    expected = hmac.new(APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:].lower())


def worker_key(mid: str) -> str:
    """Proves a worker request came from our own webhook (one key per message)."""
    return hmac.new(APP_SECRET.encode(), f"messenger-worker:{mid}".encode(), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------
# Staff takeover: the bot pauses in a conversation
# ------------------------------------------------------------------
def _pause_key(psid: str) -> str:
    return f"casaalon:fb_paused:{psid}"


def pause(psid: str, reason: str) -> None:
    r = memory._redis()
    if r and STAFF_PAUSE_HOURS > 0:
        r.set(_pause_key(psid), reason, ex=int(STAFF_PAUSE_HOURS * 3600))
        log.info("Bot paused for %s (%s)", psid, reason)


def is_paused(psid: str) -> bool:
    r = memory._redis()
    return bool(r and r.get(_pause_key(psid)))


# ------------------------------------------------------------------
# Hand a message to the worker
# ------------------------------------------------------------------
def dispatch(job: dict, worker_url: str) -> None:
    body = json.dumps(job)
    key = worker_key(job["mid"])
    if QSTASH_TOKEN:
        try:
            resp = requests.post(
                f"{QSTASH_URL}/v2/publish/{worker_url}",
                data=body,
                headers={
                    "Authorization": f"Bearer {QSTASH_TOKEN}",
                    "Content-Type": "application/json",
                    "Upstash-Forward-X-Worker-Key": key,
                    "Upstash-Deduplication-Id": hashlib.sha256(job["mid"].encode()).hexdigest(),
                    "Upstash-Retries": "2",
                },
                timeout=4,
            )
            resp.raise_for_status()
            return
        except requests.RequestException:
            log.exception("QStash publish failed for %s, calling the worker directly", job["mid"])
    try:
        # Don't wait for the reply: the worker keeps running after we hang up.
        requests.post(worker_url, data=body, timeout=(3, 1.5),
                      headers={"Content-Type": "application/json", "X-Worker-Key": key})
    except requests.ReadTimeout:
        pass  # expected: the worker is busy writing the answer
    except requests.RequestException:
        log.exception("Could not start the worker for %s", job["mid"])


# ------------------------------------------------------------------
# Messenger Send API
# ------------------------------------------------------------------
def _send(payload: dict) -> bool:
    try:
        resp = requests.post(f"{GRAPH}/me/messages", params={"access_token": PAGE_ACCESS_TOKEN},
                             json=payload, timeout=15)
        if resp.status_code != 200:
            log.error("Messenger send failed (%s): %s", resp.status_code, resp.text[:500])
            return False
        return True
    except requests.RequestException:
        log.exception("Messenger send failed")
        return False


def typing(psid: str) -> None:
    _send({"recipient": {"id": psid}, "sender_action": "typing_on"})


def split_text(text: str, limit: int = MAX_TEXT) -> list[str]:
    """Split a long reply into messages under Messenger's limit, at paragraph or
    sentence breaks where possible."""
    chunks, rest = [], text.strip()
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(". ", 0, limit) + 1
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def send_text(psid: str, text: str) -> bool:
    ok = True
    for chunk in split_text(text):
        ok = _send({
            "recipient": {"id": psid},
            "messaging_type": "RESPONSE",
            "message": {"text": chunk, "metadata": BOT_METADATA},
        }) and ok
    return ok


def guest_name(psid: str) -> str:
    """The guest's name from their Messenger profile (cached for a week)."""
    r = memory._redis()
    key = f"casaalon:fb_name:{psid}"
    if r:
        cached = r.get(key)
        if cached is not None:
            return cached
    name = ""
    try:
        resp = requests.get(f"{GRAPH}/{psid}", timeout=8,
                            params={"fields": "first_name,last_name", "access_token": PAGE_ACCESS_TOKEN})
        if resp.status_code == 200:
            data = resp.json()
            name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
    except (requests.RequestException, ValueError):
        log.warning("Could not look up the Messenger name for %s", psid)
    name = re.sub(r"[\r\n\[\]]+", " ", name).strip()[:100]
    if r:
        r.set(key, name, ex=7 * 86400)
    return name


# ------------------------------------------------------------------
# Reading Meta's webhook events
# ------------------------------------------------------------------
def jobs_from_webhook(payload: dict) -> list[dict]:
    """Turn a webhook payload into work for the worker. Echoes of staff replies
    pause the bot; delivery and read receipts are ignored."""
    jobs = []
    if payload.get("object") != "page":
        return jobs
    for entry in payload.get("entry") or []:
        for event in entry.get("messaging") or []:
            sender = str((event.get("sender") or {}).get("id", ""))
            recipient = str((event.get("recipient") or {}).get("id", ""))
            message = event.get("message") or {}
            postback = event.get("postback") or {}

            if message.get("is_echo"):
                # Sent by the Page. If it isn't the bot's own message, a staff
                # member is replying from the inbox: step aside.
                if message.get("metadata") != BOT_METADATA and PSID_PATTERN.match(recipient):
                    pause(recipient, "staff replied from the Page inbox")
                continue
            if not PSID_PATTERN.match(sender):
                continue

            if message:
                mid = str(message.get("mid", ""))
                text = (message.get("text") or "").strip()
                if message.get("attachments") and not text:
                    text = ("[The guest sent a photo or file, which you can't open. Tell them a staff "
                            "member will check it, and hand off to staff.]")
                elif message.get("attachments"):
                    text += ("\n[The guest also sent a photo or file, which you can't open. Tell them "
                             "a staff member will check it, and hand off to staff.]")
            elif postback:
                # Buttons such as "Get Started": treat the button's title as the message.
                mid = str(postback.get("mid") or f"postback-{sender}-{event.get('timestamp', '')}")
                text = (postback.get("title") or postback.get("payload") or "").strip()
            else:
                continue  # delivery, read, reactions, ...

            if text and MID_PATTERN.match(mid):
                jobs.append({"psid": sender, "mid": mid, "text": text[:4000],
                             "timestamp": event.get("timestamp") or int(time.time() * 1000)})
    return jobs
