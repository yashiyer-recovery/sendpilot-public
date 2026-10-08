"""Row-level-security session GUCs (PRD §5.3) — the keystone of tenant isolation.

Every tenant-scoped table has an RLS policy of the form::

    USING (org_id = current_setting('app.current_org')::uuid
           OR current_setting('app.system', true) = 'on')

``app.current_org`` is set per-transaction with ``set_config(..., is_local=true)``
so it can NEVER leak across asyncpg pool checkouts. The ``app.system`` escape
hatch is used ONLY by trusted bootstrap/system code (signup, login lookup,
cron jobs) — never derived from user input.

The application DB role MUST be non-superuser and NOT ``BYPASSRLS`` or these
policies are silently ignored.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NIL_ORG = "00000000-0000-0000-0000-000000000000"


async def set_org_guc(session: AsyncSession, org_id: str | uuid.UUID) -> None:
    """Scope this transaction to a single tenant."""
    await session.execute(
        text("SELECT set_config('app.current_org', :org, true)"),
        {"org": str(org_id)},
    )
    await session.execute(text("SELECT set_config('app.system', 'off', true)"))


async def set_system_guc(session: AsyncSession) -> None:
    """Trusted, cross-tenant access for bootstrap/system code only."""
    await session.execute(
        text("SELECT set_config('app.current_org', :org, true)"),
        {"org": NIL_ORG},
    )
    await session.execute(text("SELECT set_config('app.system', 'on', true)"))
