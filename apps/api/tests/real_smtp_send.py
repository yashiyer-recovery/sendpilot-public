"""Send a REAL email through Gmail SMTP with an App Password.

Credentials are read from env vars so they never appear on a command line that
gets logged or in a chat transcript. The password is sent only to your local
API (over localhost) and stored envelope-encrypted; the worker uses it to talk
to smtp.gmail.com.

    cd /Users/yashiyer/Documents/sendpilot
    GMAIL_ADDRESS=you@gmail.com \
    GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx' \
    REAL_RECIPIENT=you@gmail.com \
    /tmp/spvenv/bin/python apps/api/tests/real_smtp_send.py
"""

from __future__ import annotations

import io
import os
import sys
import time

import httpx
from openpyxl import Workbook

BASE = os.environ.get("API_BASE", "http://localhost:8080")
GMAIL = os.environ.get("GMAIL_ADDRESS", "")
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")  # strip Google's spaces
RECIPIENT = os.environ.get("REAL_RECIPIENT", GMAIL)
# Default to Gmail SMTP; override for the Workspace relay (smtp-relay.gmail.com).
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))


def make_xlsx(to: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["email", "subject", "body"])
    ws.append([to, "SendPilot live test (SMTP)",
               "Hi — this is a real email sent by SendPilot via Gmail SMTP."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    if not GMAIL or not APP_PASSWORD:
        print("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD env vars first.")
        return 2

    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/v1/auth/signup", json={"org_name": "Live", "email": "founder@acme.com"}).raise_for_status()

    conn = c.post("/v1/connections/smtp", json={
        "account_email": GMAIL, "host": SMTP_HOST, "port": SMTP_PORT,
        "username": GMAIL, "password": APP_PASSWORD, "starttls": True,
    }).json()
    print(f"connected SMTP ({SMTP_HOST}:{SMTP_PORT}) as {conn['account_email']}")
    print("sending real email to:", RECIPIENT)

    files = {"file": ("test.xlsx", make_xlsx(RECIPIENT),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    doc = c.post("/v1/documents", files=files).json()["document_id"]
    for _ in range(30):
        if c.get(f"/v1/documents/{doc}").json()["status"] == "ready":
            break
        time.sleep(1)
    job = c.post(f"/v1/documents/{doc}/extractions").json()["extraction_job_id"]
    for _ in range(30):
        if c.get(f"/v1/extractions/{job}").json()["status"] == "completed":
            break
        time.sleep(1)
    recs = [r["id"] for r in c.get(f"/v1/extractions/{job}/records").json()["records"]]
    c.post("/v1/records:bulk_approve", json={"record_ids": recs}).raise_for_status()
    camp = c.post("/v1/campaigns", json={
        "name": "Live SMTP test", "connected_account_id": conn["id"], "record_ids": recs,
    }).json()["id"]
    print("send:", c.post(f"/v1/campaigns/{camp}/send", json={"mode": "now"}).json())

    result: list = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={camp}").json()
        result = [(m["status"], m["error"]) for m in msgs]
        if msgs and all(s[0] in ("sent", "failed", "skipped") for s in result):
            break
        time.sleep(1)
    print("result:", result)
    if any(s[0] == "sent" for s in result):
        print(f"\n✓ Sent — check the inbox of {RECIPIENT}.")
    else:
        print("\n✗ Not sent — see the error above (common causes: wrong app password, "
              "2-Step Verification off, or 'less secure' blocked by your account).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
