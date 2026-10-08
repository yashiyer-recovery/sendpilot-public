"""Provider event webhook (PRD §12, §14).

Receives normalized delivered/bounce/complaint/reply events (the Gmail Pub/Sub
and Graph subscription handlers normalize into this shape). Authenticated by a
shared secret. On a bounce/complaint it also runs the circuit breaker.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..analytics.circuit_breaker import check_circuit_breaker
from ..config import settings
from ..db.session import org_session
from ..tracking.bounce import handle_inbound
from .errors import AppError
from .schemas import WebhookEvent

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/provider")
async def provider_webhook(payload: WebhookEvent, request: Request) -> dict:
    if request.headers.get("x-webhook-token") != settings.webhook_secret:
        raise AppError("forbidden", "invalid webhook token")

    async with org_session(payload.org_id) as session:
        result = await handle_inbound(session, payload.org_id, payload.model_dump())

    if payload.type in ("bounce", "complaint") and result.get("campaign_id"):
        async with org_session(payload.org_id) as session:
            await check_circuit_breaker(session, result["campaign_id"])

    return {"ok": True, **result}
