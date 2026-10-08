"""Templates, campaigns, sequence steps, messages, events (PRD §5.2, §11-13)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..types import created_at_col, pg_enum, uuid_pk


class Template(Base):
    __tablename__ = "template"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_format: Mapped[str] = mapped_column(Text, nullable=False, server_default="html")
    created_at: Mapped[datetime] = created_at_col()


class Campaign(Base):
    __tablename__ = "campaign"

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    connected_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connected_account.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(pg_enum("campaign_type_t"), nullable=False,
                                      server_default="one_off")
    status: Mapped[str] = mapped_column(pg_enum("campaign_status_t"), nullable=False,
                                        server_default="draft")
    # Approved email_record ids this campaign sends (added in migration 0003).
    record_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False
    )
    created_at: Mapped[datetime] = created_at_col()


class SequenceStep(Base):
    __tablename__ = "sequence_step"
    __table_args__ = (UniqueConstraint("campaign_id", "step_index"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template.id")
    )
    stop_on_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        # The double-send guard (PRD §11.7).
        UniqueConstraint("idempotency_key", name="uq_message_idempotency_key"),
        Index("ix_message_status", "org_id", "status"),
        Index("ix_message_thread", "connected_account_id", "thread_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaign.id", ondelete="CASCADE"), nullable=False
    )
    email_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_record.id"), nullable=False
    )
    connected_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connected_account.id"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    thread_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(pg_enum("message_status_t"), nullable=False,
                                        server_default="queued")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (Index("ix_event_msg", "message_id", "type"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(pg_enum("event_t"), nullable=False)
    # 'metadata' is reserved on Base; map the column explicitly to attribute 'meta'.
    meta: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
