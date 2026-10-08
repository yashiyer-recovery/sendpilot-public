"""Central configuration. One source of truth for environment.

Settings are read once at import via :data:`settings`. Nothing else in the
codebase should read ``os.environ`` directly.
"""

from __future__ import annotations

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: str = "local"
    log_level: str = "INFO"

    # Database. The app connects as a NON-superuser role so RLS is enforced;
    # migrations connect as the owner (postgres).
    database_url: str = "postgresql+asyncpg://sendpilot_app:sendpilot_app@db:5432/sendpilot"
    database_url_sync: str = "postgresql+psycopg://postgres:postgres@db:5432/sendpilot"
    db_echo: bool = False

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Anthropic
    anthropic_api_key: str = ""

    # KMS / envelope encryption
    kms_key_id: str = "local:dev"
    kms_master_key: str = ""  # base64, 32 bytes, for LocalKMS only

    # Object storage (S3-compatible)
    object_storage_bucket: str = "sendpilot-docs"
    object_storage_endpoint: str = "http://minio:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_region: str = "us-east-1"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/v1/connections/google/callback"

    # Microsoft OAuth (M2)
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_redirect_uri: str = "http://localhost:8000/v1/connections/microsoft/callback"

    # Mock provider (local dev). Two URLs: the browser hits the PUBLIC url for the
    # authorize redirect; the API does server-to-server token/userinfo over the
    # internal docker hostname.
    mock_provider: bool = True
    mock_provider_url: str = "http://mock-provider:9100"  # internal (server-to-server)
    mock_provider_public_url: str = "http://localhost:9100"  # browser-facing

    # Sessions
    session_secret: str = "dev-session-secret-change-me"

    # Web app base URL (OAuth post-connect redirect target)
    web_base_url: str = "http://localhost:3000"

    # Unsubscribe footer (CAN-SPAM). Off = personal cold-outreach style (no footer).
    unsubscribe_footer: bool = True
    # Public, recipient-reachable base URL for unsubscribe links (NOT localhost).
    public_base_url: str = ""
    # Always-CC these addresses on every send (comma-separated). Empty = none.
    always_cc: str = ""

    # Retention
    doc_retention_days: int = 30

    # Upload limits
    max_upload_bytes: int = 25 * 1024 * 1024

    # Validation: live MX lookups (off locally/CI to stay offline-deterministic)
    validate_mx: bool = False
    # Confidence gate — records below this are routed to needs_review (PRD §9)
    confidence_threshold: float = 0.85

    # Circuit breaker (PRD §14): pause a campaign past these rates once it has
    # sent at least circuit_breaker_min_sent messages.
    circuit_breaker_min_sent: int = 50
    bounce_rate_threshold: float = 0.05
    complaint_rate_threshold: float = 0.005

    @property
    def is_local(self) -> bool:
        return self.env in ("local", "test")

    @property
    def use_local_kms(self) -> bool:
        return self.kms_key_id.startswith("local:")

    @property
    def always_cc_list(self) -> list[str]:
        return [e.strip() for e in self.always_cc.split(",") if e.strip()]

    @cached_property
    def google_auth_url(self) -> str:
        """Authorization endpoint (browser-facing) — real Google or the local mock."""
        if self.mock_provider:
            return f"{self.mock_provider_public_url}/mock/google/authorize"
        return "https://accounts.google.com/o/oauth2/v2/auth"

    @cached_property
    def google_token_url(self) -> str:
        if self.mock_provider:
            return f"{self.mock_provider_url}/mock/google/token"
        return "https://oauth2.googleapis.com/token"

    @cached_property
    def ms_auth_url(self) -> str:
        if self.mock_provider:
            return f"{self.mock_provider_public_url}/mock/ms/authorize"
        return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

    @cached_property
    def ms_token_url(self) -> str:
        if self.mock_provider:
            return f"{self.mock_provider_url}/mock/ms/token"
        return "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    # Webhook shared secret (provider event callbacks). Optional locally.
    webhook_secret: str = "dev-webhook-secret"


settings = Settings()
