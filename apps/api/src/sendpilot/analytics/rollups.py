"""Campaign analytics rollups (PRD §14).

Message statuses and event counts are aggregated separately to avoid the
join fan-out that would over-count sends when a message has many events.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_MSG_SQL = text(
    """
    SELECT
      count(*) FILTER (WHERE status IN ('sent','delivered','bounced')) AS sent,
      count(*) FILTER (WHERE status = 'skipped') AS skipped,
      count(*) FILTER (WHERE status = 'failed')  AS failed
    FROM message WHERE campaign_id = :campaign_id
    """
)
_EVT_SQL = text(
    """
    SELECT e.type AS type, count(DISTINCT e.message_id) AS n
    FROM event e JOIN message m ON e.message_id = m.id
    WHERE m.campaign_id = :campaign_id
    GROUP BY e.type
    """
)

_EVENT_KEYS = {
    "delivered": "delivered", "bounce": "bounced", "open": "opened",
    "click": "clicked", "reply": "replied", "unsubscribe": "unsubscribed",
    "complaint": "complaints",
}


async def campaign_stats(session: AsyncSession, campaign_id: str) -> dict[str, int]:
    msg = (await session.execute(_MSG_SQL, {"campaign_id": campaign_id})).mappings().first()
    stats = {
        "sent": int(msg["sent"]), "skipped": int(msg["skipped"]), "failed": int(msg["failed"]),
        "delivered": 0, "bounced": 0, "opened": 0, "clicked": 0,
        "replied": 0, "unsubscribed": 0, "complaints": 0,
    }
    for row in (await session.execute(_EVT_SQL, {"campaign_id": campaign_id})).mappings():
        key = _EVENT_KEYS.get(row["type"])
        if key:
            stats[key] = int(row["n"])
    return stats
