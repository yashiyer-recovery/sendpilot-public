"""Idempotency — the double-send guard (PRD §11.7).

The key is deterministic from (campaign, record, step). The worker claims a
message by inserting that key; a unique-constraint conflict means the message
was already claimed/sent and the task is a no-op.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def idem_key(campaign_id: str, record_id: str, step: int) -> str:
    return hashlib.sha256(f"{campaign_id}:{record_id}:{step}".encode()).hexdigest()


_CLAIM_SQL = text(
    """
    INSERT INTO message (org_id, campaign_id, email_record_id, connected_account_id,
                         step_index, idempotency_key, status)
    VALUES (:org_id, :campaign_id, :record_id, :account_id, :step, :key, 'queued')
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING id
    """
)


async def claim_message(
    session: AsyncSession,
    *,
    org_id: str,
    campaign_id: str,
    record_id: str,
    account_id: str,
    step: int,
    key: str,
) -> str | None:
    """Insert-or-skip. Returns the new message id, or None if already claimed."""
    result = await session.execute(
        _CLAIM_SQL,
        {
            "org_id": org_id,
            "campaign_id": campaign_id,
            "record_id": record_id,
            "account_id": account_id,
            "step": step,
            "key": key,
        },
    )
    row = result.first()
    return str(row[0]) if row else None
