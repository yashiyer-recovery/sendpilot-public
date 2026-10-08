"""Provider abstraction (PRD §11.1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OutboundEmail:
    from_email: str
    to: str
    subject: str
    body: str
    body_format: str = "html"  # html | text
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str | None = None
    references: str | None = None
    thread_id: str | None = None


@dataclass
class SendResult:
    provider_message_id: str | None = None
    thread_id: str | None = None


class EmailProvider(ABC):
    @abstractmethod
    async def send(self, credential: Any, email: OutboundEmail) -> SendResult:
        """credential is provider-specific: an OAuth access token (Gmail/Graph)
        or an SMTP config dict {host, port, username, password, starttls}."""
        ...
