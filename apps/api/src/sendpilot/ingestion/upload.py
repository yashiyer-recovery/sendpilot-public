"""Upload handling (PRD §7.1).

Validates size and the *sniffed* MIME type (never the extension), computes a
SHA-256, stores the bytes, and creates a ``document`` row in ``scanning`` state.
The AV scan job is enqueued by the route after commit.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import magic
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import AppError
from ..config import settings
from ..db.models import Document

# Allowlist of sniffed MIME types (PRD §7.1). text/plain covers CSV/MD/TXT that
# libmagic often reports generically.
ALLOWED_MIME = {
    "text/csv",
    "text/plain",
    "text/html",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/pdf",
    "image/png",
    "image/jpeg",
    "message/rfc822",  # .eml — an email written out as a document
}


async def handle_upload(
    session: AsyncSession,
    org_id: str,
    user_id: str,
    filename: str,
    data: bytes,
) -> Document:
    if len(data) > settings.max_upload_bytes:
        raise AppError("file_too_large", "file exceeds the size limit")

    mime = magic.from_buffer(data, mime=True)
    if mime not in ALLOWED_MIME:
        raise AppError("unsupported_type", f"unsupported file type: {mime}")

    sha = hashlib.sha256(data).hexdigest()
    key = f"{org_id}/{sha}/{filename}"

    # Import here to avoid importing boto3 at module load for non-upload paths.
    from .storage import put_object

    await put_object(key, data, mime)

    doc = Document(
        org_id=org_id,
        uploaded_by=user_id,
        filename=filename,
        mime_type=mime,
        size_bytes=len(data),
        sha256=sha,
        storage_key=key,
        status="scanning",
        retention_expires_at=datetime.now(UTC) + timedelta(days=settings.doc_retention_days),
    )
    session.add(doc)
    await session.flush()
    return doc
