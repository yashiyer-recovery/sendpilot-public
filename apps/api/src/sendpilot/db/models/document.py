"""Documents, extraction jobs, and the canonical email records (PRD §5.2, §7-9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..types import created_at_col, pg_enum, uuid_pk


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(pg_enum("doc_status_t"), nullable=False,
                                        server_default="uploaded")
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()


class ExtractionJob(Base):
    __tablename__ = "extraction_job"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(pg_enum("job_status_t"), nullable=False,
                                        server_default="queued")
    shape: Mapped[str] = mapped_column(pg_enum("doc_shape_t"), nullable=False,
                                       server_default="unknown")
    model: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    needs_review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailRecord(Base):
    __tablename__ = "email_record"
    __table_args__ = (
        Index("ix_record_job", "extraction_job_id"),
        Index("ix_record_review", "org_id", "review_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    extraction_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_job.id", ondelete="CASCADE"), nullable=False
    )
    recipient_email: Mapped[str | None] = mapped_column(CITEXT)
    recipient_name: Mapped[str | None] = mapped_column(Text)
    cc: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    bcc: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    body_format: Mapped[str] = mapped_column(Text, nullable=False, server_default="html")
    merge_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    source_ref: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    validation_status: Mapped[str] = mapped_column(pg_enum("validation_t"), nullable=False,
                                                   server_default="needs_review")
    review_status: Mapped[str] = mapped_column(pg_enum("review_t"), nullable=False,
                                              server_default="pending")
    created_at: Mapped[datetime] = created_at_col()
