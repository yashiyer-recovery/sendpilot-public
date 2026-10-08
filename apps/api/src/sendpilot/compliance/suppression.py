"""Suppression list operations (PRD §17.2)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SuppressionEntry


async def is_suppressed(session: AsyncSession, email: str) -> bool:
    row = await session.scalar(
        select(SuppressionEntry).where(SuppressionEntry.email == email.lower())
    )
    return row is not None


async def add_suppression(
    session: AsyncSession, org_id: str, email: str, reason: str
) -> None:
    if await is_suppressed(session, email):
        return
    session.add(SuppressionEntry(org_id=org_id, email=email.lower(), reason=reason))
