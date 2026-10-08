"""Gmail provider (PRD §11.3). base64url-encodes the MIME and posts to send.

With MOCK_PROVIDER the send URL points at the local mock-provider sandbox.
"""

from __future__ import annotations

import base64

import httpx

from ..config import settings
from .mime import build_mime
from .provider import EmailProvider, OutboundEmail, SendResult

GMAIL_SEND_REAL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _send_url() -> str:
    if settings.mock_provider:
        return f"{settings.mock_provider_url}/mock/gmail/send"
    return GMAIL_SEND_REAL


class GmailProvider(EmailProvider):
    async def send(self, credential: str, email: OutboundEmail) -> SendResult:
        raw_bytes, _ = build_mime(email)
        raw = base64.urlsafe_b64encode(raw_bytes).decode()
        body: dict = {"raw": raw}
        if email.thread_id:
            body["threadId"] = email.thread_id
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _send_url(),
                headers={"Authorization": f"Bearer {credential}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        return SendResult(
            provider_message_id=data.get("id"), thread_id=data.get("threadId")
        )
