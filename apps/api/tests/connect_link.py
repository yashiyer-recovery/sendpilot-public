"""Print a Google consent URL for connecting another inbox with its OWN OAuth app.

Stores the per-account client creds in the OAuth state (scoped to the existing
org) and prints the auth URL. Open it, sign in as the target email, consent.

    docker compose exec -e GC_CLIENT_ID=... -e GC_CLIENT_SECRET=... api \
        python tests/connect_link.py
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace

from sqlalchemy import select

from sendpilot.cache import put_oauth_state
from sendpilot.connection.oauth import build_auth_url, make_pkce, new_state
from sendpilot.connection.providers import google_config
from sendpilot.db.models import AppUser, ConnectedAccount
from sendpilot.db.session import system_session

CLIENT_ID = os.environ["GC_CLIENT_ID"]
CLIENT_SECRET = os.environ["GC_CLIENT_SECRET"]
ORG_VIA = os.environ.get("ORG_VIA", "yash@zorbeai.com")  # locate the org via an existing account


async def main() -> None:
    async with system_session() as s:
        acct = await s.scalar(
            select(ConnectedAccount).where(ConnectedAccount.account_email == ORG_VIA)
        )
        org_id = str(acct.org_id)
        user = await s.scalar(select(AppUser).where(AppUser.org_id == acct.org_id))
        user_id = str(user.id)

    verifier, challenge = make_pkce()
    state = new_state()
    await put_oauth_state(state, {
        "provider": "gmail", "code_verifier": verifier,
        "org_id": org_id, "user_id": user_id,
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
    })
    cfg = replace(google_config(), client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    print(build_auth_url(cfg, state, challenge))


if __name__ == "__main__":
    asyncio.run(main())
