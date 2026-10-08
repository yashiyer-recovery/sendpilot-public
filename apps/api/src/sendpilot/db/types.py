"""Reusable column types and helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, func, text
from sqlalchemy.dialects.postgresql import CITEXT, ENUM, UUID
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeEngine

from .enums import PG_ENUMS

_ENUM_BY_NAME = {name: enum for name, enum in PG_ENUMS}


def pg_enum(name: str) -> ENUM:
    """Reference a pre-existing PG ENUM type (created in migration 0001).

    The allowed values are passed so SQLAlchemy can bind/validate them; the type
    itself is NOT (re-)created (``create_type=False``).
    """
    py_enum = _ENUM_BY_NAME[name]
    return ENUM(*[member.value for member in py_enum], name=name, create_type=False)


def uuid_pk():
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


def fk_uuid(**kw):
    return mapped_column(UUID(as_uuid=True), **kw)


def created_at_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def citext() -> TypeEngine:
    return CITEXT()


# Re-exported so models import a single place.
__all__ = [
    "CITEXT",
    "ENUM",
    "UUID",
    "Enum",
    "citext",
    "created_at_col",
    "datetime",
    "fk_uuid",
    "pg_enum",
    "uuid",
    "uuid_pk",
]
