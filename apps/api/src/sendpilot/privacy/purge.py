"""Document retention purge (PRD §16.3).

Scheduled daily. Deletes the bytes of documents past their retention window and
marks them ``purged`` (metadata is kept for audit). Runs as a trusted system
session so it spans all tenants.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from ..db.models import Document
from ..db.session import system_session
from ..ingestion.storage import delete_object
from ..logging import get_logger

log = get_logger("privacy.purge")


async def purge_expired_documents(ctx: dict) -> int:
    now = datetime.now(UTC)
    async with system_session() as session:
        docs = (await session.scalars(
            select(Document).where(
                Document.retention_expires_at < now,
                Document.status != "purged",
            )
        )).all()
        for doc in docs:
            try:
                await delete_object(doc.storage_key)
            except Exception as exc:  # already gone / transient — still mark purged
                log.warning("purge.delete_failed", document_id=str(doc.id), error=str(exc))
            doc.status = "purged"
    log.info("purge.completed", count=len(docs))
    return len(docs)
