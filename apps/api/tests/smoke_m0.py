"""M0 end-to-end smoke: signup -> connect (mock Gmail) -> upload -> AV-ready.

Run from the HOST (it acts like a browser, following published ports
localhost:8000 -> localhost:9100 -> localhost:8000):

    python apps/api/tests/smoke_m0.py        # needs httpx
"""

from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://localhost:8000")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30)

    r = c.post("/v1/auth/signup", json={"org_name": "Acme", "email": "founder@acme.com"})
    r.raise_for_status()
    print("signup:", r.json())

    r = c.post("/v1/connections/google/start")
    r.raise_for_status()
    auth_url = r.json()["auth_url"]
    print("auth_url:", auth_url)

    # mock authorize -> redirect to API callback
    r = c.get(auth_url, follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    r = c.get(r.headers["location"], follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    print("callback ->", r.headers.get("location"))

    r = c.get("/v1/connections")
    r.raise_for_status()
    conns = r.json()
    assert conns and conns[0]["account_email"], conns
    print("connections:", conns)

    csv = b"email,subject,body\njane@acme.com,Hi,Hello Jane\n"
    r = c.post("/v1/documents", files={"file": ("list.csv", csv, "text/csv")})
    r.raise_for_status()
    doc_id = r.json()["document_id"]
    print("upload:", r.json())

    status = "scanning"
    for _ in range(30):
        r = c.get(f"/v1/documents/{doc_id}")
        r.raise_for_status()
        status = r.json()["status"]
        if status in ("ready", "rejected"):
            break
        time.sleep(1)
    print("document status:", status)
    assert status == "ready", f"expected ready, got {status}"

    print("\nM0 SMOKE OK ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
