"""Idempotency guard — the double-send guarantee (PRD §11.7).

The send pipeline claims a message (committed) before the provider call. This
test proves that two claims for the same (campaign, record, step) — as happens
when a worker is killed mid-send and the task is retried — yield exactly one
message row, i.e. zero duplicate sends.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from sendpilot.db.models import (
    AppUser,
    Campaign,
    ConnectedAccount,
    Document,
    EmailRecord,
    ExtractionJob,
    Message,
    Organization,
)
from sendpilot.db.session import org_session, system_session
from sendpilot.sending.idempotency import claim_message, idem_key

pytestmark = pytest.mark.db


async def _graph() -> tuple[str, str, str, str]:
    """Create org → user → account → doc → job → record → campaign. Returns ids."""
    async with system_session() as s:
        org = Organization(name="chaos")
        s.add(org)
        await s.flush()
        org_id = str(org.id)
        user = AppUser(org_id=org.id, email=f"u{uuid.uuid4().hex}@acme.com", role="owner")
        s.add(user)
        await s.flush()
        user_id = str(user.id)

    async with org_session(org_id) as s:
        acct = ConnectedAccount(
            org_id=org_id, provider="gmail", account_email=f"a{uuid.uuid4().hex}@acme.com",
            enc_tokens=b"x", enc_key_id="local:dev",
        )
        s.add(acct)
        await s.flush()
        doc = Document(
            org_id=org_id, uploaded_by=user_id, filename="f.csv", mime_type="text/csv",
            size_bytes=1, sha256="x", storage_key="k", status="ready",
        )
        s.add(doc)
        await s.flush()
        job = ExtractionJob(org_id=org_id, document_id=doc.id, status="completed")
        s.add(job)
        await s.flush()
        rec = EmailRecord(org_id=org_id, extraction_job_id=job.id, recipient_email="x@y.com",
                          subject="s", body="b", confidence=0.99, validation_status="valid",
                          review_status="approved")
        s.add(rec)
        await s.flush()
        camp = Campaign(org_id=org_id, connected_account_id=acct.id, name="c",
                        created_by=user_id, record_ids=[str(rec.id)])
        s.add(camp)
        await s.flush()
        return org_id, str(camp.id), str(rec.id), str(acct.id)


async def test_claim_is_idempotent():
    org_id, campaign_id, record_id, account_id = await _graph()
    key = idem_key(campaign_id, record_id, 0)

    async with org_session(org_id) as s:
        first = await claim_message(s, org_id=org_id, campaign_id=campaign_id,
                                    record_id=record_id, account_id=account_id, step=0, key=key)
    # Second claim (simulating a retry after a mid-send crash) must be a no-op.
    async with org_session(org_id) as s:
        second = await claim_message(s, org_id=org_id, campaign_id=campaign_id,
                                     record_id=record_id, account_id=account_id, step=0, key=key)

    assert first is not None
    assert second is None

    async with org_session(org_id) as s:
        count = await s.scalar(
            select(func.count()).select_from(Message).where(Message.idempotency_key == key)
        )
        assert count == 1  # exactly one message — zero duplicates
