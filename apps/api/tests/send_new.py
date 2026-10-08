"""Send a staged outbound list, skipping anyone already emailed (dedup against
all 'sent' messages in the org). Creates records + a campaign and enqueues sends.

    docker compose exec api python tests/send_new.py
"""

from __future__ import annotations

import asyncio
import json
import os

from sqlalchemy import distinct, select

from sendpilot.db.models import (
    AppUser,
    Campaign,
    ConnectedAccount,
    Document,
    EmailRecord,
    ExtractionJob,
    Message,
)
from sendpilot.db.session import org_session, system_session
from sendpilot.queue import enqueue

ACCOUNT = os.environ.get("SEND_ACCOUNT", "yash@zorbeai.com")
DATA = os.environ.get("OUTBOUND_JSON", "/app/tests/_outbound.json")


async def main() -> None:
    rows = json.load(open(DATA))  # [{email, subject, body}, ...]

    async with system_session() as s:
        acct = await s.scalar(
            select(ConnectedAccount).where(ConnectedAccount.account_email == ACCOUNT)
        )
        if acct is None:
            print(f"No connected account for {ACCOUNT}")
            return
        acct.warmup_day = 8  # lift warmup cap (established mailbox, actively sending)
        org_id, account_id = str(acct.org_id), str(acct.id)
        user = await s.scalar(select(AppUser).where(AppUser.org_id == acct.org_id))
        user_id = str(user.id)

    async with org_session(org_id) as s:
        # Dedup: skip anyone who already has a 'sent' message in this org.
        already = {
            e.lower() for e in (await s.scalars(
                select(distinct(EmailRecord.recipient_email))
                .join(Message, Message.email_record_id == EmailRecord.id)
                .where(Message.status == "sent")
            )).all() if e
        }
        new_rows = [r for r in rows if (r.get("email") or "").strip().lower() not in already]
        if not new_rows:
            print("Nothing new to send — all recipients were already emailed.")
            return

        doc = Document(
            org_id=org_id, uploaded_by=user_id, filename="Zorbe_Outbound_Deduped.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size_bytes=0, sha256="manual", storage_key="manual", status="ready",
        )
        s.add(doc)
        await s.flush()
        job = ExtractionJob(
            org_id=org_id, document_id=doc.id, status="completed", shape="tabular",
            record_count=len(new_rows), needs_review_count=0,
        )
        s.add(job)
        await s.flush()

        rec_ids = []
        for r in new_rows:
            rec = EmailRecord(
                org_id=org_id, extraction_job_id=job.id, recipient_email=r["email"].strip(),
                subject=r.get("subject") or "", body=r.get("body") or "", body_format="text",
                confidence=0.99, validation_status="valid", review_status="approved",
            )
            s.add(rec)
            await s.flush()
            rec_ids.append(str(rec.id))

        campaign = Campaign(
            org_id=org_id, connected_account_id=account_id, name="Outbound (new only)",
            created_by=user_id, record_ids=rec_ids, status="running",
        )
        s.add(campaign)
        await s.flush()
        campaign_id = str(campaign.id)
        emails = [r["email"] for r in new_rows]

    for rid in rec_ids:
        await enqueue("send_message_task", org_id, campaign_id, rid, 0)

    print(f"campaign {campaign_id}: enqueued {len(rec_ids)} new (skipped {len(rows) - len(rec_ids)} "
          f"already-sent)")
    for e in emails:
        print("  ->", e)


if __name__ == "__main__":
    asyncio.run(main())
