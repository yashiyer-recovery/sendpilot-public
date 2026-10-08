"""Minimal HMAC-signed session tokens + RBAC principal.

The PRD assumes a session-cookie auth surface but doesn't specify an IdP; this
is a small, real, dependency-free implementation good enough for v1 (swap for
an IdP/OIDC later). The browser never holds a scoped API token — only this
signed session cookie identifying ``{org_id, user_id, role}``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from .config import settings

SESSION_COOKIE = "sp_session"
SESSION_TTL = 86_400  # 24h


@dataclass(frozen=True)
class Principal:
    org_id: str
    user_id: str
    role: str  # owner | admin | member


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sig(payload: bytes) -> bytes:
    return hmac.new(settings.session_secret.encode(), payload, hashlib.sha256).digest()


def issue_session(p: Principal, ttl: int = SESSION_TTL) -> str:
    body = json.dumps(
        {"org_id": p.org_id, "user_id": p.user_id, "role": p.role, "exp": int(time.time()) + ttl}
    ).encode()
    return f"{_b64e(body)}.{_b64e(_sig(body))}"


def verify_session(token: str | None) -> Principal | None:
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64d(payload_b64)
        if not hmac.compare_digest(_b64d(sig_b64), _sig(payload)):
            return None
        body = json.loads(payload)
        if int(body["exp"]) < time.time():
            return None
        return Principal(body["org_id"], body["user_id"], body["role"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


# Role ordering for RBAC checks (owner ⊇ admin ⊇ member).
_RANK = {"member": 0, "admin": 1, "owner": 2}


def has_role(principal: Principal, minimum: str) -> bool:
    return _RANK.get(principal.role, -1) >= _RANK.get(minimum, 99)
