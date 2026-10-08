"""RLS tenant isolation — the keystone test (PRD §5.3).

Requires a live Postgres (the app connecting as the NON-superuser role) with
migrations applied. Marked ``db``; runs in CI and inside docker-compose.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from sendpilot.db.models import Organization, SuppressionEntry
from sendpilot.db.session import SessionLocal, org_session, system_session

pytestmark = pytest.mark.db


async def _make_org(name: str) -> str:
    async with system_session() as s:
        org = Organization(name=name)
        s.add(org)
        await s.flush()
        return str(org.id)


async def test_tenant_isolation():
    org_a = await _make_org("tenant-A")
    org_b = await _make_org("tenant-B")
    email = f"x{uuid.uuid4().hex}@a.test"

    async with org_session(org_a) as s:
        s.add(SuppressionEntry(org_id=org_a, email=email, reason="manual"))

    # Visible within org A.
    async with org_session(org_a) as s:
        rows = (await s.scalars(select(SuppressionEntry).where(SuppressionEntry.email == email))).all()
        assert len(rows) == 1

    # Invisible to org B — the whole point.
    async with org_session(org_b) as s:
        rows = (await s.scalars(select(SuppressionEntry))).all()
        assert rows == []


async def test_missing_org_context_denies():
    """A session that forgets to set the org GUC must see zero rows, not error."""
    org = await _make_org("tenant-C")
    async with org_session(org) as s:
        s.add(SuppressionEntry(org_id=org, email=f"c{uuid.uuid4().hex}@c.test", reason="manual"))

    async with SessionLocal() as s:  # no GUC set
        count = await s.scalar(select(func.count()).select_from(SuppressionEntry))
        assert count == 0
