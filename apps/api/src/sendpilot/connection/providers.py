"""OAuth provider configuration (PRD §6.1).

Send-only scopes by default; read scope is only requested when reply tracking is
enabled (M2). With ``MOCK_PROVIDER=true`` the auth/token/userinfo URLs point at
the local mock-provider so the flow works without real Google credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import settings

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


@dataclass(frozen=True)
class ProviderConfig:
    name: str  # provider_t value
    auth_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    client_id: str
    client_secret: str
    redirect_uri: str


def google_config() -> ProviderConfig:
    userinfo = (
        f"{settings.mock_provider_url}/mock/google/userinfo"
        if settings.mock_provider
        else "https://www.googleapis.com/oauth2/v3/userinfo"
    )
    return ProviderConfig(
        name="gmail",
        auth_url=settings.google_auth_url,
        token_url=settings.google_token_url,
        userinfo_url=userinfo,
        # openid+email let us identify the connected account; gmail.send to send.
        scopes=["openid", "email", GMAIL_SEND_SCOPE],
        client_id=settings.google_client_id or "mock-client-id",
        client_secret=settings.google_client_secret or "mock-client-secret",
        redirect_uri=settings.google_redirect_uri,
    )


def microsoft_config() -> ProviderConfig:
    userinfo = (
        f"{settings.mock_provider_url}/mock/ms/userinfo"
        if settings.mock_provider
        else "https://graph.microsoft.com/v1.0/me"
    )
    return ProviderConfig(
        name="microsoft",
        auth_url=settings.ms_auth_url,
        token_url=settings.ms_token_url,
        userinfo_url=userinfo,
        scopes=["openid", "email", "offline_access", "Mail.Send"],
        client_id=settings.ms_client_id or "mock-client-id",
        client_secret=settings.ms_client_secret or "mock-client-secret",
        redirect_uri=settings.ms_redirect_uri,
    )


def config_for(provider: str) -> ProviderConfig:
    if provider == "gmail":
        return google_config()
    if provider == "microsoft":
        return microsoft_config()
    raise ValueError(f"unsupported provider: {provider}")
