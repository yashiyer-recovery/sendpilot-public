"""PKCE S256 challenge derivation (PRD §6.1)."""

from __future__ import annotations

import base64
import hashlib

from sendpilot.connection.oauth import build_auth_url, make_pkce, new_state
from sendpilot.connection.providers import ProviderConfig


def test_pkce_s256():
    verifier, challenge = make_pkce()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    assert challenge == expected


def test_states_unique():
    assert new_state() != new_state()


def test_auth_url_has_required_params():
    cfg = ProviderConfig(
        name="gmail", auth_url="https://x/auth", token_url="https://x/token",
        userinfo_url="https://x/info", scopes=["openid", "email"],
        client_id="cid", client_secret="sec", redirect_uri="https://app/cb",
    )
    url = build_auth_url(cfg, "st", "ch")
    for needle in ["code_challenge=ch", "code_challenge_method=S256", "state=st",
                   "response_type=code", "access_type=offline"]:
        assert needle in url
