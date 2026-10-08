"""SMTP provider (PRD §11.5).

Sends a built MIME message over SMTP. The credential is a config dict decrypted
from the connected account: {host, port, username, password, starttls}. Works
with Gmail SMTP (smtp.gmail.com:587 + an App Password) and with a local sink
like Mailpit (port 1025, no TLS/auth).
"""

from __future__ import annotations

from typing import Any

import aiosmtplib

from .mime import build_mime_message
from .provider import EmailProvider, OutboundEmail, SendResult


class SmtpProvider(EmailProvider):
    async def send(self, credential: Any, email: OutboundEmail) -> SendResult:
        cfg = credential  # {host, port, username, password, starttls}
        message, msg_id = build_mime_message(email)
        await aiosmtplib.send(
            message,
            hostname=cfg["host"],
            port=int(cfg["port"]),
            start_tls=bool(cfg.get("starttls", True)),
            username=cfg.get("username") or None,
            password=cfg.get("password") or None,
        )
        # SMTP returns no provider id; use the RFC Message-ID for tracking.
        return SendResult(provider_message_id=msg_id, thread_id=None)
