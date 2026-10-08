"""Dev/bootstrap auth: signup, current principal, logout.

A minimal session surface so the rest of the flow has an org + user. Swap for a
real IdP later; the rest of the code only depends on :class:`Principal`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..auth import SESSION_COOKIE, Principal, issue_session
from ..db.models import AppUser, Organization
from ..db.session import system_session
from ..deps import current_principal
from .schemas import PrincipalOut, SignupRequest

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/signup", response_model=PrincipalOut)
async def signup(body: SignupRequest, response: Response) -> PrincipalOut:
    # Bootstrap runs as a trusted system session (no org context exists yet).
    async with system_session() as session:
        org = Organization(name=body.org_name)
        session.add(org)
        await session.flush()
        user = AppUser(org_id=org.id, email=body.email, role="owner")
        session.add(user)
        await session.flush()
        org_id, user_id = str(org.id), str(user.id)

    principal = Principal(org_id=org_id, user_id=user_id, role="owner")
    response.set_cookie(
        SESSION_COOKIE, issue_session(principal),
        httponly=True, samesite="lax", max_age=86_400,
    )
    return PrincipalOut(org_id=org_id, user_id=user_id, role="owner", email=str(body.email))


@router.get("/me", response_model=PrincipalOut)
async def me(principal: Principal = Depends(current_principal)) -> PrincipalOut:
    return PrincipalOut(org_id=principal.org_id, user_id=principal.user_id, role=principal.role)


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
