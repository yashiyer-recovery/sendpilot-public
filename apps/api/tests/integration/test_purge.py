"""Retention purge job (PRD §16.3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from sendpilot.db.models import AppUser, Document, Organization
from sendpilot.db.session import org_session, system_session
from sendpilot.privacy.purge import purge_expired_documents

pytestmark = pytest.mark.db


async def test_purge_marks_expired_documents():
    async with system_session() as s:
        org = Organization(name="purge")
        s.add(org)
        await s.flush()
        org_id = str(org.id)
        user = AppUser(org_id=org.id, email=f"u{uuid.uuid4().hex}@acme.com", role="owner")
        s.add(user)
        await s.flush()
        user_id = str(user.id)

    async with org_session(org_id) as s:
        doc = Document(
            org_id=org_id, uploaded_by=user_id, filename="old.csv", mime_type="text/csv",
            size_bytes=1, sha256="x", storage_key=f"{org_id}/missing/old.csv", status="ready",
            retention_expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        s.add(doc)
        await s.flush()
        doc_id = str(doc.id)

    n = await purge_expired_documents({})
    assert n >= 1

    async with org_session(org_id) as s:
        doc = await s.get(Document, doc_id)
        assert doc.status == "purged"
