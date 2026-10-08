"""Prove the SMTP send path end-to-end against the local Mailpit sink.

No real credentials needed — connects an SMTP account pointing at Mailpit
(host=mailpit, port=1025, no TLS/auth), sends, and confirms the message landed.

    python apps/api/tests/smtp_send.py     # then view at http://localhost:8025
"""

from __future__ import annotations

import io
import os
import sys
import time

import httpx
from openpyxl import Workbook

BASE = os.environ.get("API_BASE", "http://localhost:8080")
MAILPIT = os.environ.get("MAILPIT_API", "http://localhost:8025")


def make_xlsx(to: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["email", "subject", "body"])
    ws.append([to, "SendPilot SMTP test", "Hi — this was sent through the SMTP provider."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/v1/auth/signup", json={"org_name": "Smtp", "email": "founder@acme.com"}).raise_for_status()

    conn = c.post("/v1/connections/smtp", json={
        "account_email": "sender@acme.com", "host": "mailpit", "port": 1025, "starttls": False,
    }).json()
    print("connected SMTP account:", conn["account_email"])

    to = "inbox@acme.com"
    files = {"file": ("t.xlsx", make_xlsx(to),
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
        "name": "smtp test", "connected_account_id": conn["id"], "record_ids": recs,
    }).json()["id"]
    print("send:", c.post(f"/v1/campaigns/{camp}/send", json={"mode": "now"}).json())

    statuses: list[str] = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={camp}").json()
        statuses = [m["status"] for m in msgs]
        if msgs and all(s in ("sent", "failed", "skipped") for s in statuses):
            break
        time.sleep(1)
    print("message statuses:", statuses)
    assert "sent" in statuses, statuses

    time.sleep(1)
    box = httpx.get(f"{MAILPIT}/api/v1/messages").json()
    print("mailpit captured:", box.get("total"), "message(s)")
    assert box.get("total", 0) >= 1, box
    latest = box["messages"][0]
    print("subject:", latest.get("Subject"), "| to:", latest.get("To"))
    print(f"\nSMTP SMOKE OK ✓  — open {MAILPIT} to view the email")
    return 0


if __name__ == "__main__":
    sys.exit(main())
