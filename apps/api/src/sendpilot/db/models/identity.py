"""Tenant root + users (PRD §5.2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base
from ..types import created_at_col, uuid_pk


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="free")
    # Required in the CAN-SPAM unsubscribe footer (PRD §17).
    physical_address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    users: Mapped[list[AppUser]] = relationship(back_populates="org")


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("org_id", "email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="member")
    created_at: Mapped[datetime] = created_at_col()

    org: Mapped[Organization] = relationship(back_populates="users")
