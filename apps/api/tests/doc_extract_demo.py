"""Demo: extract emails from a prose DOCUMENT (not a spreadsheet).

Uploads a plain-text document containing two email drafts written as prose and
shows the engine pulling {recipient, subject, body} from each — proving the
narrative path, not just the tabular/Excel path.

    python apps/api/tests/doc_extract_demo.py
"""

from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://localhost:8080")

DOCUMENT = b"""To: jane@acme.com
Subject: Onboarding question
Hi Jane, loved the demo - one quick question about your rollout timeline.

---

To: sam@globex.io (Sam Lee)
Subject: Following up
Hi Sam, circling back on the pilot we discussed last week.
"""


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/v1/auth/signup", json={"org_name": "Docs", "email": "founder@acme.com"}).raise_for_status()

    files = {"file": ("drafts.txt", DOCUMENT, "text/plain")}
    doc_id = c.post("/v1/documents", files=files).json()["document_id"]
    for _ in range(30):
        if c.get(f"/v1/documents/{doc_id}").json()["status"] == "ready":
            break
        time.sleep(1)

    job_id = c.post(f"/v1/documents/{doc_id}/extractions").json()["extraction_job_id"]
    job = {}
    for _ in range(30):
        job = c.get(f"/v1/extractions/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(1)

    print("document shape detected:", job["shape"], "| records:", job["record_count"])
    for r in c.get(f"/v1/extractions/{job_id}/records").json()["records"]:
        print(f"  • {r['recipient_email']:<22} subject={r['subject']!r:<24} "
              f"conf={r['confidence']:.2f} status={r['validation_status']}")
        print(f"    body: {r['body'][:60]!r}")
    print("\n(extracted from a prose .txt with NO Anthropic key — deterministic fallback)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
