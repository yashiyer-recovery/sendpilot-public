"""Bounce / complaint / reply ingestion (PRD §12).

Pure, transport-agnostic logic: the Gmail Pub/Sub and Microsoft Graph webhook
handlers normalize provider notifications into the event shape consumed here, so
this is unit-testable with fixtures. Hard bounces (5.x.x DSN) and complaints add
a suppression entry; replies record a reply event (and would stop a sequence in
v1.x).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..compliance.suppression import add_suppression
from ..db.models import EmailRecord, Event, Message
from ..metrics import bounces_total, complaints_total

HARD_DSN = re.compile(r"\b5\.\d+\.\d+\b")  # 5.x.x = permanent failure


async def _message_by_provider_id(session: AsyncSession, provider_message_id: str) -> Message | None:
    return await session.scalar(
        select(Message).where(Message.provider_message_id == provider_message_id)
    )


async def _recipient(session: AsyncSession, message: Message) -> str | None:
    rec = await session.get(EmailRecord, message.email_record_id)
    return rec.recipient_email if rec else None


async def handle_inbound(session: AsyncSession, org_id: str, event: dict) -> dict:
    """event = {type, provider_message_id, dsn_status?, from_addr?}."""
    msg = await _message_by_provider_id(session, event["provider_message_id"])
    if msg is None:
        return {"matched": False}

    etype = event["type"]
    if etype == "delivered":
        session.add(Event(org_id=org_id, message_id=msg.id, type="delivered"))
        if msg.status == "sent":
            msg.status = "delivered"

    elif etype == "bounce":
        dsn = event.get("dsn_status", "")
        hard = bool(HARD_DSN.search(dsn))
        bounces_total.labels(kind="hard" if hard else "soft").inc()
        if hard:
            recipient = await _recipient(session, msg)
            if recipient:
                await add_suppression(session, org_id, recipient, "hard_bounce")
            msg.status = "bounced"
        session.add(Event(org_id=org_id, message_id=msg.id, type="bounce",
                          meta={"dsn": dsn, "hard": hard}))

    elif etype == "complaint":
        complaints_total.inc()
        recipient = await _recipient(session, msg)
        if recipient:
            await add_suppression(session, org_id, recipient, "complaint")
        session.add(Event(org_id=org_id, message_id=msg.id, type="complaint"))

    elif etype == "reply":
        session.add(Event(org_id=org_id, message_id=msg.id, type="reply",
                          meta={"from": event.get("from_addr")}))
        # stop-on-reply halts the sequence for this recipient (sequences are v1.x).

    return {"matched": True, "campaign_id": str(msg.campaign_id)}
