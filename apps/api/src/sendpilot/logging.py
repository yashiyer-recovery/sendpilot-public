"""Structured JSON logging with PII/secret redaction.

Recipient addresses, email bodies, and tokens must NEVER reach the logs
(PRD §16, §20). Redaction is enforced centrally as a structlog processor so
no call site can leak. ``tests/unit/test_redaction.py`` asserts this holds.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog

from .config import settings

# Keys whose values are always dropped.
_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "tokens",
    "enc_tokens",
    "authorization",
    "client_secret",
    "password",
    "kms_master_key",
    "session_secret",
    "code_verifier",
}
# Keys whose values are PII and must be masked, not shown.
_PII_KEYS = {"recipient_email", "to", "email", "body", "subject", "recipient_name"}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_REDACTED = "[REDACTED]"


def _mask_email(value: str) -> str:
    # Keep enough to debug ("j***@acme.com") without storing the address.
    def repl(m: re.Match[str]) -> str:
        local, _, domain = m.group(0).partition("@")
        head = local[0] if local else ""
        return f"{head}***@{domain}"

    return _EMAIL_RE.sub(repl, value)


def redact_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        lkey = key.lower()
        if lkey in _SECRET_KEYS:
            event_dict[key] = _REDACTED
        elif lkey in _PII_KEYS and isinstance(event_dict[key], str):
            event_dict[key] = _mask_email(event_dict[key]) if "@" in event_dict[key] else _REDACTED
    # Also scrub any stray emails in the free-text event message.
    msg = event_dict.get("event")
    if isinstance(msg, str) and "@" in msg:
        event_dict["event"] = _mask_email(msg)
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
