"""Send booking-pipeline follow-ups as threaded replies (runs INSIDE the api container).

Reads /app/tests/_booking_followups.json: [{email, step, subject, body}] (staged by
bookings/pipeline.py followups). For each target it finds the most recent SENT message
to that recipient and replies into that thread. Safety properties:

  - anyone whose touch-1 never actually sent is skipped (state drift is harmless)
  - idempotency key is deterministic per (record, step) across runs and campaigns,
    so re-running this script can never double-send a step
  - bodies arrive fully personalized; this script never templates

    docker compose exec -e DRY=1 api python /app/bookings_send_followups.py   # preview
    docker compose exec api python /app/bookings_send_followups.py           # send
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime

import httpx
from sqlalchemy import select, text

from sendpilot.config import settings
from sendpilot.connection.tokens import valid_access_token
from sendpilot.db.models import AppUser, Campaign, ConnectedAccount
from sendpilot.db.session import org_session, system_session
from sendpilot.sending.gmail import GmailProvider
from sendpilot.sending.idempotency import claim_message
from sendpilot.sending.provider import OutboundEmail

DRY = os.environ.get("DRY") == "1"
FROM = os.environ.get("FROM", "yash@zorbe.ai")
TARGETS = os.environ.get("TARGETS", "/app/tests/_booking_followups.json")


def booking_idem_key(record_id: str, step: int) -> str:
    # deliberately campaign-independent: one follow-up per (record, step), ever
    return hashlib.sha256(f"booking-followup:{record_id}:{step}".encode()).hexdigest()


async def rfc_message_id(client: httpx.AsyncClient, token: str, gmail_id: str) -> str | None:
    r = await client.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{gmail_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"format": "metadata", "metadataHeaders": "Message-ID"},
    )
    if r.status_code != 200:
        return None
    for h in r.json().get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == "message-id":
            return h.get("value")
    return None


async def main() -> None:
    targets = json.load(open(TARGETS))
    async with system_session() as s:
        acct = await s.scalar(select(ConnectedAccount).where(ConnectedAccount.account_email == FROM))
        org_id, acct_id = str(acct.org_id), str(acct.id)
        user = await s.scalar(select(AppUser).where(AppUser.org_id == acct.org_id))
        user_id = str(user.id)
        token = await valid_access_token(s, acct)

    # newest sent message per recipient -> (record_id, subject, gmail id, thread id)
    async with org_session(org_id) as s:
        rows = (await s.execute(text("""
            SELECT DISTINCT ON (lower(er.recipient_email))
                   lower(er.recipient_email), er.id::text, er.subject,
                   m.provider_message_id, m.thread_id
            FROM message m JOIN email_record er ON er.id = m.email_record_id
            WHERE m.status = 'sent'
            ORDER BY lower(er.recipient_email), m.sent_at DESC
        """))).all()
    sent_index = {r[0]: dict(rec_id=r[1], subject=r[2], gid=r[3], tid=r[4]) for r in rows}

    ready, skipped_unsent = [], []
    for t in targets:
        orig = sent_index.get(t["email"].lower())
        if orig is None:
            skipped_unsent.append(t["email"])
            continue
        # thread on the ORIGINAL sent subject, not the staged follow-up subject
        ready.append({**t, "rec_id": orig["rec_id"], "orig_subject": orig["subject"], "gid": orig["gid"], "tid": orig["tid"]})
    print(f"targets: {len(targets)} | ready: {len(ready)} | skipped (touch-1 never sent): {len(skipped_unsent)}")
    for e in skipped_unsent:
        print(f"  !! never sent, skipping: {e}")

    if DRY:
        for t in ready[:3]:
            print(f"\n--- preview: {t['email']} step {t['step']} ---")
            print("Subject: Re:", (t.get("orig_subject") or "")[:80])
            print("Cc:", settings.always_cc_list)
            print(t["body"])
        print("\nDRY RUN - nothing sent.")
        return
    if not ready:
        return

    async with org_session(org_id) as s:
        camp = Campaign(org_id=org_id, connected_account_id=acct_id, name="Booking follow-up",
                        created_by=user_id, record_ids=[t["rec_id"] for t in ready], status="running")
        s.add(camp)
        await s.flush()
        campaign_id = str(camp.id)

    sent = failed = skipped = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, t in enumerate(ready, 1):
            async with org_session(org_id) as s:
                msg_id = await claim_message(
                    s, org_id=org_id, campaign_id=campaign_id, record_id=t["rec_id"],
                    account_id=acct_id, step=t["step"],
                    key=booking_idem_key(t["rec_id"], t["step"]),
                )
            if msg_id is None:
                skipped += 1
                continue

            base = t.get("orig_subject") or t.get("subject") or ""
            subject = base if base.lower().startswith("re:") else f"Re: {base}"
            mid = await rfc_message_id(client, token, t["gid"]) if t["gid"] else None
            out = OutboundEmail(
                from_email=FROM, to=t["email"], subject=subject, body=t["body"],
                body_format="text", cc=settings.always_cc_list or None,
                in_reply_to=mid, references=mid, thread_id=t["tid"],
            )
            try:
                try:
                    res = await GmailProvider().send(token, out)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 400 and out.thread_id:
                        out = replace(out, thread_id=None)
                        res = await GmailProvider().send(token, out)
                        print("      (threadId rejected - sent unthreaded)")
                    else:
                        raise
                async with org_session(org_id) as s:
                    from sendpilot.db.models import Message
                    m = await s.get(Message, msg_id)
                    m.status = "sent"
                    m.provider_message_id = res.provider_message_id
                    m.thread_id = res.thread_id
                    m.sent_at = datetime.now(UTC)
                sent += 1
                print(f"  [{i}/{len(ready)}] step {t['step']} sent -> {t['email']}")
            except Exception as exc:
                async with org_session(org_id) as s:
                    from sendpilot.db.models import Message
                    m = await s.get(Message, msg_id)
                    m.status = "failed"
                    m.error = str(exc)[:180]
                failed += 1
                print(f"  [{i}/{len(ready)}] FAILED -> {t['email']}: {str(exc)[:120]}")
            await asyncio.sleep(1.5)

    print(f"\nfollow-ups: sent={sent} failed={failed} skipped(already-sent-this-step)={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
