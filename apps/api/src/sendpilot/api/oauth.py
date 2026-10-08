"""Connection (OAuth) routes (PRD §6, §10, §25)."""

from __future__ import annotations

import time
from dataclasses import replace

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..cache import pop_oauth_state, put_oauth_state
from ..config import settings
from ..connection.oauth import build_auth_url, exchange_code, fetch_userinfo, make_pkce, new_state
from ..connection.providers import google_config, microsoft_config
from ..crypto.envelope import encrypt_tokens
from ..crypto.kms import get_kms
from ..db.models import AuditLog, ConnectedAccount
from ..db.session import org_session
from ..deps import current_principal, get_db, require_role
from .errors import AppError
from .schemas import AuthStartResponse, ConnectionOut, GoogleStartRequest, SmtpConnectRequest

router = APIRouter(prefix="/v1/connections", tags=["connections"])


async def _start(provider: str, cfg, principal: Principal,
                 client_id: str | None = None, client_secret: str | None = None) -> AuthStartResponse:
    verifier, challenge = make_pkce()
    state = new_state()
    state_data = {
        "provider": provider, "code_verifier": verifier,
        "org_id": principal.org_id, "user_id": principal.user_id,
    }
    if client_id:  # per-account OAuth client — remember it for callback + refresh
        state_data["client_id"] = client_id
        state_data["client_secret"] = client_secret or ""
    await put_oauth_state(state, state_data)
    return AuthStartResponse(auth_url=build_auth_url(cfg, state, challenge))


def _cfg_from_state(provider: str, saved: dict):
    """Rebuild the provider config, honoring a per-account OAuth client if set."""
    if provider == "gmail":
        cid = saved.get("client_id")
        if cid:
            return replace(google_config(), client_id=cid,
                           client_secret=saved.get("client_secret") or "")
        return google_config()
    if provider == "microsoft":
        return microsoft_config()
    raise AppError("invalid_state", f"unsupported provider: {provider}")


async def _complete(provider: str, code: str, state: str) -> RedirectResponse:
    saved = await pop_oauth_state(state)
    if not saved:
        raise AppError("invalid_state", "invalid or expired OAuth state")
    cfg = _cfg_from_state(provider, saved)

    tok = await exchange_code(cfg, code, saved["code_verifier"])
    email = tok.get("email")
    if not email:
        info = await fetch_userinfo(cfg, tok["access_token"])
        # Google -> email; Microsoft Graph -> mail / userPrincipalName.
        email = info.get("email") or info.get("mail") or info.get("userPrincipalName")
    if not email:
        raise AppError("invalid_state", "could not determine connected account email")

    tokens = {
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token", ""),
        "expires_at": time.time() + int(tok.get("expires_in", 3600)),
    }
    if saved.get("client_id"):  # store per-account client so refresh uses it
        tokens["client_id"] = saved["client_id"]
        tokens["client_secret"] = saved.get("client_secret") or ""
    enc = encrypt_tokens(get_kms(), settings.kms_key_id, tokens)
    scopes = tok["scope"].split() if tok.get("scope") else list(cfg.scopes)

    async with org_session(saved["org_id"]) as session:
        existing = await session.scalar(
            select(ConnectedAccount).where(
                ConnectedAccount.provider == provider,
                ConnectedAccount.account_email == email,
            )
        )
        if existing:
            existing.enc_tokens, existing.enc_key_id = enc, settings.kms_key_id
            existing.scopes, existing.status = scopes, "active"
            account_id = existing.id
        else:
            acct = ConnectedAccount(
                org_id=saved["org_id"], provider=provider, account_email=email,
                scopes=scopes, enc_tokens=enc, enc_key_id=settings.kms_key_id, status="active",
            )
            session.add(acct)
            await session.flush()
            account_id = acct.id
        session.add(AuditLog(
            org_id=saved["org_id"], actor=saved["user_id"], action="connection.created",
            target=str(account_id), meta={"provider": provider},
        ))

    return RedirectResponse(url=f"{settings.web_base_url}/connections?connected=1")


@router.post("/google/start", response_model=AuthStartResponse)
async def google_start(
    body: GoogleStartRequest | None = None,
    principal: Principal = Depends(current_principal),
) -> AuthStartResponse:
    if body and body.client_id:
        cfg = replace(google_config(), client_id=body.client_id,
                      client_secret=body.client_secret or "")
        return await _start("gmail", cfg, principal, body.client_id, body.client_secret)
    return await _start("gmail", google_config(), principal)


@router.get("/google/callback")
async def google_callback(code: str, state: str) -> RedirectResponse:
    return await _complete("gmail", code, state)


@router.post("/microsoft/start", response_model=AuthStartResponse)
async def microsoft_start(principal: Principal = Depends(current_principal)) -> AuthStartResponse:
    return await _start("microsoft", microsoft_config(), principal)


@router.get("/microsoft/callback")
async def microsoft_callback(code: str, state: str) -> RedirectResponse:
    return await _complete("microsoft", code, state)


@router.post("/smtp", response_model=ConnectionOut)
async def connect_smtp(
    body: SmtpConnectRequest, principal: Principal = Depends(current_principal)
) -> ConnectionOut:
    # SMTP config is stored in the same envelope-encrypted token vault as OAuth
    # tokens — the password never touches the DB in plaintext.
    cfg = {
        "host": body.host, "port": body.port,
        "username": body.username or "", "password": body.password or "",
        "starttls": body.starttls,
    }
    enc = encrypt_tokens(get_kms(), settings.kms_key_id, cfg)
    async with org_session(principal.org_id) as session:
        existing = await session.scalar(
            select(ConnectedAccount).where(
                ConnectedAccount.provider == "smtp",
                ConnectedAccount.account_email == str(body.account_email),
            )
        )
        if existing:
            existing.enc_tokens, existing.enc_key_id = enc, settings.kms_key_id
            existing.status = "active"
            account_id = existing.id
        else:
            acct = ConnectedAccount(
                org_id=principal.org_id, provider="smtp",
                account_email=str(body.account_email), enc_tokens=enc,
                enc_key_id=settings.kms_key_id, status="active",
            )
            session.add(acct)
            await session.flush()
            account_id = acct.id
        session.add(AuditLog(
            org_id=principal.org_id, actor=principal.user_id, action="connection.created",
            target=str(account_id), meta={"provider": "smtp"},
        ))
        out = ConnectionOut(id=str(account_id), provider="smtp",
                            account_email=str(body.account_email), status="active")
    return out


@router.get("", response_model=list[ConnectionOut])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> list[ConnectionOut]:
    rows = (await db.scalars(
        select(ConnectedAccount).order_by(ConnectedAccount.created_at)
    )).all()
    return [
        ConnectionOut(id=str(r.id), provider=r.provider, account_email=r.account_email,
                      status=r.status)
        for r in rows
    ]


@router.delete("/{conn_id}")
async def delete_connection(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role("admin")),
) -> dict:
    acct = await db.get(ConnectedAccount, conn_id)
    if acct is None:
        raise AppError("not_found", "connection not found")
    await db.delete(acct)
    return {"deleted": True}
