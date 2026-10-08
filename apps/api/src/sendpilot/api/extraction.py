"""Extraction trigger + job status + paginated record listing (PRD §10, §25)."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..db.models import Document, EmailRecord, ExtractionJob
from ..db.session import org_session
from ..deps import current_principal, get_db
from ..queue import enqueue
from .errors import AppError
from .schemas import (
    ExtractionJobListItem,
    ExtractionJobOut,
    ExtractionStartResponse,
    RecordOut,
    RecordsPage,
)

router = APIRouter(prefix="/v1", tags=["extraction"])


def _encode_cursor(rec: EmailRecord) -> str:
    raw = f"{rec.created_at.isoformat()}|{rec.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    raw = base64.urlsafe_b64decode(cursor).decode()
    ts, rid = raw.split("|", 1)
    return ts, rid


def _to_out(r: EmailRecord) -> RecordOut:
    return RecordOut(
        id=str(r.id), recipient_email=r.recipient_email, recipient_name=r.recipient_name,
        subject=r.subject, body=r.body, body_format=r.body_format, confidence=r.confidence,
        validation_status=r.validation_status, review_status=r.review_status,
        source_ref=r.source_ref,
    )


@router.post("/documents/{doc_id}/extractions", response_model=ExtractionStartResponse)
async def start_extraction(
    doc_id: str, principal: Principal = Depends(current_principal)
) -> ExtractionStartResponse:
    async with org_session(principal.org_id) as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise AppError("not_found", "document not found")
        if doc.status != "ready":
            raise AppError("invalid_state", f"document not ready (status={doc.status})")
        job = ExtractionJob(org_id=principal.org_id, document_id=doc.id, status="queued")
        session.add(job)
        await session.flush()
        job_id = str(job.id)

    await enqueue("run_extraction", principal.org_id, job_id)
    return ExtractionStartResponse(extraction_job_id=job_id, status="queued")


@router.get("/extractions", response_model=list[ExtractionJobListItem])
async def list_extractions(
    db: AsyncSession = Depends(get_db), _: Principal = Depends(current_principal)
) -> list[ExtractionJobListItem]:
    rows = (await db.execute(
        select(ExtractionJob, Document.filename)
        .join(Document, Document.id == ExtractionJob.document_id)
        .order_by(ExtractionJob.created_at.desc())
        .limit(50)
    )).all()
    return [
        ExtractionJobListItem(
            id=str(j.id), filename=fn, status=j.status, shape=j.shape,
            record_count=j.record_count, needs_review_count=j.needs_review_count,
            created_at=j.created_at.isoformat(),
        )
        for j, fn in rows
    ]


@router.get("/extractions/{job_id}", response_model=ExtractionJobOut)
async def get_extraction(
    job_id: str, db: AsyncSession = Depends(get_db), _: Principal = Depends(current_principal)
) -> ExtractionJobOut:
    job = await db.get(ExtractionJob, job_id)
    if job is None:
        raise AppError("not_found", "extraction job not found")
    return ExtractionJobOut(
        id=str(job.id), status=job.status, shape=job.shape,
        record_count=job.record_count, needs_review_count=job.needs_review_count,
    )


@router.get("/extractions/{job_id}/records", response_model=RecordsPage)
async def list_records(
    job_id: str,
    status: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> RecordsPage:
    limit = max(1, min(limit, 200))
    q = select(EmailRecord).where(EmailRecord.extraction_job_id == job_id)
    if status:
        q = q.where(EmailRecord.validation_status == status)
    if cursor:
        ts, rid = _decode_cursor(cursor)
        q = q.where(tuple_(EmailRecord.created_at, EmailRecord.id) > (ts, rid))
    q = q.order_by(EmailRecord.created_at, EmailRecord.id).limit(limit + 1)

    rows = (await db.scalars(q)).all()
    next_cursor = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return RecordsPage(records=[_to_out(r) for r in rows[:limit]], next_cursor=next_cursor)
