"""
Email-confirmed reservations.

Flow:
  1. In chat, prepare_reservation (in _rag.py) checks the live rate, then calls
     start_email_confirmation(): the details are saved in Redis under a random
     token, and the guest is emailed a summary with a Confirm button.
  2. The button opens GET /api/confirm?token=..., a page showing the summary
     with one more Confirm button. Email security scanners open links
     automatically, so only the button on that page (a POST) books anything.
  3. POST /api/confirm calls place_hold(): price and availability are checked
     again, the reservation is saved ON HOLD in the PMS with its holdTill
     deadline, the guest is emailed the result, and staff are alerted.

Each token works once and expires after CONFIRM_LINK_HOURS.
"""
import html
import json
import logging
import os
import secrets
import smtplib
import ssl
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests

import _memory as memory
import _pms as pms

log = logging.getLogger("booking")

HOTEL_NAME = "Casa Alon Hotel"
FRONT_DESK = "+63 917 000 0000"
HOTEL_TIMEZONE = ZoneInfo("Asia/Manila")

CONFIRM_LINK_HOURS = int(os.getenv("CONFIRM_LINK_HOURS", "24"))
MAX_CONFIRM_EMAILS_PER_GUEST_PER_DAY = int(os.getenv("MAX_CONFIRM_EMAILS_PER_GUEST_PER_DAY", "3"))
MAX_BOOKINGS_PER_GUEST_PER_DAY = int(os.getenv("MAX_BOOKINGS_PER_GUEST_PER_DAY", "2"))
STAFF_WEBHOOK_URL = os.getenv("STAFF_WEBHOOK_URL", "")

# Email sending (SMTP). Defaults suit a Gmail account with an app password.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "") or SMTP_USER
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", HOTEL_NAME)
# Where staff alerts (handoffs, holds placed, failures) are emailed.
# Defaults to the sending account itself, so alerts never silently go nowhere.
STAFF_ALERT_EMAIL = os.getenv("STAFF_ALERT_EMAIL", "") or EMAIL_FROM

BRAND_COLOR = "#1F3A3D"
ACCENT_COLOR = "#C9962C"


def today() -> date:
    return datetime.now(HOTEL_TIMEZONE).date()


def hold_deadline(check_in: date, booking_date: date) -> date | None:
    """When an on-hold reservation expires, based on days until arrival.
    None means book & buy: too close to arrival for a hold."""
    lead = (check_in - booking_date).days
    if lead >= 30:
        return booking_date + timedelta(days=10)
    if lead >= 14:
        return booking_date + timedelta(days=5)
    if lead >= 7:
        return booking_date + timedelta(days=3)
    if lead >= 3:
        return booking_date + timedelta(days=1)
    return None


def public_base_url() -> str:
    """The site's address, for links in emails. PUBLIC_BASE_URL wins; otherwise
    Vercel's own production domain variable is used."""
    explicit = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    vercel = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip().rstrip("/")
    return f"https://{vercel}" if vercel else ""


# ------------------------------------------------------------------
# Confirmation tokens (Redis)
# ------------------------------------------------------------------
def _key(token: str) -> str:
    return f"casaalon:confirm:{token}"


def _require_redis():
    r = memory._redis()
    if not r:
        raise RuntimeError("Redis is required for email confirmations")
    return r


def get_confirmation(token: str) -> dict | None:
    if not token or len(token) > 100:
        return None
    try:
        raw = _require_redis().get(_key(token))
        return json.loads(raw) if raw else None
    except Exception:
        log.exception("Could not read confirmation %s", token[:8])
        return None


def is_claimed(token: str) -> bool:
    try:
        return bool(_require_redis().get(_key(token) + ":claimed"))
    except Exception:
        return False


def _claim(token: str) -> bool:
    """True for the first caller only, so a double click can't book twice."""
    r = _require_redis()
    return bool(r.set(_key(token) + ":claimed", "1", nx=True, ex=CONFIRM_LINK_HOURS * 3600))


def _count_email(thread: str) -> int:
    r = _require_redis()
    key = f"casaalon:confirm_emails:{thread}:{today().isoformat()}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 86400)
    return int(count)


# ------------------------------------------------------------------
# Email
# ------------------------------------------------------------------
def email_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD and EMAIL_FROM)


def send_email(to: str, subject: str, text: str, html_body: str) -> None:
    if not email_configured():
        raise RuntimeError("Email is not configured (SMTP_USER / SMTP_PASSWORD)")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=20) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls(context=context)
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)


def summary_rows(p: dict, hold_till: str | None) -> list[tuple[str, str]]:
    ci, co = date.fromisoformat(p["check_in"]), date.fromisoformat(p["check_out"])
    nights = (co - ci).days
    guests = f"{p['adults']} adult{'s' if p['adults'] != 1 else ''}"
    if p.get("children"):
        guests += f", {p['children']} child{'ren' if p['children'] != 1 else ''}"
    g = p["guest"]
    rows = [
        ("Room", f"{p['room_type']} ({p['rate_plan']})"),
        ("Dates", f"{ci:%B %d, %Y} to {co:%B %d, %Y} ({nights} night{'s' if nights != 1 else ''})"),
        ("Guests", guests),
        ("Total", f"{p['currency']} {p['total']:,.2f}"),
        ("Name", f"{g['first_name']} {g['last_name']}"),
        ("Email", g["email"]),
        ("Mobile", g["mobile"]),
    ]
    if hold_till:
        rows.append(("Held until", f"{date.fromisoformat(hold_till):%B %d, %Y}"))
    if p.get("cancellation"):
        rows.append(("Cancellation", p["cancellation"]))
    return rows


def _rows_html(rows) -> str:
    return "".join(
        f'<tr><td style="padding:6px 12px 6px 0;color:#5b6b6c;vertical-align:top">{html.escape(k)}</td>'
        f'<td style="padding:6px 0;color:#122321">{html.escape(v)}</td></tr>'
        for k, v in rows
    )


def _rows_text(rows) -> str:
    return "\n".join(f"{k}: {v}" for k, v in rows)


def _email_shell(title: str, body_html: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#FAF6EE;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background:{BRAND_COLOR};color:#FAF6EE;padding:18px 24px;font-size:18px">{html.escape(HOTEL_NAME)}</td></tr>
<tr><td style="padding:24px">
<h1 style="margin:0 0 16px;font-size:20px;color:#122321">{html.escape(title)}</h1>
{body_html}
<p style="margin:24px 0 0;color:#5b6b6c;font-size:13px">Questions? Call or Viber our front desk at {html.escape(FRONT_DESK)}.</p>
</td></tr></table></td></tr></table></body></html>"""


def _confirmation_request_email(p: dict, link: str) -> tuple[str, str, str]:
    rows = summary_rows(p, p.get("hold_till"))
    subject = f"Confirm your reservation at {HOTEL_NAME}"
    text = (
        f"Hi {p['guest']['first_name']},\n\n"
        "Here are the details of the reservation you asked for. Nothing is held yet.\n\n"
        f"{_rows_text(rows)}\n\n"
        f"To place this reservation on hold, open this link within {CONFIRM_LINK_HOURS} hours:\n{link}\n\n"
        "The down payment must be made by the \"Held until\" date, or the room is released. "
        "No payment is collected online.\n\n"
        "If you didn't ask for this, you can ignore this email.\n"
    )
    body = (
        f"<p style=\"color:#122321\">Hi {html.escape(p['guest']['first_name'])},</p>"
        "<p style=\"color:#122321\">Here are the details of the reservation you asked for. "
        "<strong>Nothing is held yet.</strong></p>"
        f'<table role="presentation" style="margin:12px 0;font-size:14px">{_rows_html(rows)}</table>'
        f'<p style="margin:20px 0"><a href="{html.escape(link)}" style="background:{ACCENT_COLOR};color:#122321;'
        'text-decoration:none;padding:12px 22px;border-radius:999px;display:inline-block;font-weight:bold">'
        "Confirm my reservation</a></p>"
        f"<p style=\"color:#122321;font-size:14px\">The link works for {CONFIRM_LINK_HOURS} hours. "
        "The down payment must be made by the \"Held until\" date, or the room is released. "
        "No payment is collected online.</p>"
        "<p style=\"color:#5b6b6c;font-size:13px\">If you didn't ask for this, you can ignore this email.</p>"
    )
    return subject, text, _email_shell("Please confirm your reservation", body)


def _on_hold_email(p: dict, result: pms.ReservationResult) -> tuple[str, str, str]:
    rows = summary_rows(p, result.hold_till or None)
    number = ", ".join(result.reservation_codes) or result.order_id
    if number:
        rows.insert(0, ("Reference", number))
    deadline = (f"{date.fromisoformat(result.hold_till):%B %d, %Y}" if result.hold_till else "")
    subject = f"Your room is on hold at {HOTEL_NAME}"
    pay_line = (f"Please make the down payment by {deadline}, or the room is released. "
                if deadline else "Please make the down payment as soon as possible. ")
    text = (
        f"Hi {p['guest']['first_name']},\n\nYour room is now ON HOLD. It is not confirmed yet.\n\n"
        f"{_rows_text(rows)}\n\n{pay_line}"
        "Our team will contact you by email or mobile with the payment details.\n"
    )
    body = (
        f"<p style=\"color:#122321\">Hi {html.escape(p['guest']['first_name'])},</p>"
        "<p style=\"color:#122321\">Your room is now <strong>on hold</strong>. It is not confirmed yet.</p>"
        f'<table role="presentation" style="margin:12px 0;font-size:14px">{_rows_html(rows)}</table>'
        f"<p style=\"color:#122321;font-size:14px\">{html.escape(pay_line)}"
        "Our team will contact you by email or mobile with the payment details.</p>"
    )
    return subject, text, _email_shell("Your room is on hold", body)


# ------------------------------------------------------------------
# Staff alerts: emailed to STAFF_ALERT_EMAIL, and posted to STAFF_WEBHOOK_URL if set
# ------------------------------------------------------------------
ALERT_SUBJECTS = {
    "reservation": "On-hold reservation placed",
    "booking_failed": "ACTION NEEDED: a chat reservation failed",
    "booking_uncertain": "ACTION NEEDED: check StayGrid for a chat reservation",
    "hold_not_applied": "URGENT: block a chat reservation before it expires",
    "book_and_buy": "ACTION NEEDED: guest needs a book & buy reservation",
    "booking_limit": "ACTION NEEDED: guest hit the chat booking limit",
}


def _send_staff_email(subject: str, text: str) -> None:
    if not (STAFF_ALERT_EMAIL and email_configured()):
        log.warning("Staff alert not emailed (email not configured): %s", subject)
        return
    body = (f'<pre style="font-family:Arial,Helvetica,sans-serif;font-size:14px;white-space:pre-wrap">'
            f"{html.escape(text)}</pre>")
    try:
        send_email(STAFF_ALERT_EMAIL, f"[Casa Alon chat] {subject}", text, body)
    except Exception:
        log.exception("Could not email staff alert: %s", subject)


def _post_webhook(payload: dict) -> None:
    if not STAFF_WEBHOOK_URL:
        return
    try:
        requests.post(STAFF_WEBHOOK_URL, data=json.dumps(payload, default=str),
                      headers={"Content-Type": "application/json"}, timeout=10)
    except requests.RequestException:
        log.exception("Could not reach STAFF_WEBHOOK_URL")


def notify_staff(event: str, p: dict, note: str = "", reservation: dict | None = None) -> None:
    """Alert staff about a reservation request: placed, failed, or needing them."""
    thread = p.get("thread", "")
    log.info("Staff alert (%s): %s", event, thread)
    channel, _, user_id = thread.partition(":")
    _post_webhook({"event": event, "channel": channel, "user_id": user_id, "note": note,
                   "request": p, "reservation": reservation})

    g = p.get("guest", {})
    rows = summary_rows(p, (reservation or {}).get("hold_till") or p.get("hold_till"))
    lines = [ALERT_SUBJECTS.get(event, event), ""]
    if reservation:
        number = ", ".join(reservation.get("reservation_codes") or []) or reservation.get("order_id") or "none returned"
        lines.append(f"Reference: {number}")
    lines += [f"{k}: {v}" for k, v in rows]
    if note:
        lines += ["", f"Details: {note}"]
    if event == "hold_not_applied":
        hold = p.get("hold_till")
        lines += ["", "This reservation was saved in StayGrid as Temp Reserved, but couldn't be blocked "
                      "automatically, so it will expire on StayGrid's short default hold (about an hour)."
                      + (f" Block it until {date.fromisoformat(hold):%B %d, %Y} now," if hold else " Block it now,")
                      + " then contact the guest with the down payment details."]
    elif event == "booking_uncertain":
        hold = (reservation or {}).get("hold_till") or p.get("hold_till")
        lines += ["", "The reservation system timed out while saving this hold, so it may have been created. "
                      "Check StayGrid for a reservation under this guest's name."
                      + (f" If it's there, make sure it's held until {date.fromisoformat(hold):%B %d, %Y}"
                         " and contact the guest with the down payment details." if hold else "")
                      + " If it isn't, contact the guest to book."]
    elif event == "booking_failed":
        lines += ["", "Check StayGrid: a temporary reservation may have been created under this guest's name. "
                      "Contact the guest to complete or cancel it."]
    elif event == "reservation":
        lines += ["", "No payment was collected. Contact the guest with the down payment details."]
    else:
        lines += ["", "Contact the guest to help them book."]
    lines += ["", f"Chat session: {thread}"]
    subject = f"{ALERT_SUBJECTS.get(event, event)}: {g.get('first_name', '')} {g.get('last_name', '')}".strip()
    _send_staff_email(subject, "\n".join(lines))


def notify_handoff(thread: str, question: str, answer: str) -> None:
    """Alert staff that a chat guest needs a person, with the recent conversation,
    so they don't have to ask the guest to repeat themselves."""
    log.info("Staff alert (handoff): %s", thread)
    channel, _, user_id = thread.partition(":")
    _post_webhook({"event": "handoff", "channel": channel, "user_id": user_id,
                   "question": question, "bot_answer": answer})

    transcript = []
    for turn in memory.load_history(thread)[-16:]:
        text = turn["content"]
        if turn["role"] == "user" and text.startswith("[Today is"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
        transcript.append(f"{'Guest' if turn['role'] == 'user' else 'Bot'}: {text}")
    lines = [
        "A guest in the website chat needs a person.",
        "",
        f"Latest guest message: {question}",
        f"Bot's reply: {answer}",
        "",
        "Website guests can't be messaged back in the chat. Use the contact details in the conversation "
        "below if the guest gave them; if not, they were given the front desk number.",
        "",
        "Recent conversation:",
        *(transcript or ["(not available)"]),
        "",
        f"Chat session: {thread}",
    ]
    _send_staff_email(f"Guest needs a person: {question[:60]}", "\n".join(lines))


# ------------------------------------------------------------------
# Step 1 (from chat): save the request and email the guest
# ------------------------------------------------------------------
def start_email_confirmation(p: dict) -> str:
    """Save the reservation request and email the guest a confirm link.
    Returns a short status for the chat agent (starts with ERROR on failure)."""
    base = public_base_url()
    if not base:
        log.error("PUBLIC_BASE_URL is not set, so no confirm link can be built")
        return f"ERROR: email confirmation is not set up. Give the front desk contact {FRONT_DESK} and hand off."
    if not email_configured():
        log.error("SMTP_USER / SMTP_PASSWORD are not set")
        return f"ERROR: email confirmation is not set up. Give the front desk contact {FRONT_DESK} and hand off."
    try:
        if _count_email(p["thread"]) > MAX_CONFIRM_EMAILS_PER_GUEST_PER_DAY:
            return "ERROR: too many confirmation emails have been sent for this guest today. Hand off to staff."
        token = secrets.token_urlsafe(24)
        _require_redis().set(_key(token), json.dumps(p, default=str), ex=CONFIRM_LINK_HOURS * 3600)
    except Exception:
        log.exception("Could not save the reservation request")
        return f"ERROR: the reservation request could not be saved. Give the front desk contact {FRONT_DESK} and hand off."

    link = f"{base}/api/confirm?token={token}"
    try:
        send_email(p["guest"]["email"], *_confirmation_request_email(p, link))
    except Exception:
        log.exception("Could not send the confirmation email to %s", p["guest"]["email"])
        return (f"ERROR: the confirmation email could not be sent. Ask the guest to double-check their email "
                f"address, or give the front desk contact {FRONT_DESK} and hand off.")
    log.info("Confirmation email sent for %s", p["thread"])
    return "OK"


# ------------------------------------------------------------------
# Step 3 (from the confirm page): place the hold
# ------------------------------------------------------------------
def place_hold(token: str) -> tuple[bool, str, str]:
    """Returns (success, page title, page message)."""
    p = get_confirmation(token)
    if not p:
        return False, "This link has expired", (
            f"Confirmation links work for {CONFIRM_LINK_HOURS} hours. Please start a new reservation in our chat, "
            f"or contact our front desk at {FRONT_DESK}.")
    try:
        if not _claim(token):
            return False, "Already confirmed", (
                "This reservation request has already been used. Check your email for the result, "
                f"or contact our front desk at {FRONT_DESK}.")
    except Exception:
        log.exception("Could not claim confirmation %s", token[:8])
        return False, "Something went wrong", f"Please try again later, or contact our front desk at {FRONT_DESK}."

    thread = p["thread"]
    ci, co = date.fromisoformat(p["check_in"]), date.fromisoformat(p["check_out"])
    # The hold starts now, so the deadline is worked out from today's date.
    hold_till = hold_deadline(ci, today())
    if hold_till is None:
        notify_staff("book_and_buy", p, "Guest confirmed too close to arrival for a hold")
        return False, "Please contact our front desk", (
            "Your arrival is now within 2 days, so this booking needs full payment and can't be held. "
            f"Please contact our front desk at {FRONT_DESK} to book.")
    if memory.recent_booking_count(thread) >= MAX_BOOKINGS_PER_GUEST_PER_DAY:
        notify_staff("booking_limit", p, "Daily chat booking limit reached")
        return False, "Please contact our front desk", (
            f"We couldn't place this hold automatically. Please contact our front desk at {FRONT_DESK}.")

    try:
        result = pms.get_client().create_reservation(
            ci, co, p["adults"], p["children"], p["room_type"], p["total"], pms.Guest(**p["guest"]),
            channel=thread.split(":", 1)[0] if ":" in thread else "",
            hold_till=hold_till,
        )
    except pms.PriceChangedError as e:
        return False, "The price has changed", (
            f"The total is now {e.currency} {e.new_total:,.2f}, so nothing was held. "
            f"Please start again in our chat, or contact our front desk at {FRONT_DESK}.")
    except pms.PMSUncertainError as e:
        # The request may have created the reservation, so never tell the guest it
        # failed (they'd book again) or that it's held (it may not be). Staff check.
        log.warning("Hold outcome unknown for %s: %s", thread, e)
        memory.record_booking(thread)
        if isinstance(e, pms.HoldNotAppliedError):
            # Saved as Temp Reserved, which expires on Hotelogix's short default.
            notify_staff("hold_not_applied", p, f"{e}"[:500],
                         reservation={"order_id": e.order_id, "reservation_codes": e.codes,
                                      "hold_till": p.get("hold_till")})
        else:
            notify_staff("booking_uncertain", p, f"{type(e).__name__}: {e}"[:500])
        return False, "We're finishing your hold", (
            "Your request reached our reservation system, but it was slow to confirm. "
            "Our team will check your hold and contact you by email or mobile. "
            "Please don't send the request again.")
    except pms.NotAvailableError:
        return False, "The room is no longer available", (
            "That room was just booked by someone else, so nothing was held. "
            f"Please check other rooms in our chat, or contact our front desk at {FRONT_DESK}.")
    except Exception as e:
        log.exception("Placing the hold failed for %s", thread)
        notify_staff("booking_failed", p, f"{type(e).__name__}: {e}"[:500])
        message = ("Our team has been alerted and will check it and contact you. "
                   f"You can also reach our front desk at {FRONT_DESK}.")
        # TEMPORARY troubleshooting aid, same switch as the chat: shows the real
        # error on the page. Turn CHAT_DEBUG off once fixed.
        if os.getenv("CHAT_DEBUG", "false").lower() == "true":
            message += f" [Debug: {type(e).__name__}: {e}]"[:900]
        return False, "We couldn't complete this", message

    # The request stays in Redis until it expires (the claim blocks reuse), so a
    # second click shows "already confirmed" instead of "expired".
    memory.record_booking(thread)
    reservation = asdict(result)
    notify_staff("reservation", p, reservation=reservation)
    try:
        send_email(p["guest"]["email"], *_on_hold_email(p, result))
    except Exception:
        log.exception("Could not send the on-hold email to %s", p["guest"]["email"])

    deadline = f"{date.fromisoformat(result.hold_till):%B %d, %Y}" if result.hold_till else ""
    number = ", ".join(result.reservation_codes) or result.order_id
    message = "Your room is now on hold. It is not confirmed yet."
    if number:
        message += f" Your reference number is {number}."
    if deadline:
        message += f" Please make the down payment by {deadline}, or the room is released."
    message += " We've emailed you the details, and our team will contact you with the payment details."
    return True, "Your room is on hold", message
