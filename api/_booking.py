"""
Reservations placed from the chat, and the payment email that follows.

Flow:
  1. In chat, review_reservation (in _rag.py) checks the live rate and shows
     the guest a summary. When they reply YES (checked in code), the chat
     calls place_hold_now() here.
  2. place_hold_now() checks price and availability again, saves the booking
     in the PMS and blocks it until its holdTill deadline, then emails the
     guest a payment email with a "View payment details" button, and alerts
     staff.
  3. The button opens GET /api/pay?token=... (api/pay.py): the amount due
     (a minimum down payment, or the full stay) and the bank details to pay
     to. It changes nothing in the PMS; staff confirm payments themselves.

While PAYMENT_DETAILS_ARE_DUMMY is true (the default), the bank details are
placeholders and the page says plainly not to transfer anything.
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

# Down payment: the guest pays at least this share of the total, or the full stay.
MIN_DOWN_PAYMENT_PERCENT = float(os.getenv("MIN_DOWN_PAYMENT_PERCENT", "10"))
# Bank details shown on the payment page. Placeholders until real ones are set.
PAYMENT_DETAILS_ARE_DUMMY = os.getenv("PAYMENT_DETAILS_ARE_DUMMY", "true").lower() == "true"
PAYMENT_BANK_NAME = os.getenv("PAYMENT_BANK_NAME", "Sample Bank (dummy)")
PAYMENT_ACCOUNT_NAME = os.getenv("PAYMENT_ACCOUNT_NAME", "Casa Alon Hotel (dummy account)")
PAYMENT_ACCOUNT_NUMBER = os.getenv("PAYMENT_ACCOUNT_NUMBER", "0000-0000-0000")
DUMMY_WARNING = "This is a dummy account. Do not transfer anything."
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
# Payment page links (Redis): each held reservation gets a random token
# ------------------------------------------------------------------
def _key(token: str) -> str:
    return f"casaalon:pay:{token}"


def _require_redis():
    r = memory._redis()
    if not r:
        raise RuntimeError("Redis is required for payment page links")
    return r


def payment_amounts(total: float) -> tuple[float, float]:
    """(minimum down payment, full amount)."""
    minimum = round(total * MIN_DOWN_PAYMENT_PERCENT / 100, 2)
    return minimum, round(total, 2)


def save_payment(p: dict, result: pms.ReservationResult) -> str:
    """Store what the payment page shows, until a few days after the hold ends."""
    token = secrets.token_urlsafe(24)
    hold = date.fromisoformat(result.hold_till) if result.hold_till else today()
    seconds = max(86400, int((datetime.combine(hold, datetime.min.time(), HOTEL_TIMEZONE)
                              - datetime.now(HOTEL_TIMEZONE)).total_seconds()) + 3 * 86400)
    record = {**p, "total": result.total_price, "currency": result.currency,
              "room_type": result.room_type, "rate_plan": result.rate_plan,
              "hold_till": result.hold_till,
              "reference": ", ".join(result.reservation_codes) or result.order_id}
    _require_redis().set(_key(token), json.dumps(record, default=str), ex=seconds)
    return token


def get_payment(token: str) -> dict | None:
    if not token or len(token) > 100:
        return None
    try:
        raw = _require_redis().get(_key(token))
        return json.loads(raw) if raw else None
    except Exception:
        log.exception("Could not read payment link %s", token[:8])
        return None


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


def _payment_email(p: dict, result: pms.ReservationResult, link: str) -> tuple[str, str, str]:
    rows = summary_rows(p, result.hold_till or None)
    reference = ", ".join(result.reservation_codes) or result.order_id
    if reference:
        rows.insert(0, ("Reference", reference))
    minimum, full = payment_amounts(result.total_price)
    cur = result.currency
    deadline = f"{date.fromisoformat(result.hold_till):%B %d, %Y}" if result.hold_till else "as soon as possible"
    pct = f"{MIN_DOWN_PAYMENT_PERCENT:g}%"
    subject = f"Your room is on hold at {HOTEL_NAME}: payment details"
    dummy_text = f"\n\nNote: {DUMMY_WARNING}\n" if PAYMENT_DETAILS_ARE_DUMMY else ""
    text = (
        f"Hi {p['guest']['first_name']},\n\nYour room is on hold. It is not confirmed yet.\n\n"
        f"{_rows_text(rows)}\n\n"
        f"To keep it, make a down payment by {deadline}, or the room is released:\n"
        f"- Minimum ({pct}): {cur} {minimum:,.2f}\n- Or pay in full: {cur} {full:,.2f}\n\n"
        f"See where to pay: {link}{dummy_text}\n"
        "Our team confirms your reservation once the payment is received.\n"
    )
    dummy_html = (f'<p style="background:#FBEDE9;color:#8A2E1F;padding:10px 12px;border-radius:6px;'
                  f'font-size:14px"><strong>{html.escape(DUMMY_WARNING)}</strong></p>'
                  if PAYMENT_DETAILS_ARE_DUMMY else "")
    body = (
        f"<p style=\"color:#122321\">Hi {html.escape(p['guest']['first_name'])},</p>"
        "<p style=\"color:#122321\">Your room is <strong>on hold</strong>. It is not confirmed yet.</p>"
        f'<table role="presentation" style="margin:12px 0;font-size:14px">{_rows_html(rows)}</table>'
        f"<p style=\"color:#122321;font-size:14px\">To keep it, make a down payment by "
        f"<strong>{html.escape(deadline)}</strong>, or the room is released:</p>"
        f'<table role="presentation" style="margin:4px 0 12px;font-size:14px">'
        f'{_rows_html([(f"Minimum ({pct})", f"{cur} {minimum:,.2f}"), ("Or pay in full", f"{cur} {full:,.2f}")])}'
        "</table>"
        f'<p style="margin:20px 0"><a href="{html.escape(link)}" style="background:{ACCENT_COLOR};color:#122321;'
        'text-decoration:none;padding:12px 22px;border-radius:999px;display:inline-block;font-weight:bold">'
        "View payment details</a></p>"
        f"{dummy_html}"
        "<p style=\"color:#122321;font-size:14px\">Our team confirms your reservation once the payment "
        "is received.</p>"
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
        lines += ["", "No payment was collected. The guest was emailed the payment details (unless noted "
                      "above). Confirm the reservation in StayGrid once the down payment arrives."]
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
# Placing the hold (called from the chat after the guest replies YES)
# ------------------------------------------------------------------
def place_hold_now(p: dict) -> str:
    """Place the hold and email the payment details. Returns the result for the
    chat agent: starts with RESERVATION ON HOLD, HOLD BEING FINALIZED, or ERROR."""
    thread = p["thread"]
    ci, co = date.fromisoformat(p["check_in"]), date.fromisoformat(p["check_out"])
    hold_till = hold_deadline(ci, today())
    if hold_till is None:
        return ("ERROR: BOOK_AND_BUY. Arrival is within 2 days, so this booking can't be placed on hold. "
                f"Tell the guest it needs full payment at booking and hand off to the front desk ({FRONT_DESK}).")
    if memory.recent_booking_count(thread) >= MAX_BOOKINGS_PER_GUEST_PER_DAY:
        notify_staff("booking_limit", p, "Daily chat booking limit reached")
        return "ERROR: this guest has reached the daily limit for chat reservations. Hand off to staff."

    try:
        result = pms.get_client().create_reservation(
            ci, co, p["adults"], p["children"], p["room_type"], p["total"], pms.Guest(**p["guest"]),
            channel=thread.split(":", 1)[0] if ":" in thread else "",
            hold_till=hold_till,
        )
    except pms.PriceChangedError as e:
        return (f"ERROR: the price changed to {e.currency} {e.new_total:,.2f}. Nothing was booked. "
                "Tell the guest the new total and ask if they still want it.")
    except pms.NotAvailableError:
        return "ERROR: that room just became unavailable. Nothing was booked. Offer to check other rooms."
    except pms.PMSUncertainError as e:
        # The booking may exist (or exists, but couldn't be blocked until the hold
        # date), so never tell the guest it failed, or that it's held. Staff check.
        log.warning("Hold outcome unknown for %s: %s", thread, e)
        memory.record_booking(thread)
        if isinstance(e, pms.HoldNotAppliedError):
            notify_staff("hold_not_applied", p, f"{e}"[:500],
                         reservation={"order_id": e.order_id, "reservation_codes": e.codes,
                                      "hold_till": hold_till.isoformat()})
        else:
            notify_staff("booking_uncertain", p, f"{type(e).__name__}: {e}"[:500])
        return ("HOLD BEING FINALIZED. The reservation reached the hotel system but the hold couldn't be "
                "completed automatically. Tell the guest our team is finishing their hold and will contact "
                "them by email or mobile with the payment details. Do not say the room is held, and do not "
                "ask them to try again.")
    except Exception as e:
        log.exception("Placing the hold failed for %s", thread)
        notify_staff("booking_failed", p, f"{type(e).__name__}: {e}"[:500])
        return ("ERROR: the reservation could not be completed. Do not tell the guest it is booked. "
                f"Give the front desk contact {FRONT_DESK} and hand off.")

    memory.record_booking(thread)
    reservation = asdict(result)
    note = ""
    try:
        base = public_base_url()
        if not base:
            raise RuntimeError("PUBLIC_BASE_URL is not set")
        link = f"{base}/api/pay?token={save_payment(p, result)}"
        send_email(p["guest"]["email"], *_payment_email(p, result, link))
        emailed = True
    except Exception as e:
        log.exception("Could not send the payment email for %s", thread)
        note = f"The payment email could not be sent ({type(e).__name__}); send the guest the payment details."
        emailed = False
    notify_staff("reservation", p, note, reservation=reservation)

    minimum, full = payment_amounts(result.total_price)
    reference = ", ".join(result.reservation_codes) or result.order_id
    deadline = f"{date.fromisoformat(result.hold_till):%B %d, %Y}" if result.hold_till else ""
    return (
        "RESERVATION ON HOLD."
        + (f" Reference number: {reference}." if reference else "")
        + f" {result.room_type}, total {result.currency} {result.total_price:,.2f}."
        + (f" Held until {deadline}: the room is released if the down payment isn't made by then." if deadline else "")
        + f" Down payment: at least {MIN_DOWN_PAYMENT_PERCENT:g}% ({result.currency} {minimum:,.2f}), "
          f"or the full {result.currency} {full:,.2f}."
        + (f" The payment details were emailed to {p['guest']['email']}." if emailed
           else " The payment email could not be sent; say our team will send the payment details.")
        + " Tell the guest the room is on hold, NOT confirmed: our team confirms it once the payment is received."
    )
