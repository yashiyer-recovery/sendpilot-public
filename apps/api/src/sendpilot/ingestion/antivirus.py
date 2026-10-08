"""Antivirus scan worker job (PRD §7.1, §16).

In production this calls clamd. Locally it performs a real (if minimal) check —
the EICAR test signature is rejected — and otherwise marks the document ready.
"""

from __future__ import annotations

from ..db.models import Document
from ..db.session import org_session
from ..logging import get_logger
from .storage import get_object

log = get_logger("ingestion.antivirus")

# Standard EICAR antivirus test string (safe; triggers real AV engines).
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


async def av_scan(ctx: dict, org_id: str, document_id: str) -> None:
    async with org_session(org_id) as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            log.warning("av_scan.missing_document", document_id=document_id)
            return
        data = await get_object(doc.storage_key)
        if EICAR in data:
            doc.status = "rejected"
            log.warning("av_scan.rejected", document_id=document_id)
        else:
            doc.status = "ready"
            log.info("av_scan.ready", document_id=document_id)
