"""Re-send ONLY the records that were skipped by the daily/warmup cap.

Targets records that have a 'skipped' message and NO 'sent' message for the given
account — so the already-delivered 20 are never touched. Creates a fresh campaign
(new idempotency keys) and enqueues the sends.

    docker compose exec api python tests/resend_capped.py
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import distinct, select

from sendpilot.db.models import AppUser, Campaign, ConnectedAccount, EmailRecord, Message
from sendpilot.db.session import org_session, system_session
from sendpilot.queue import enqueue

ACCOUNT_EMAIL = os.environ.get("RESEND_ACCOUNT", "yash@zorbeai.com")


async def main() -> None:
    async with system_session() as s:
        acct = await s.scalar(
            select(ConnectedAccount).where(ConnectedAccount.account_email == ACCOUNT_EMAIL)
        )
        if acct is None:
            print(f"No connected account for {ACCOUNT_EMAIL}")
            return
        org_id, account_id = str(acct.org_id), str(acct.id)
        user = await s.scalar(select(AppUser).where(AppUser.org_id == acct.org_id))
        user_id = str(user.id)

    async with org_session(org_id) as s:
        skipped = set((await s.scalars(
            select(distinct(Message.email_record_id))
            .where(Message.connected_account_id == account_id, Message.status == "skipped")
        )).all())
        already_sent = set((await s.scalars(
            select(distinct(Message.email_record_id))
            .where(Message.connected_account_id == account_id, Message.status == "sent")
        )).all())
        target_ids = [r for r in skipped if r not in already_sent]  # never re-hit the sent ones

        recs = (await s.scalars(
            select(EmailRecord).where(EmailRecord.id.in_(target_ids))
        )).all()
        approved = [r for r in recs if r.review_status == "approved"]
        emails = [r.recipient_email for r in approved]

        if not approved:
            print("Nothing to resend (no approved, capped-but-unsent records).")
            return

        campaign = Campaign(
            org_id=org_id, connected_account_id=account_id, name="Resend (capped 9)",
            created_by=user_id, record_ids=[str(r.id) for r in approved], status="running",
        )
        s.add(campaign)
        await s.flush()
        campaign_id = str(campaign.id)

    for r in approved:
        await enqueue("send_message_task", org_id, campaign_id, str(r.id), 0)

    print(f"campaign {campaign_id}: enqueued {len(approved)} record(s)")
    for e in emails:
        print("  ->", e)


if __name__ == "__main__":
    asyncio.run(main())
