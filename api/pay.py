"""
GET /api/pay?token=...   the payment details for a reservation on hold

Opened from the "View payment details" button in the guest's email. It shows
the amount due (the minimum down payment, or the full stay), the bank details
to pay to, and the reservation reference. It changes nothing in the PMS:
staff confirm the reservation themselves once the payment arrives.
"""
import html
import logging
import sys
from datetime import date
from pathlib import Path

# Vercel loads this file by path, so add its folder for the sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import _booking as booking

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pay")

app = FastAPI(title="Casa Alon payment details")


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(status_code=status, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
                        content=f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{html.escape(title)} | {html.escape(booking.HOTEL_NAME)}</title>
<style>
  :root {{ --brand: {booking.BRAND_COLOR}; --accent: {booking.ACCENT_COLOR}; --ink: #122321; --muted: #5b6b6c;
          --bg: #FAF6EE; --card: #ffffff; --line: #e6ddce; --warn-bg: #FBEDE9; --warn-ink: #8A2E1F; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --ink: #EFE6D8; --muted: #a9b5b4; --bg: #0f1c1b; --card: #172928; --line: #2a3f3d;
            --warn-bg: #3a1d17; --warn-ink: #f3b8a8; }}
  }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: system-ui, -apple-system, Segoe UI, Arial, sans-serif; }}
  header {{ background: var(--brand); color: #FAF6EE; padding: 16px 20px; font-size: 18px; }}
  main {{ max-width: 560px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: var(--card); border-radius: 10px; padding: 22px; }}
  h1 {{ font-size: 21px; margin: 0 0 14px; }}
  h2 {{ font-size: 16px; margin: 22px 0 6px; }}
  table {{ border-collapse: collapse; font-size: 15px; margin: 6px 0 4px; width: 100%; }}
  td {{ padding: 7px 14px 7px 0; vertical-align: top; border-bottom: 1px solid var(--line); }}
  td:first-child {{ color: var(--muted); white-space: nowrap; width: 40%; }}
  .amount {{ font-weight: 600; }}
  p {{ line-height: 1.5; }}
  .muted {{ color: var(--muted); font-size: 14px; }}
  .warning {{ background: var(--warn-bg); color: var(--warn-ink); border-radius: 8px; padding: 12px 14px;
             font-weight: 600; margin: 0 0 18px; }}
</style></head>
<body><header>{html.escape(booking.HOTEL_NAME)}</header>
<main><div class="card"><h1>{html.escape(title)}</h1>{body}</div>
<p class="muted">Questions? Call or Viber our front desk at {html.escape(booking.FRONT_DESK)}.</p></main>
</body></html>""")


def _table(rows) -> str:
    return "<table>" + "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in rows) + "</table>"


@app.get("/api/pay")
@app.get("/pay")
def show(token: str = ""):
    p = booking.get_payment(token)
    if not p:
        return _page("This link has expired", (
            "<p>This payment link is no longer available. If your room is still on hold, please contact "
            f"our front desk at {html.escape(booking.FRONT_DESK)} for the payment details.</p>"), status=404)

    cur = p["currency"]
    minimum, full = booking.payment_amounts(p["total"])
    pct = f"{booking.MIN_DOWN_PAYMENT_PERCENT:g}%"
    deadline = f"{date.fromisoformat(p['hold_till']):%B %d, %Y}" if p.get("hold_till") else ""
    reference = p.get("reference") or ""

    stay = [(k, v) for k, v in booking.summary_rows(p, p.get("hold_till"))
            if k not in ("Email", "Mobile", "Cancellation")]
    if reference:
        stay.insert(0, ("Reference", reference))
    amounts = [(f"Minimum down payment ({pct})", f"{cur} {minimum:,.2f}"), ("Or pay in full", f"{cur} {full:,.2f}")]
    bank = [("Bank", booking.PAYMENT_BANK_NAME), ("Account name", booking.PAYMENT_ACCOUNT_NAME),
            ("Account number", booking.PAYMENT_ACCOUNT_NUMBER)]
    if reference:
        bank.append(("Payment reference", reference))

    warning = (f'<p class="warning">{html.escape(booking.DUMMY_WARNING)}</p>'
               if booking.PAYMENT_DETAILS_ARE_DUMMY else "")
    pay_by = (f"Pay by <strong>{html.escape(deadline)}</strong>, or the room is released."
              if deadline else "Please pay as soon as possible to keep the room.")
    body = (
        warning
        + "<p>Your room is on hold. It is not confirmed yet.</p>"
        + _table(stay)
        + "<h2>Amount to pay</h2>"
        + _table(amounts).replace("<td>" + html.escape(f"{cur} {minimum:,.2f}"),
                                  '<td class="amount">' + html.escape(f"{cur} {minimum:,.2f}"))
        + f"<p>{pay_by}</p>"
        + "<h2>Where to pay</h2>"
        + _table(bank)
        + "<p class=\"muted\">Include the payment reference with your transfer. Our team confirms your "
          "reservation once the payment is received.</p>"
    )
    return _page("Payment details", body)
