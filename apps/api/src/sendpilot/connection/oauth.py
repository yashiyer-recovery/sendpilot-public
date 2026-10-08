"""OAuth 2.0 authorization-code + PKCE — provider-agnostic core (PRD §6.3).

HTTP routing lives in ``api/oauth.py``; this module is the pure logic so it can
be unit-tested against the mock provider.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import httpx

from .providers import ProviderConfig


def make_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for the S256 method."""
    verifier = base64.urlsafe_b64encode(os.urandom(40)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def new_state() -> str:
    return secrets.token_urlsafe(24)


def build_auth_url(cfg: ProviderConfig, state: str, challenge: str) -> str:
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": " ".join(cfg.scopes),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": "offline",  # request a refresh token
        "prompt": "consent",
    }
    return f"{cfg.auth_url}?{urlencode(params)}"


async def exchange_code(cfg: ProviderConfig, code: str, verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            cfg.token_url,
            data={
                "code": code,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "redirect_uri": cfg.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_userinfo(cfg: ProviderConfig, access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            cfg.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()
