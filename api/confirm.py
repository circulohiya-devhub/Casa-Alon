"""
GET  /api/confirm?token=...   shows the reservation summary and a Confirm button
POST /api/confirm             (form field: token) places the hold

The link in the guest's email opens the GET page. Only the button's POST books
anything, because email security scanners open links automatically and would
otherwise place holds the guest never confirmed.
"""
import html
import logging
import sys
from pathlib import Path
from urllib.parse import parse_qs

# Vercel loads this file by path, so add its folder for the sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

import _booking as booking

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("confirm")

app = FastAPI(title="Casa Alon reservation confirmation")


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(status_code=status, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
                        content=f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{html.escape(title)} | {html.escape(booking.HOTEL_NAME)}</title>
<style>
  :root {{ --brand: {booking.BRAND_COLOR}; --accent: {booking.ACCENT_COLOR}; --ink: #122321; --muted: #5b6b6c;
          --bg: #FAF6EE; --card: #ffffff; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --ink: #EFE6D8; --muted: #a9b5b4; --bg: #0f1c1b; --card: #172928; }}
  }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: system-ui, -apple-system, Segoe UI, Arial, sans-serif; }}
  header {{ background: var(--brand); color: #FAF6EE; padding: 16px 20px; font-size: 18px; }}
  main {{ max-width: 560px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: var(--card); border-radius: 10px; padding: 22px; }}
  h1 {{ font-size: 21px; margin: 0 0 14px; }}
  table {{ border-collapse: collapse; font-size: 15px; margin: 8px 0 18px; }}
  td {{ padding: 6px 14px 6px 0; vertical-align: top; }}
  td:first-child {{ color: var(--muted); white-space: nowrap; }}
  p {{ line-height: 1.5; }}
  .muted {{ color: var(--muted); font-size: 14px; }}
  button {{ background: var(--accent); color: #122321; border: 0; border-radius: 999px; padding: 13px 24px;
           font-size: 16px; font-weight: 600; cursor: pointer; }}
  button:disabled {{ opacity: .6; cursor: wait; }}
</style></head>
<body><header>{html.escape(booking.HOTEL_NAME)}</header>
<main><div class="card"><h1>{html.escape(title)}</h1>{body}</div>
<p class="muted">Questions? Call or Viber our front desk at {html.escape(booking.FRONT_DESK)}.</p></main>
</body></html>""")


def _message_page(title: str, message: str, status: int = 200) -> HTMLResponse:
    return _page(title, f"<p>{html.escape(message)}</p>", status)


@app.get("/api/confirm")
@app.get("/confirm")
def show(token: str = ""):
    p = booking.get_confirmation(token)
    if not p:
        return _message_page("This link has expired", (
            f"Confirmation links work for {booking.CONFIRM_LINK_HOURS} hours. Please start a new reservation "
            f"in our chat, or contact our front desk at {booking.FRONT_DESK}."), status=404)
    if booking.is_claimed(token):
        return _message_page("Already confirmed", (
            "This reservation request has already been used. Check your email for the result, "
            f"or contact our front desk at {booking.FRONT_DESK}."))
    rows = booking.summary_rows(p, p.get("hold_till"))
    table = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in rows)
    body = (
        "<p>Please check the details below. Your room is <strong>not held yet</strong>.</p>"
        f"<table>{table}</table>"
        f'<form method="post" action="/api/confirm" onsubmit="this.querySelector(\'button\').disabled=true">'
        f'<input type="hidden" name="token" value="{html.escape(token)}">'
        "<button type=\"submit\">Confirm and hold my room</button></form>"
        "<p class=\"muted\">No payment is collected online. The down payment must be made by the "
        "\"Held until\" date, or the room is released.</p>"
    )
    return _page("Confirm your reservation", body)


@app.post("/api/confirm")
@app.post("/confirm")
async def confirm(request: Request):
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    token = (form.get("token") or [""])[0]
    try:
        ok, title, message = booking.place_hold(token)
    except Exception:
        log.exception("Unexpected error placing a hold")
        ok, title, message = False, "Something went wrong", (
            f"Please contact our front desk at {booking.FRONT_DESK}.")
    return _message_page(title, message, status=200 if ok else 409)
