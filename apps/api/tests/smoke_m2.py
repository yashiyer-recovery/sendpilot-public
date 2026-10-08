"""M2 smoke: Microsoft 365 send + bounce/delivered webhooks + analytics + suppression.

Run from the HOST: python apps/api/tests/smoke_m2.py
"""

from __future__ import annotations

import io
import os
import sys
import time

import httpx
from openpyxl import Workbook

BASE = os.environ.get("API_BASE", "http://localhost:8080")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "dev-webhook-secret")


def make_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["email", "subject", "body"])
    ws.append(["carol@acme.com", "Hi Carol", "Hello Carol"])
    ws.append(["dave@globex.io", "Hi Dave", "Hello Dave"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30)
    org_id = c.post("/v1/auth/signup",
                    json={"org_name": "Acme", "email": "founder@acme.com"}).json()["org_id"]

    # Connect Microsoft 365 (mock).
    auth_url = c.post("/v1/connections/microsoft/start").json()["auth_url"]
    r = c.get(auth_url, follow_redirects=False)
    c.get(r.headers["location"], follow_redirects=False)
    conns = c.get("/v1/connections").json()
    ms = next(x for x in conns if x["provider"] == "microsoft")
    print("connected microsoft:", ms["account_email"])

    # Upload + extract + approve + send via the M365 account.
    files = {"file": ("list.xlsx", make_xlsx(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    doc_id = c.post("/v1/documents", files=files).json()["document_id"]
    for _ in range(30):
        if c.get(f"/v1/documents/{doc_id}").json()["status"] == "ready":
            break
        time.sleep(1)
    job_id = c.post(f"/v1/documents/{doc_id}/extractions").json()["extraction_job_id"]
    for _ in range(30):
        if c.get(f"/v1/extractions/{job_id}").json()["status"] == "completed":
            break
        time.sleep(1)
    record_ids = [r["id"] for r in c.get(f"/v1/extractions/{job_id}/records").json()["records"]]
    c.post("/v1/records:bulk_approve", json={"record_ids": record_ids}).raise_for_status()
    campaign_id = c.post("/v1/campaigns", json={
        "name": "M365 outreach", "connected_account_id": ms["id"], "record_ids": record_ids,
    }).json()["id"]
    c.post(f"/v1/campaigns/{campaign_id}/send", json={"mode": "now"}).raise_for_status()

    msgs: list[dict] = []
    for _ in range(30):
        msgs = c.get(f"/v1/messages?campaign_id={campaign_id}").json()
        if msgs and all(m["status"] in ("sent", "failed", "skipped") for m in msgs):
            break
        time.sleep(1)
    sent_msgs = [m for m in msgs if m["status"] == "sent"]
    assert len(sent_msgs) == 2, msgs
    assert all(m["provider_message_id"] for m in sent_msgs), sent_msgs
    print("M365 sent:", len(sent_msgs))

    # Simulate provider callbacks: deliver the first, hard-bounce the second.
    hdr = {"x-webhook-token": WEBHOOK_TOKEN}
    c.post("/v1/webhooks/provider", headers=hdr, json={
        "org_id": org_id, "type": "delivered",
        "provider_message_id": sent_msgs[0]["provider_message_id"],
    }).raise_for_status()
    c.post("/v1/webhooks/provider", headers=hdr, json={
        "org_id": org_id, "type": "bounce", "dsn_status": "5.1.1",
        "provider_message_id": sent_msgs[1]["provider_message_id"],
    }).raise_for_status()

    stats = c.get(f"/v1/campaigns/{campaign_id}/analytics").json()
    print("analytics:", stats)
    assert stats["sent"] == 2 and stats["delivered"] >= 1 and stats["bounced"] >= 1, stats

    supp = c.get("/v1/suppressions").json()
    assert any(s["reason"] == "hard_bounce" for s in supp), supp
    print("hard-bounce suppression recorded:", [s["email"] for s in supp])

    # Webhook auth is enforced.
    bad = c.post("/v1/webhooks/provider", json={
        "org_id": org_id, "type": "delivered", "provider_message_id": "x"})
    assert bad.status_code == 403, bad.status_code

    print("\nM2 SMOKE OK ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
