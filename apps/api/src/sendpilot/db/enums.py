"""Python enums mirroring the PostgreSQL ENUM types (PRD §5.2).

The PG types themselves are created in migration 0001. Model columns reference
them with ``create_type=False`` so SQLAlchemy never tries to re-create them.
"""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
    gmail = "gmail"
    microsoft = "microsoft"
    smtp = "smtp"


class AccountStatus(StrEnum):
    active = "active"
    paused = "paused"
    revoked = "revoked"
    error = "error"


class DocStatus(StrEnum):
    uploaded = "uploaded"
    scanning = "scanning"
    ready = "ready"
    rejected = "rejected"
    purged = "purged"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class DocShape(StrEnum):
    tabular = "tabular"
    repeated_blocks = "repeated_blocks"
    single_draft = "single_draft"
    unknown = "unknown"


class ValidationStatus(StrEnum):
    valid = "valid"
    needs_review = "needs_review"
    invalid = "invalid"
    suppressed = "suppressed"
    duplicate = "duplicate"


class ReviewStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CampaignType(StrEnum):
    one_off = "one_off"
    sequence = "sequence"


class CampaignStatus(StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    running = "running"
    paused = "paused"
    completed = "completed"


class MessageStatus(StrEnum):
    queued = "queued"  # claimed but not yet handed to a provider
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    bounced = "bounced"
    failed = "failed"
    skipped = "skipped"


class EventType(StrEnum):
    open = "open"
    click = "click"
    reply = "reply"
    bounce = "bounce"
    complaint = "complaint"
    unsubscribe = "unsubscribe"
    delivered = "delivered"


class SuppressionReason(StrEnum):
    unsubscribe = "unsubscribe"
    hard_bounce = "hard_bounce"
    complaint = "complaint"
    manual = "manual"


class Role(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


# (pg_type_name, python_enum) — consumed by migration 0001 to create the types.
PG_ENUMS: list[tuple[str, type[StrEnum]]] = [
    ("provider_t", Provider),
    ("account_status_t", AccountStatus),
    ("doc_status_t", DocStatus),
    ("job_status_t", JobStatus),
    ("doc_shape_t", DocShape),
    ("validation_t", ValidationStatus),
    ("review_t", ReviewStatus),
    ("campaign_type_t", CampaignType),
    ("campaign_status_t", CampaignStatus),
    ("message_status_t", MessageStatus),
    ("event_t", EventType),
    ("suppression_t", SuppressionReason),
]
