"""Unsubscribe token signing + CAN-SPAM footer injection (PRD §17.3)."""

from __future__ import annotations

import base64
import hashlib
import hmac

from ..config import settings


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sig(payload: bytes) -> str:
    return hmac.new(settings.session_secret.encode(), payload, hashlib.sha256).hexdigest()[:16]


def sign_unsubscribe(org_id: str, email: str) -> str:
    payload = f"{org_id}:{email}".encode()
    return f"{_b64e(payload)}.{_sig(payload)}"


def verify_unsubscribe(token: str) -> tuple[str, str] | None:
    if "." not in token:
        return None
    try:
        payload_b64, sig = token.split(".", 1)
        payload = _b64d(payload_b64)
        if not hmac.compare_digest(sig, _sig(payload)):
            return None
        org_id, email = payload.decode().split(":", 1)
        return org_id, email
    except (ValueError, UnicodeDecodeError):
        return None


def add_unsubscribe_footer(body: str, org_id: str, recipient_email: str,
                           org_address: str | None, body_format: str = "html") -> str:
    token = sign_unsubscribe(org_id, recipient_email)
    base = settings.public_base_url or settings.web_base_url
    url = f"{base}/u/{token}"
    if body_format == "html":
        footer = (
            '<hr><p style="font-size:12px;color:#888">'
            f"{org_address or ''}<br>"
            f'<a href="{url}">Unsubscribe</a></p>'
        )
    else:  # plain-text body — don't inject raw HTML tags
        footer = f"\n\n--\n{(org_address + chr(10)) if org_address else ''}Unsubscribe: {url}"
    return body + footer
