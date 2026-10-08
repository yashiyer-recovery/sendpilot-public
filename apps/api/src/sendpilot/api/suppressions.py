"""Suppression list + one-click unsubscribe (PRD §10, §17)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..compliance.suppression import add_suppression
from ..db.models import SuppressionEntry
from ..db.session import org_session
from ..deps import current_principal, get_db
from .schemas import SuppressionCreate, SuppressionOut

router = APIRouter(prefix="/v1", tags=["suppressions"])
public_router = APIRouter(tags=["unsubscribe"])  # no auth — the unsubscribe link


@router.post("/suppressions", response_model=SuppressionOut)
async def create_suppression(
    body: SuppressionCreate, principal: Principal = Depends(current_principal)
) -> SuppressionOut:
    async with org_session(principal.org_id) as session:
        await add_suppression(session, principal.org_id, str(body.email), body.reason)
    return SuppressionOut(email=str(body.email).lower(), reason=body.reason)


@router.get("/suppressions", response_model=list[SuppressionOut])
async def list_suppressions(
    db: AsyncSession = Depends(get_db), _: Principal = Depends(current_principal)
) -> list[SuppressionOut]:
    rows = (await db.scalars(select(SuppressionEntry))).all()
    return [SuppressionOut(email=s.email, reason=s.reason) for s in rows]


@public_router.get("/u/{token}", response_class=HTMLResponse)
async def unsubscribe(token: str) -> HTMLResponse:
    # Import here to avoid a cycle at module load.
    from ..compliance.unsubscribe import verify_unsubscribe

    parsed = verify_unsubscribe(token)
    if parsed is None:
        return HTMLResponse("<p>Invalid unsubscribe link.</p>", status_code=400)
    org_id, email = parsed
    async with org_session(org_id) as session:
        await add_suppression(session, org_id, email, "unsubscribe")
    return HTMLResponse(
        f"<p>{email} has been unsubscribed and will receive no further emails.</p>"
    )
