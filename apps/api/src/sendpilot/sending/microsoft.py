"""Microsoft 365 provider via Graph sendMail (PRD §11.4).

Graph ``/me/sendMail`` returns 202 with no message id. To capture an id/thread
for tracking, the production path is create-draft -> send -> read Sent Items
(deferred); the mock returns {id, threadId} directly for local demos.
"""

from __future__ import annotations

import httpx

from ..config import settings
from .provider import EmailProvider, OutboundEmail, SendResult

GRAPH_SENDMAIL_REAL = "https://graph.microsoft.com/v1.0/me/sendMail"


def _send_url() -> str:
    if settings.mock_provider:
        return f"{settings.mock_provider_url}/mock/ms/sendmail"
    return GRAPH_SENDMAIL_REAL


class MicrosoftProvider(EmailProvider):
    async def send(self, credential: str, email: OutboundEmail) -> SendResult:
        message = {
            "subject": email.subject,
            "body": {
                "contentType": "HTML" if email.body_format == "html" else "Text",
                "content": email.body,
            },
            "toRecipients": [{"emailAddress": {"address": email.to}}],
            "ccRecipients": [{"emailAddress": {"address": a}} for a in (email.cc or [])],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _send_url(),
                headers={"Authorization": f"Bearer {credential}"},
                json={"message": message, "saveToSentItems": True},
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
        return SendResult(
            provider_message_id=data.get("id"), thread_id=data.get("threadId")
        )
