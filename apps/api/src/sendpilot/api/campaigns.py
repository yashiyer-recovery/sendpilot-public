"""Campaign create + send + message/event listing (PRD §10, §25).

The send action enqueues ONLY approved records — re-verified server-side, never
trusting the client. This gate is both quality control and anti-abuse (PRD §10).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..db.models import Campaign, ConnectedAccount, EmailRecord, Event, Message
from ..db.session import org_session
from ..deps import current_principal, get_db, require_role
from ..queue import enqueue
from .errors import AppError
from .schemas import (
    CampaignCreate,
    CampaignOut,
    EventOut,
    MessageOut,
    SendRequest,
    SendResponse,
)

router = APIRouter(prefix="/v1", tags=["campaigns"])


@router.post("/campaigns", response_model=CampaignOut)
async def create_campaign(
    body: CampaignCreate, principal: Principal = Depends(current_principal)
) -> CampaignOut:
    async with org_session(principal.org_id) as session:
        account = await session.get(ConnectedAccount, body.connected_account_id)
        if account is None:
            raise AppError("not_found", "connected account not found")
        campaign = Campaign(
            org_id=principal.org_id, connected_account_id=account.id, name=body.name,
            type=body.type, status="draft", created_by=principal.user_id,
            record_ids=body.record_ids,
        )
        session.add(campaign)
        await session.flush()
        out = CampaignOut(id=str(campaign.id), name=campaign.name, type=campaign.type,
                          status=campaign.status, record_count=len(body.record_ids))
    return out


@router.post("/campaigns/{campaign_id}/send", response_model=SendResponse)
async def send_campaign(
    campaign_id: str,
    body: SendRequest,
    principal: Principal = Depends(require_role("admin")),
) -> SendResponse:
    async with org_session(principal.org_id) as session:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            raise AppError("not_found", "campaign not found")
        rows = (await session.scalars(
            select(EmailRecord).where(EmailRecord.id.in_(campaign.record_ids))
        )).all()
        # Server-side approved-only gate.
        approved = [r for r in rows if r.review_status == "approved"]
        # Dedup: never re-email someone already sent to from ANY mailbox in the org.
        already = {
            e.lower() for e in (await session.scalars(
                select(distinct(EmailRecord.recipient_email))
                .join(Message, Message.email_record_id == EmailRecord.id)
                .where(Message.status == "sent")
            )).all() if e
        }
        to_send = [r for r in approved if (r.recipient_email or "").lower() not in already]
        skipped_unapproved = len(campaign.record_ids) - len(approved)
        skipped_already = len(approved) - len(to_send)
        send_ids = [str(r.id) for r in to_send]
        campaign.status = "running"

    for record_id in send_ids:
        await enqueue("send_message_task", principal.org_id, campaign_id, record_id, 0)

    return SendResponse(campaign_id=campaign_id, enqueued=len(send_ids),
                        skipped_unapproved=skipped_unapproved,
                        skipped_already_sent=skipped_already)


@router.get("/messages", response_model=list[MessageOut])
async def list_messages(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> list[MessageOut]:
    rows = (await db.scalars(
        select(Message).where(Message.campaign_id == campaign_id)
    )).all()
    return [
        MessageOut(id=str(m.id), status=m.status, provider_message_id=m.provider_message_id,
                   thread_id=m.thread_id, error=m.error)
        for m in rows
    ]


@router.get("/messages/{message_id}/events", response_model=list[EventOut])
async def list_events(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> list[EventOut]:
    rows = (await db.scalars(
        select(Event).where(Event.message_id == message_id)
    )).all()
    return [EventOut(type=e.type, occurred_at=e.occurred_at.isoformat()) for e in rows]
