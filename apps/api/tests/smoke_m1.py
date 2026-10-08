"""M1 end-to-end smoke: Excel -> extract -> review/approve -> idempotent send.

Run from the HOST (browser-like; uses published ports). Needs httpx + openpyxl:
    python apps/api/tests/smoke_m1.py
"""

from __future__ import annotations

import io
import os
import sys
import time

import httpx
from openpyxl import Workbook

BASE = os.environ.get("API_BASE", "http://localhost:8080")
MOCK = os.environ.get("MOCK_BASE", "http://localhost:9100")


def make_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["email", "subject", "body"])
    ws.append(["alice@acme.com", "Quick question", "Hi Alice, loved the demo."])
    ws.append(["bob@globex.io", "Following up", "Hi Bob, circling back on the pilot."])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30)

    c.post("/v1/auth/signup", json={"org_name": "Acme", "email": "founder@acme.com"}).raise_for_status()

    # Connect mock Gmail.
    auth_url = c.post("/v1/connections/google/start").json()["auth_url"]
    r = c.get(auth_url, follow_redirects=False)
    c.get(r.headers["location"], follow_redirects=False)
    account_id = c.get("/v1/connections").json()[0]["id"]
    print("connected account:", account_id)

    # Upload the Excel sheet.
    files = {"file": ("list.xlsx", make_xlsx(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    doc_id = c.post("/v1/documents", files=files).json()["document_id"]
    for _ in range(30):
        if c.get(f"/v1/documents/{doc_id}").json()["status"] == "ready":
            break
        time.sleep(1)

    # Extract.
    job_id = c.post(f"/v1/documents/{doc_id}/extractions").json()["extraction_job_id"]
    job = {}
    for _ in range(30):
        job = c.get(f"/v1/extractions/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    print("extraction:", job)
    assert job["status"] == "completed", job
    assert job["record_count"] == 2, job
    assert job["shape"] == "tabular", job

    records = c.get(f"/v1/extractions/{job_id}/records").json()["records"]
    assert all(r["validation_status"] == "valid" for r in records), records
    record_ids = [r["id"] for r in records]
    print("records:", [(r["recipient_email"], r["confidence"], r["validation_status"]) for r in records])

    # Approve + send.
    c.post("/v1/records:bulk_approve", json={"record_ids": record_ids}).raise_for_status()
    campaign_id = c.post("/v1/campaigns", json={
        "name": "Q3 outreach", "connected_account_id": account_id, "record_ids": record_ids,
    }).json()["id"]
    send = c.post(f"/v1/campaigns/{campaign_id}/send", json={"mode": "now"}).json()
    print("send:", send)
    assert send["enqueued"] == 2, send

    statuses: list[str] = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={campaign_id}").json()
        statuses = [m["status"] for m in msgs]
        if msgs and all(s in ("sent", "failed", "skipped") for s in statuses):
            break
        time.sleep(1)
    print("message statuses:", statuses)
    assert statuses.count("sent") == 2, statuses

    sent = httpx.get(f"{MOCK}/mock/sent").json()
    print("mock provider sent count:", sent["count"])
    assert sent["count"] >= 2

    # Suppression enforcement: suppress alice, re-send, expect her message skipped.
    c.post("/v1/suppressions", json={"email": "alice@acme.com"}).raise_for_status()
    c.post("/v1/records:bulk_approve", json={"record_ids": record_ids}).raise_for_status()
    c2 = c.post("/v1/campaigns", json={
        "name": "Q3 resend", "connected_account_id": account_id, "record_ids": record_ids,
    }).json()["id"]
    c.post(f"/v1/campaigns/{c2}/send", json={"mode": "now"}).raise_for_status()
    statuses2: list[str] = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={c2}").json()
        statuses2 = [m["status"] for m in msgs]
        if msgs and all(s in ("sent", "failed", "skipped") for s in statuses2):
            break
        time.sleep(1)
    print("resend statuses:", statuses2)
    assert "skipped" in statuses2, statuses2  # alice suppressed

    print("\nM1 SMOKE OK ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
