"""SendPilot mock email provider (local dev).

Stands in for Google's OAuth endpoints so the connect flow works with no real
Google credentials. M1 extends this with a /mock/gmail/send sandbox and a
webhook emitter for delivered/bounce events.
"""

from __future__ import annotations

import secrets

from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

app = FastAPI(title="SendPilot Mock Provider")

ACCOUNT_EMAIL = "demo@sendpilot.test"
MS_EMAIL = "demo@contoso.com"
SCOPE = "openid email https://www.googleapis.com/auth/gmail.send"
MS_SCOPE = "openid email offline_access Mail.Send"

_codes: dict[str, str] = {}     # code -> email
_tokens: dict[str, str] = {}    # access_token -> email
_sent: list[dict] = []          # sandbox of "sent" messages


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/mock/google/authorize")
def authorize(redirect_uri: str, state: str) -> RedirectResponse:
    code = "mc_" + secrets.token_urlsafe(16)
    _codes[code] = ACCOUNT_EMAIL
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}code={code}&state={state}")


@app.post("/mock/google/token")
def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    refresh_token: str | None = Form(None),
) -> JSONResponse:
    email = _codes.pop(code, ACCOUNT_EMAIL) if (grant_type == "authorization_code" and code) \
        else ACCOUNT_EMAIL
    access = "at_" + secrets.token_urlsafe(16)
    _tokens[access] = email
    body = {
        "access_token": access,
        "expires_in": 3600,
        "scope": SCOPE,
        "token_type": "Bearer",
        "email": email,
    }
    if grant_type == "authorization_code":
        body["refresh_token"] = "rt_" + secrets.token_urlsafe(16)
    return JSONResponse(body)


@app.get("/mock/google/userinfo")
def userinfo(request: Request) -> dict:
    access = request.headers.get("authorization", "").removeprefix("Bearer ")
    return {"sub": "mock-sub", "email": _tokens.get(access, ACCOUNT_EMAIL), "email_verified": True}


@app.post("/mock/gmail/send")
async def gmail_send(request: Request) -> dict:
    body = await request.json()
    mid = "m_" + secrets.token_urlsafe(8)
    tid = body.get("threadId") or ("t_" + secrets.token_urlsafe(8))
    _sent.append({"id": mid, "threadId": tid, "provider": "gmail"})
    return {"id": mid, "threadId": tid, "labelIds": ["SENT"]}


# ── Microsoft 365 (Graph) mock ──────────────────────────────────────────────
@app.get("/mock/ms/authorize")
def ms_authorize(redirect_uri: str, state: str) -> RedirectResponse:
    code = "mc_" + secrets.token_urlsafe(16)
    _codes[code] = MS_EMAIL
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{sep}code={code}&state={state}")


@app.post("/mock/ms/token")
def ms_token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    refresh_token: str | None = Form(None),
) -> JSONResponse:
    email = _codes.pop(code, MS_EMAIL) if (grant_type == "authorization_code" and code) \
        else MS_EMAIL
    access = "at_" + secrets.token_urlsafe(16)
    _tokens[access] = email
    body = {"access_token": access, "expires_in": 3600, "scope": MS_SCOPE,
            "token_type": "Bearer", "email": email}
    if grant_type == "authorization_code":
        body["refresh_token"] = "rt_" + secrets.token_urlsafe(16)
    return JSONResponse(body)


@app.get("/mock/ms/userinfo")
def ms_userinfo(request: Request) -> dict:
    access = request.headers.get("authorization", "").removeprefix("Bearer ")
    email = _tokens.get(access, MS_EMAIL)
    return {"id": "mock-ms-id", "mail": email, "userPrincipalName": email}


@app.post("/mock/ms/sendmail")
async def ms_sendmail(request: Request) -> dict:
    mid = "m_" + secrets.token_urlsafe(8)
    tid = "t_" + secrets.token_urlsafe(8)
    _sent.append({"id": mid, "threadId": tid, "provider": "microsoft"})
    return {"id": mid, "threadId": tid}


@app.get("/mock/sent")
def sent() -> dict:
    return {"count": len(_sent), "messages": _sent}
