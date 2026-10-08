"""Send a staged batch with org-wide dedup and optional round-robin across inboxes.

Env:
  OUTBOUND_JSON   path to [{email,subject,body}, ...]   (default /app/tests/_batch.json)
  ACCOUNTS        comma-separated sender emails; >1 => round-robin
  DRY_RUN         "1" to only report counts (no records created, no sends)

    docker compose exec -e ACCOUNTS=yash@zorbe.ai -e DRY_RUN=1 api python tests/send_batch.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os

from sqlalchemy import distinct, select

from sendpilot.cache import get_redis
from sendpilot.config import settings
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
from sendpilot.sending.warmup import effective_daily_cap

DATA = os.environ.get("OUTBOUND_JSON", "/app/tests/_batch.json")
ACCOUNTS = [a.strip() for a in os.environ.get("ACCOUNTS", "yash@zorbe.ai").split(",") if a.strip()]
DRY_RUN = os.environ.get("DRY_RUN") == "1"
LIMIT = int(os.environ["LIMIT"]) if os.environ.get("LIMIT") else None  # send at most N new rows
# Explicit per-inbox counts, e.g. "yash@zorbe.ai:80,yash@zorbeai.com:20". Overrides
# the auto-distributor; assigns the first N new rows to each inbox in order.
SPLIT = None
if os.environ.get("SPLIT"):
    SPLIT = {}
    for _pair in os.environ["SPLIT"].split(","):
        _em, _c = _pair.rsplit(":", 1)
        SPLIT[_em.strip()] = int(_c)


async def main() -> None:
    import json
    rows = json.load(open(DATA))

    async with system_session() as s:
        accts = []
        for email in ACCOUNTS:
            a = await s.scalar(
                select(ConnectedAccount).where(ConnectedAccount.account_email == email)
            )
            if a is None:
                print(f"!! no connected account for {email}")
                return
            accts.append(a)
        org_id = str(accts[0].org_id)
        user = await s.scalar(select(AppUser).where(AppUser.org_id == accts[0].org_id))
        user_id = str(user.id)
        caps = {str(a.id): effective_daily_cap(a.warmup_day, a.daily_cap) for a in accts}
        acct_ids = [str(a.id) for a in accts]

    # Remaining headroom TODAY = cap - already-sent-today (Redis daily counter),
    # so we never route to an inbox that would just skip on daily_cap.
    r = get_redis()
    today = dt.date.today().isoformat()
    used = {aid: int(await r.get(f"cap:{aid}:{today}") or 0) for aid in acct_ids}
    headroom = {aid: max(0, caps[aid] - used[aid]) for aid in acct_ids}

    async with org_session(org_id) as s:
        already = {
            e.lower() for e in (await s.scalars(
                select(distinct(EmailRecord.recipient_email))
                .join(Message, Message.email_record_id == EmailRecord.id)
                .where(Message.status == "sent")
            )).all() if e
        }
        new_rows = [r for r in rows if (r.get("email") or "").strip().lower() not in already]
        total_new = len(new_rows)
        if LIMIT is not None:
            new_rows = new_rows[:LIMIT]

        print(f"file rows: {len(rows)} | already-emailed (org-wide): {len(rows) - total_new} "
              f"| NEW: {total_new}" + (f" | LIMIT this run: {len(new_rows)} (holding {total_new - len(new_rows)})" if LIMIT is not None else ""))
        used_by_email = {email: used[aid] for email, aid in zip(ACCOUNTS, acct_ids)}
        room_by_email = {email: headroom[aid] for email, aid in zip(ACCOUNTS, acct_ids)}
        print(f"accounts: {ACCOUNTS} | cap: {caps} | sent-today: {used_by_email} "
              f"| headroom-today: {room_by_email} | always_cc: {settings.always_cc_list}")

        buckets: dict[str, list] = {aid: [] for aid in acct_ids}
        unplaced = []
        if SPLIT is not None:
            # Explicit per-inbox counts: assign the first N new rows to each inbox in
            # order (clamped to today's headroom so we never over-send a cap).
            ptr = 0
            for email, aid in zip(ACCOUNTS, acct_ids):
                want = min(SPLIT.get(email, 0), headroom[aid])
                buckets[aid] = new_rows[ptr:ptr + want]
                ptr += want
            unplaced = new_rows[ptr:]  # everything past the requested split = held
            note = f" | HELD (not in this split): {len(unplaced)}" if unplaced else ""
        else:
            # Cap-aware round-robin against TODAY's remaining headroom: fill inboxes
            # with room, overflow to others; anything past total headroom is left.
            i = 0
            for r in new_rows:
                placed = False
                for k in range(len(acct_ids)):
                    aid = acct_ids[(i + k) % len(acct_ids)]
                    if len(buckets[aid]) < headroom[aid]:
                        buckets[aid].append(r)
                        i = (i + k + 1) % len(acct_ids)
                        placed = True
                        break
                if not placed:
                    unplaced.append(r)
            note = f" | UNPLACED (no headroom left today): {len(unplaced)}" if unplaced else ""
        dist = {email: len(buckets[aid]) for email, aid in zip(ACCOUNTS, acct_ids)}
        print(f"distribution: {dist}{note}")

        if DRY_RUN:
            print("DRY RUN — nothing sent.")
            return
        if not new_rows:
            print("Nothing new to send.")
            return

        enq = []
        for aid in acct_ids:
            bucket = buckets[aid]
            if not bucket:
                continue
            doc = Document(org_id=org_id, uploaded_by=user_id, filename="batch.xlsx",
                           mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           size_bytes=0, sha256="manual", storage_key="manual", status="ready")
            s.add(doc)
            await s.flush()
            job = ExtractionJob(org_id=org_id, document_id=doc.id, status="completed",
                                shape="tabular", record_count=len(bucket))
            s.add(job)
            await s.flush()
            rec_ids = []
            for r in bucket:
                rec = EmailRecord(org_id=org_id, extraction_job_id=job.id,
                                  recipient_email=r["email"].strip(), subject=r.get("subject") or "",
                                  body=r.get("body") or "", body_format="text", confidence=0.99,
                                  validation_status="valid", review_status="approved")
                s.add(rec)
                await s.flush()
                rec_ids.append(str(rec.id))
            camp = Campaign(org_id=org_id, connected_account_id=aid, name="Batch",
                            created_by=user_id, record_ids=rec_ids, status="running")
            s.add(camp)
            await s.flush()
            enq.append((str(camp.id), rec_ids))

    for campaign_id, rec_ids in enq:
        for rid in rec_ids:
            await enqueue("send_message_task", org_id, campaign_id, rid, 0)
    total = sum(len(r) for _, r in enq)
    print(f"enqueued {total} send(s) across {len(enq)} campaign(s)")


if __name__ == "__main__":
    asyncio.run(main())
