"""Extraction orchestrator (PRD §8.6) — the arq worker task.

Routes by document shape: deterministic tabular path vs Claude narrative path,
normalizes, validates, and persists records + job stats. The CPU/IO-bound
extraction runs in a thread; DB work stays on the event loop under RLS.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from ..db.models import Document, EmailRecord as EmailRecordRow, ExtractionJob
from ..ingestion.extract_text import extract_document_text
from ..ingestion.storage import get_object
from ..logging import get_logger
from ..metrics import (
    extraction_confidence,
    extraction_latency_seconds,
    extraction_records_total,
)
from ..validation.validate import validate_records
from ..worker.context import task_session
from .classify import classify_shape
from .chunk import dedupe
from .narrative import extract_narrative_records
from .schema import EmailRecord
from .tabular import extract_tabular

log = get_logger("extraction.orchestrator")


def _extract_pipeline(
    data: bytes, mime: str, document_id: str
) -> tuple[str, str, list[EmailRecord], int, int]:
    """Pure, blocking pipeline — safe to run in a thread."""
    parsed = extract_document_text(data, mime)
    shape = classify_shape(parsed)
    tokens_in = tokens_out = 0
    records: list[EmailRecord] = []
    if shape == "tabular":
        path = "tabular"
        for frame in parsed.tables:
            records += extract_tabular(frame, document_id)
    else:
        path = "narrative"
        records, tokens_in, tokens_out = extract_narrative_records(parsed.text, document_id)
        if shape == "unknown":
            shape = "single_draft"
    return shape, path, dedupe(records), tokens_in, tokens_out


async def run_extraction(ctx: dict, org_id: str, job_id: str) -> None:
    async with task_session(org_id) as session:
        job = await session.get(ExtractionJob, job_id)
        if job is None:
            return
        doc = await session.get(Document, job.document_id)
        if doc is None:
            job.status = "failed"
            job.error = "document not found"
            return
        job.status = "running"
        storage_key, mime, doc_id = doc.storage_key, doc.mime_type, str(doc.id)

    try:
        data = await get_object(storage_key)
        t0 = time.perf_counter()
        shape, path, records, tokens_in, tokens_out = await asyncio.to_thread(
            _extract_pipeline, data, mime, doc_id
        )
        extraction_latency_seconds.labels(path=path).observe(time.perf_counter() - t0)

        async with task_session(org_id) as session:
            records = await validate_records(session, records)
            for r in records:
                session.add(
                    EmailRecordRow(
                        org_id=org_id,
                        extraction_job_id=job_id,
                        recipient_email=r.recipient_email or None,
                        recipient_name=r.recipient_name,
                        cc=r.cc,
                        bcc=r.bcc,
                        subject=r.subject,
                        body=r.body,
                        body_format=r.body_format,
                        merge_fields=r.merge_fields,
                        source_ref=r.source_ref,
                        confidence=r.confidence,
                        validation_status=r.validation_status,
                        review_status="pending",
                    )
                )
                extraction_confidence.observe(r.confidence)
            job = await session.get(ExtractionJob, job_id)
            job.status = "completed"
            job.shape = shape
            job.record_count = len(records)
            job.needs_review_count = sum(1 for r in records if r.validation_status != "valid")
            job.tokens_in = tokens_in
            job.tokens_out = tokens_out
            job.completed_at = datetime.now(UTC)

        extraction_records_total.labels(shape=shape).inc(len(records))
        log.info("extraction.completed", job_id=job_id, shape=shape, count=len(records))
    except Exception as exc:
        async with task_session(org_id) as session:
            job = await session.get(ExtractionJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:500]
        log.exception("extraction.failed", job_id=job_id)
        raise
