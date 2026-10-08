"""Connected mailbox + encrypted token vault + sending profile (PRD §5.2, §6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..types import created_at_col, pg_enum, uuid_pk

DEFAULT_SEND_WINDOW = {"start": "08:00", "end": "18:00"}


class ConnectedAccount(Base):
    __tablename__ = "connected_account"
    __table_args__ = (UniqueConstraint("org_id", "provider", "account_email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(pg_enum("provider_t"), nullable=False)
    account_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")

    # Envelope-encrypted token blob: KMS-wrapped data key + AES-GCM ciphertext.
    enc_tokens: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enc_key_id: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(pg_enum("account_status_t"), nullable=False,
                                        server_default="active")
    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, server_default="200")
    rate_per_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    warmup_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    send_window: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default='{"start":"08:00","end":"18:00"}'
    )
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
