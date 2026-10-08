"""Review/approve routes (PRD §10). The send action is gated on approved records.

Editing a record re-runs validation for that row and resets it to pending.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import Principal
from ..db.models import EmailRecord
from ..deps import current_principal, get_db
from ..extraction.schema import EmailRecord as EmailRecordModel
from ..validation.validate import validate_records
from .errors import AppError
from .extraction import _to_out
from .schemas import BulkApprove, RecordOut

router = APIRouter(prefix="/v1", tags=["review"])


@router.patch("/records/{record_id}", response_model=RecordOut)
async def patch_record(
    record_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> RecordOut:
    rec = await db.get(EmailRecord, record_id)
    if rec is None:
        raise AppError("not_found", "record not found")
    if "subject" in body and body["subject"] is not None:
        rec.subject = body["subject"]
    if "body" in body and body["body"] is not None:
        rec.body = body["body"]
    if "recipient_email" in body and body["recipient_email"] is not None:
        rec.recipient_email = body["recipient_email"]

    # Editing re-runs validation for that row (PRD §10).
    pyrec = EmailRecordModel(
        recipient_email=rec.recipient_email or "", recipient_name=rec.recipient_name,
        subject=rec.subject or "", body=rec.body or "", body_format=rec.body_format,
        cc=rec.cc, bcc=rec.bcc, merge_fields=dict(rec.merge_fields), source_ref=rec.source_ref,
        confidence=rec.confidence,
    )
    await validate_records(db, [pyrec])
    rec.validation_status = pyrec.validation_status
    rec.recipient_email = pyrec.recipient_email or None
    rec.merge_fields = pyrec.merge_fields
    rec.review_status = "pending"  # re-approval required after an edit
    await db.flush()
    return _to_out(rec)


@router.post("/records/{record_id}/approve")
async def approve_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> dict:
    rec = await db.get(EmailRecord, record_id)
    if rec is None:
        raise AppError("not_found", "record not found")
    rec.review_status = "approved"
    return {"approved": True}


@router.post("/records:bulk_approve")
async def bulk_approve(
    body: BulkApprove,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> dict:
    if not body.record_ids:
        return {"approved": 0}
    result = await db.execute(
        update(EmailRecord)
        .where(EmailRecord.id.in_(body.record_ids))
        .values(review_status="approved")
    )
    return {"approved": result.rowcount}


@router.post("/extractions/{job_id}/approve_all")
async def approve_all(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(current_principal),
) -> dict:
    """Approve every record in an extraction job (server-side, beyond the page).

    Suppressed/invalid recipients are still skipped at send time (PRD §9, §11).
    """
    result = await db.execute(
        update(EmailRecord)
        .where(EmailRecord.extraction_job_id == job_id)
        .values(review_status="approved")
    )
    return {"approved": result.rowcount}
