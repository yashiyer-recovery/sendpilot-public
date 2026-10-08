"""Async engine + RLS-aware session factories.

Two entry points, and a query must never run outside one of them:

* :func:`org_session` — scopes the transaction to one tenant (HTTP requests,
  worker tasks). RLS enforced.
* :func:`system_session` — trusted cross-tenant access for bootstrap/system
  code only (signup, login lookup, cron).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..config import settings
from .rls import set_org_guc, set_system_guc

# Tests run each case on its own event loop; NullPool avoids reusing a pooled
# connection bound to a closed loop. Production uses the default pool.
_engine_kwargs: dict = {"echo": settings.db_echo, "pool_pre_ping": True}
if settings.env == "test":
    _engine_kwargs = {"echo": settings.db_echo, "poolclass": NullPool}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def org_session(org_id: str | uuid.UUID) -> AsyncIterator[AsyncSession]:
    """One transaction, scoped to ``org_id`` via RLS. Commits on clean exit."""
    async with SessionLocal() as session, session.begin():
        await set_org_guc(session, org_id)
        yield session


@asynccontextmanager
async def system_session() -> AsyncIterator[AsyncSession]:
    """Trusted cross-tenant transaction. Use sparingly, never with user input."""
    async with SessionLocal() as session, session.begin():
        await set_system_guc(session)
        yield session
