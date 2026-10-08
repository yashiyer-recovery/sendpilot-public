"""FastAPI dependency providers: auth principal, RBAC, org-scoped DB session."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .api.errors import AppError
from .auth import SESSION_COOKIE, Principal, has_role, verify_session
from .db.session import org_session


def current_principal(request: Request) -> Principal:
    principal = verify_session(request.cookies.get(SESSION_COOKIE))
    if principal is None:
        raise AppError("unauthorized", "authentication required")
    return principal


def require_role(minimum: str) -> Callable[..., Principal]:
    """Dependency factory enforcing a minimum role (owner ⊇ admin ⊇ member)."""

    def _dep(principal: Principal = Depends(current_principal)) -> Principal:
        if not has_role(principal, minimum):
            raise AppError("forbidden", f"requires '{minimum}' role")
        return principal

    return _dep


async def get_db(
    principal: Principal = Depends(current_principal),
) -> AsyncIterator[AsyncSession]:
    """An RLS-scoped session+transaction for the principal's org."""
    async with org_session(principal.org_id) as session:
        yield session
