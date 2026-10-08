"""Campaign analytics endpoint (PRD §14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..analytics.rollups import campaign_stats
from ..auth import Principal
from ..deps import current_principal, get_db

router = APIRouter(prefix="/v1", tags=["analytics"])


@router.get("/campaigns/{campaign_id}/analytics")
async def campaign_analytics(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> dict:
    return await campaign_stats(db, campaign_id)
