"""Validation, dedupe, suppression enforcement, confidence gating (PRD §9).

Records that fail or fall below the confidence threshold are marked, never
silently dropped. Suppression is enforced here AND again at send time (§11/§17).
"""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import SuppressionEntry
from ..extraction.schema import EmailRecord
from .mx import has_mx

ROLE_LOCALPARTS = {"info", "sales", "support", "admin", "noreply", "no-reply"}


async def suppression_set(session: AsyncSession) -> set[str]:
    rows = await session.scalars(select(SuppressionEntry.email))
    return {e.lower() for e in rows.all()}


async def validate_records(session: AsyncSession, records: list[EmailRecord]) -> list[EmailRecord]:
    suppressed = await suppression_set(session)
    seen: set[str] = set()
    for r in records:
        addr = (r.recipient_email or "").strip().lower()
        status = "valid"
        try:
            v = validate_email(addr, check_deliverability=False)
            addr = v.normalized.lower()
        except EmailNotValidError:
            status = "invalid"

        if status == "valid":
            if not r.subject or not r.body:
                status = "needs_review"
            elif addr in suppressed:
                status = "suppressed"
            elif addr in seen:
                status = "duplicate"
            elif settings.validate_mx and not has_mx(addr.split("@")[1]):
                status = "needs_review"
            elif r.confidence < settings.confidence_threshold:
                status = "needs_review"

        if status == "valid" and addr.split("@")[0] in ROLE_LOCALPARTS:
            r.merge_fields["_role_account"] = "true"  # flag, do not block

        r.recipient_email = addr
        r.validation_status = status
        seen.add(addr)
    return records
