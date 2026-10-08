"""Send worker — idempotent claim, pre-send guards, retries/backoff (PRD §11.8).

Crash-safety: the message row is claimed (committed) BEFORE the provider call, so
a retried task hits the unique-key conflict and becomes a no-op — at most one
provider send per (campaign, record, step). Proven by the chaos test.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime

import httpx

from ..campaign.merge import MissingMergeField, render
from ..compliance.suppression import is_suppressed
from ..config import settings
from ..connection.tokens import valid_access_token
from ..crypto.envelope import decrypt_tokens
from ..crypto.kms import get_kms
from ..db.models import Campaign, ConnectedAccount, EmailRecord, Message, Organization
from ..logging import get_logger
from ..metrics import provider_errors_total, send_latency_seconds, send_total
from ..worker.context import task_session
from .gmail import GmailProvider
from .idempotency import claim_message, idem_key
from .microsoft import MicrosoftProvider
from .provider import OutboundEmail
from .ratelimit import allow_send, under_daily_cap
from .smtp import SmtpProvider
from .warmup import effective_daily_cap

log = get_logger("sending.worker")

PROVIDERS = {
    "gmail": GmailProvider(),
    "microsoft": MicrosoftProvider(),
    "smtp": SmtpProvider(),
}


def _merge_cc(record_cc) -> list[str] | None:
    """Per-record CC plus the global always-CC list (PRD §13.1), deduped."""
    cc = list(record_cc) if record_cc else []
    lower = {c.lower() for c in cc}
    for addr in settings.always_cc_list:
        if addr.lower() not in lower:
            cc.append(addr)
    return cc or None


async def _credential_for(session, account: ConnectedAccount):
    """OAuth access token for Gmail/Graph; decrypted SMTP config for SMTP."""
    if account.provider == "smtp":
        return decrypt_tokens(get_kms(), account.enc_key_id, account.enc_tokens)
    return await valid_access_token(session, account)
MAX_ATTEMPTS = 5
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# Gmail intermittently returns 400 under a send burst even for valid messages
# (proven: the same request succeeds on immediate retry). Retry 400 a few times
# before giving up — a genuine bad-request just fails after these attempts.
TRANSIENT_400_MAX = 3


async def _mark(org_id: str, msg_id: str, status: str, **fields) -> None:
    async with task_session(org_id) as session:
        msg = await session.get(Message, msg_id)
        if msg is None:
            return
        msg.status = status
        for k, v in fields.items():
            setattr(msg, k, v)


async def send_message_task(
    ctx: dict, org_id: str, campaign_id: str, record_id: str, step: int = 0
) -> None:
    # ── Phase A: claim + guards + token + render (one committed transaction) ──
    async with task_session(org_id) as session:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None or campaign.status == "paused":
            return
        account = await session.get(ConnectedAccount, campaign.connected_account_id)
        record = await session.get(EmailRecord, record_id)
        org = await session.get(Organization, org_id)
        if account is None or record is None:
            return

        key = idem_key(campaign_id, record_id, step)
        msg_id = await claim_message(
            session, org_id=org_id, campaign_id=campaign_id, record_id=record_id,
            account_id=str(account.id), step=step, key=key,
        )
        if msg_id is None:
            return  # already claimed/sent — idempotent no-op

        msg = await session.get(Message, msg_id)

        # Pre-send guards.
        if record.recipient_email and await is_suppressed(session, record.recipient_email):
            msg.status = "skipped"
            msg.error = "suppressed"
            return
        cap = effective_daily_cap(account.warmup_day, account.daily_cap)
        if not await under_daily_cap(str(account.id), cap):
            msg.status = "skipped"
            msg.error = "daily_cap"
            return

        try:
            credential = await _credential_for(session, account)
            subject, body = render(record, org)
        except MissingMergeField as exc:
            msg.status = "failed"
            msg.error = f"missing_merge_field:{exc.field}"
            return

        msg.status = "sending"
        ctx_send = {
            "msg_id": msg_id,
            "provider": account.provider,
            "credential": credential,
            "from_email": account.account_email,
            "to": record.recipient_email,
            "subject": subject,
            "body": body,
            "body_format": record.body_format,
            "cc": _merge_cc(record.cc),
            "rate_per_min": account.rate_per_min,
            "account_id": str(account.id),
        }

    # ── Rate-limit wait (outside the DB transaction) ──
    for _ in range(60):
        if await allow_send(ctx_send["account_id"], ctx_send["rate_per_min"]):
            break
        await asyncio.sleep(1 + random.random())

    # ── Phase B: provider send with retry/backoff ──
    provider = PROVIDERS[ctx_send["provider"]]
    email = OutboundEmail(
        from_email=ctx_send["from_email"], to=ctx_send["to"], subject=ctx_send["subject"],
        body=ctx_send["body"], body_format=ctx_send["body_format"], cc=ctx_send["cc"],
    )
    t0 = time.perf_counter()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await provider.send(ctx_send["credential"], email)
            send_latency_seconds.labels(provider=ctx_send["provider"]).observe(
                time.perf_counter() - t0
            )
            send_total.labels(provider=ctx_send["provider"], status="sent").inc()
            await _mark(
                org_id, ctx_send["msg_id"], "sent",
                provider_message_id=result.provider_message_id,
                thread_id=result.thread_id, sent_at=datetime.now(UTC),
            )
            log.info("send.sent", msg_id=ctx_send["msg_id"], provider=ctx_send["provider"])
            return
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            provider_errors_total.labels(provider=ctx_send["provider"], code=str(code)).inc()
            retryable = code in RETRYABLE_STATUS or (code == 400 and attempt < TRANSIENT_400_MAX)
            if retryable and attempt < MAX_ATTEMPTS:
                await asyncio.sleep(min(60, 2 ** attempt) + random.random())
                continue
            send_total.labels(provider=ctx_send["provider"], status="failed").inc()
            detail = (exc.response.text or "")[:180].replace("\n", " ")
            await _mark(org_id, ctx_send["msg_id"], "failed", error=f"http_{code}:{detail}")
            log.warning("send.failed", msg_id=ctx_send["msg_id"], code=code, detail=detail)
            return
        except httpx.HTTPError as exc:
            provider_errors_total.labels(provider=ctx_send["provider"], code="network").inc()
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(min(60, 2 ** attempt) + random.random())
                continue
            send_total.labels(provider=ctx_send["provider"], status="failed").inc()
            await _mark(org_id, ctx_send["msg_id"], "failed", error=str(exc)[:200])
            return
