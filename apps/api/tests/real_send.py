"""Drive a REAL Gmail send (MOCK_PROVIDER=false).

Signs up, starts the live Google OAuth (prints a consent URL for you to open),
waits for the connection, then uploads a one-row Excel and sends a real email.

    REAL_RECIPIENT=you@example.com python apps/api/tests/real_send.py
"""

from __future__ import annotations

import io
import os
import sys
import time

import httpx
from openpyxl import Workbook

BASE = os.environ.get("API_BASE", "http://localhost:8080")


def make_xlsx(recipient: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["email", "subject", "body"])
    ws.append([recipient, "SendPilot live test",
               "Hi — this is a real test email sent by SendPilot via Gmail OAuth."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/v1/auth/signup", json={"org_name": "Live", "email": "founder@acme.com"}).raise_for_status()

    auth_url = c.post("/v1/connections/google/start").json()["auth_url"]
    print("\n" + "=" * 70)
    print("1) Open this URL in your browser and click Allow:\n")
    print(auth_url)
    print("\n   (You'll land on a localhost:3000 page that may not load — that's")
    print("    fine; the Gmail connection is already saved.)")
    print("=" * 70 + "\n")
    print("Waiting for the Gmail connection ...")

    account = None
    for _ in range(150):  # up to ~5 min
        conns = c.get("/v1/connections").json()
        active = [x for x in conns if x["provider"] == "gmail" and x["status"] == "active"]
        if active:
            account = active[0]
            break
        time.sleep(2)
    if account is None:
        print("Timed out waiting for the connection.")
        return 1
    print("Connected:", account["account_email"])

    recipient = os.environ.get("REAL_RECIPIENT", account["account_email"])
    print("Sending a real test email to:", recipient)

    files = {"file": ("test.xlsx", make_xlsx(recipient),
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
        "name": "Live test", "connected_account_id": account["id"], "record_ids": recs,
    }).json()["id"]
    print("send:", c.post(f"/v1/campaigns/{camp}/send", json={"mode": "now"}).json())

    result: list = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={camp}").json()
        result = [(m["status"], m["provider_message_id"]) for m in msgs]
        if msgs and all(s[0] in ("sent", "failed", "skipped") for s in result):
            break
        time.sleep(1)
    print("result:", result)
    print(f"\n✓ Done — check the inbox of {recipient}; a real email should arrive shortly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
