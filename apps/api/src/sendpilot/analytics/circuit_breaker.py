"""Quality circuit breaker (PRD §14).

Auto-pauses a campaign when its bounce or complaint rate crosses a threshold
(once it has enough volume to be meaningful), and audits the action.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import AuditLog, Campaign
from ..logging import get_logger
from .rollups import campaign_stats

log = get_logger("analytics.circuit_breaker")


async def check_circuit_breaker(session: AsyncSession, campaign_id: str) -> bool:
    stats = await campaign_stats(session, campaign_id)
    sent = stats["sent"]
    if sent < settings.circuit_breaker_min_sent:
        return False

    bounce_rate = stats["bounced"] / sent
    complaint_rate = stats["complaints"] / sent
    if bounce_rate > settings.bounce_rate_threshold or \
            complaint_rate > settings.complaint_rate_threshold:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is not None and campaign.status != "paused":
            campaign.status = "paused"
            session.add(AuditLog(
                org_id=campaign.org_id, actor="system", action="campaign.circuit_breaker",
                target=campaign_id,
                meta={"sent": sent, "bounced": stats["bounced"], "complaints": stats["complaints"]},
            ))
            log.warning("circuit_breaker.paused", campaign_id=campaign_id,
                        bounce_rate=round(bounce_rate, 4))
        return True
    return False
