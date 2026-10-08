"""Bounce ingestion + circuit breaker (PRD §12, §14)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from sendpilot.analytics.circuit_breaker import check_circuit_breaker
from sendpilot.config import settings
from sendpilot.db.models import (
    AppUser,
    Campaign,
    ConnectedAccount,
    Document,
    EmailRecord,
    Event,
    ExtractionJob,
    Message,
    Organization,
    SuppressionEntry,
)
from sendpilot.db.session import org_session, system_session
from sendpilot.tracking.bounce import handle_inbound

pytestmark = pytest.mark.db


async def _setup() -> tuple[str, str, str, str]:
    async with system_session() as s:
        org = Organization(name="trk")
        s.add(org)
        await s.flush()
        org_id = str(org.id)
        user = AppUser(org_id=org.id, email=f"u{uuid.uuid4().hex}@acme.com", role="owner")
        s.add(user)
        await s.flush()
        user_id = str(user.id)
    async with org_session(org_id) as s:
        acct = ConnectedAccount(org_id=org_id, provider="gmail",
                                account_email=f"a{uuid.uuid4().hex}@acme.com",
                                enc_tokens=b"x", enc_key_id="k")
        s.add(acct)
        await s.flush()
        doc = Document(org_id=org_id, uploaded_by=user_id, filename="f", mime_type="text/csv",
                       size_bytes=1, sha256="x", storage_key="k", status="ready")
        s.add(doc)
        await s.flush()
        job = ExtractionJob(org_id=org_id, document_id=doc.id, status="completed")
        s.add(job)
        await s.flush()
        rec = EmailRecord(org_id=org_id, extraction_job_id=job.id,
                          recipient_email=f"r{uuid.uuid4().hex}@x.com", subject="s", body="b",
                          confidence=0.99, validation_status="valid", review_status="approved")
        s.add(rec)
        await s.flush()
        camp = Campaign(org_id=org_id, connected_account_id=acct.id, name="c",
                        created_by=user_id, status="running", record_ids=[str(rec.id)])
        s.add(camp)
        await s.flush()
        return org_id, str(camp.id), str(rec.id), str(acct.id)


async def test_hard_bounce_suppresses_and_marks_bounced():
    org_id, campaign_id, record_id, account_id = await _setup()
    async with org_session(org_id) as s:
        rec = await s.get(EmailRecord, record_id)
        recipient = rec.recipient_email
        msg = Message(org_id=org_id, campaign_id=campaign_id, email_record_id=record_id,
                      connected_account_id=account_id, idempotency_key=uuid.uuid4().hex,
                      provider_message_id="pm-bounce", status="sent")
        s.add(msg)

    async with org_session(org_id) as s:
        result = await handle_inbound(s, org_id, {
            "type": "bounce", "provider_message_id": "pm-bounce", "dsn_status": "5.1.1",
        })
        assert result["matched"]

    async with org_session(org_id) as s:
        supp = await s.scalar(select(SuppressionEntry).where(SuppressionEntry.email == recipient))
        assert supp is not None and supp.reason == "hard_bounce"
        msg = await s.scalar(select(Message).where(Message.provider_message_id == "pm-bounce"))
        assert msg.status == "bounced"
        ev = await s.scalar(select(Event).where(Event.message_id == msg.id, Event.type == "bounce"))
        assert ev is not None


async def test_circuit_breaker_pauses_campaign():
    org_id, campaign_id, record_id, account_id = await _setup()
    async with org_session(org_id) as s:
        for i in range(3):
            s.add(Message(org_id=org_id, campaign_id=campaign_id, email_record_id=record_id,
                          connected_account_id=account_id, idempotency_key=uuid.uuid4().hex,
                          provider_message_id=f"pm{i}", status="sent"))
        await s.flush()
        first = await s.scalar(select(Message).where(Message.campaign_id == campaign_id))
        s.add(Event(org_id=org_id, message_id=first.id, type="bounce", meta={"hard": True}))

    original = settings.circuit_breaker_min_sent
    settings.circuit_breaker_min_sent = 2
    try:
        async with org_session(org_id) as s:
            tripped = await check_circuit_breaker(s, campaign_id)
            assert tripped is True
        async with org_session(org_id) as s:
            camp = await s.get(Campaign, campaign_id)
            assert camp.status == "paused"
    finally:
        settings.circuit_breaker_min_sent = original
