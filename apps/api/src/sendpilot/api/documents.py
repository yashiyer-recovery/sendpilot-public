"""Document upload + status routes (PRD §7, §10, §25)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..db.models import Document
from ..db.session import org_session
from ..deps import current_principal, get_db
from ..ingestion.upload import handle_upload
from ..queue import enqueue
from .errors import AppError
from .schemas import DocumentOut, UploadResponse

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("", response_model=UploadResponse)
async def upload(
    file: UploadFile,
    principal: Principal = Depends(current_principal),
) -> UploadResponse:
    data = await file.read()
    # Explicit transaction so we commit BEFORE enqueuing the AV job (otherwise the
    # worker, in its own transaction, wouldn't see the row yet).
    async with org_session(principal.org_id) as session:
        doc = await handle_upload(
            session, principal.org_id, principal.user_id, file.filename or "upload", data
        )
        doc_id = str(doc.id)

    await enqueue("av_scan", principal.org_id, doc_id)
    return UploadResponse(document_id=doc_id, status="scanning")


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> DocumentOut:
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise AppError("not_found", "document not found")
    return DocumentOut(
        id=str(doc.id), status=doc.status, filename=doc.filename,
        mime_type=doc.mime_type, size_bytes=doc.size_bytes,
    )
