"""Access-token accessor with refresh + health (PRD §6.4).

Returns a valid access token, refreshing (and re-encrypting) when it is close to
expiry. On a revoked refresh token the account is marked ``revoked`` and a
``reauthorization_required`` error is raised so the caller can pause campaigns.
"""

from __future__ import annotations

import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import AppError
from ..crypto.envelope import decrypt_tokens, encrypt_tokens
from ..crypto.kms import get_kms
from ..db.models import ConnectedAccount
from .providers import config_for

REFRESH_SKEW = 120  # refresh when <2 min of validity remains


async def valid_access_token(session: AsyncSession, account: ConnectedAccount) -> str:
    kms = get_kms()
    tokens = decrypt_tokens(kms, account.enc_key_id, account.enc_tokens)

    if tokens.get("expires_at", 0) - time.time() > REFRESH_SKEW:
        return tokens["access_token"]

    cfg = config_for(account.provider)
    # Use this account's own OAuth client if one was stored at connect time.
    client_id = tokens.get("client_id") or cfg.client_id
    client_secret = tokens.get("client_secret") or cfg.client_secret
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            cfg.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )

    if resp.status_code == 400:
        account.status = "revoked"
        await session.flush()
        raise AppError("reauthorization_required", "mailbox reauthorization required")
    resp.raise_for_status()

    new = resp.json()
    tokens["access_token"] = new["access_token"]
    tokens["expires_at"] = time.time() + int(new.get("expires_in", 3600))
    if new.get("refresh_token"):
        tokens["refresh_token"] = new["refresh_token"]

    account.enc_tokens = encrypt_tokens(kms, account.enc_key_id, tokens)
    await session.flush()
    return tokens["access_token"]
