"""All ORM models. Importing this package populates ``Base.metadata``."""

from __future__ import annotations

from ..base import Base
from .campaign import Campaign, Event, Message, SequenceStep, Template
from .connection import ConnectedAccount
from .document import Document, EmailRecord, ExtractionJob
from .identity import AppUser, Organization
from .suppression import AuditLog, SuppressionEntry

# Tenant-scoped tables (carry org_id) — RLS policies are applied to exactly these
# in migration 0002. ``organization`` is the tenant root and gets its own policy.
TENANT_TABLES: list[str] = [
    "app_user",
    "connected_account",
    "document",
    "extraction_job",
    "email_record",
    "template",
    "campaign",
    "message",
    "event",
    "suppression_entry",
    "audit_log",
]
# sequence_step is scoped transitively through campaign (no org_id column); it is
# protected by FK + cascade and the campaign policy. Not listed above.

__all__ = [
    "AppUser",
    "AuditLog",
    "Base",
    "Campaign",
    "ConnectedAccount",
    "Document",
    "EmailRecord",
    "Event",
    "ExtractionJob",
    "Message",
    "Organization",
    "SequenceStep",
    "SuppressionEntry",
    "TENANT_TABLES",
    "Template",
]
