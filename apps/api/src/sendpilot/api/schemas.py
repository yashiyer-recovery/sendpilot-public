"""Request/response DTOs for the HTTP surface (kept separate from ORM models)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    org_name: str
    email: EmailStr


class PrincipalOut(BaseModel):
    org_id: str
    user_id: str
    role: str
    email: str | None = None


class AuthStartResponse(BaseModel):
    auth_url: str


class ConnectionOut(BaseModel):
    id: str
    provider: str
    account_email: str
    status: str


class ConnectedResult(BaseModel):
    connected: bool
    account_id: str
    email: str


class SmtpConnectRequest(BaseModel):
    account_email: EmailStr
    host: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    starttls: bool = True


class GoogleStartRequest(BaseModel):
    # Optional per-account OAuth client. If omitted, the global default is used.
    client_id: str | None = None
    client_secret: str | None = None


class DocumentOut(BaseModel):
    id: str
    status: str
    filename: str
    mime_type: str
    size_bytes: int


class UploadResponse(BaseModel):
    document_id: str
    status: str


class ExtractionStartResponse(BaseModel):
    extraction_job_id: str
    status: str


class ExtractionJobOut(BaseModel):
    id: str
    status: str
    shape: str
    record_count: int
    needs_review_count: int


class ExtractionJobListItem(BaseModel):
    id: str
    filename: str
    status: str
    shape: str
    record_count: int
    needs_review_count: int
    created_at: str


class RecordOut(BaseModel):
    id: str
    recipient_email: str | None
    recipient_name: str | None
    subject: str | None
    body: str | None
    body_format: str
    confidence: float
    validation_status: str
    review_status: str
    source_ref: dict


class RecordsPage(BaseModel):
    records: list[RecordOut]
    next_cursor: str | None = None


class RecordPatch(BaseModel):
    subject: str | None = None
    body: str | None = None
    recipient_email: str | None = None


class BulkApprove(BaseModel):
    record_ids: list[str]


class CampaignCreate(BaseModel):
    name: str
    connected_account_id: str
    type: str = "one_off"
    record_ids: list[str]


class CampaignOut(BaseModel):
    id: str
    name: str
    type: str
    status: str
    record_count: int


class SendRequest(BaseModel):
    mode: str = "now"  # now | scheduled
    scheduled_at: str | None = None


class SendResponse(BaseModel):
    campaign_id: str
    enqueued: int
    skipped_unapproved: int
    skipped_already_sent: int = 0


class MessageOut(BaseModel):
    id: str
    status: str
    provider_message_id: str | None
    thread_id: str | None
    error: str | None


class EventOut(BaseModel):
    type: str
    occurred_at: str


class SuppressionCreate(BaseModel):
    email: EmailStr
    reason: str = "manual"


class SuppressionOut(BaseModel):
    email: str
    reason: str


class WebhookEvent(BaseModel):
    org_id: str
    type: str  # delivered | bounce | complaint | reply
    provider_message_id: str
    dsn_status: str | None = None
    from_addr: str | None = None
