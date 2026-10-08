"""The canonical EmailRecord contract (PRD §5.5, §8.4).

The pydantic model is the single source of truth. The JSON Schema handed to
Claude for constrained decoding is DERIVED from it (see ``email_records_schema``)
so the two can never drift — ``tests/unit/test_schema.py`` asserts this.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

BODY_FORMATS = ["text", "html"]


class EmailRecord(BaseModel):
    recipient_email: str
    recipient_name: str | None = None
    subject: str
    body: str
    body_format: str = "text"
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    merge_fields: dict[str, str] = Field(default_factory=dict)
    source_ref: dict = Field(default_factory=dict)
    confidence: float = 0.0
    # Internal (not model-emitted): set by the validation stage (PRD §9).
    validation_status: str = "needs_review"


# Fields the extractor is allowed to emit. NOTE: strict structured outputs forbid
# open-ended objects (additionalProperties must be false), so merge_fields and
# source_ref are NOT model-emitted — source_ref is attached by us, and merge
# placeholders live inline in the body ({{first_name}}), not as a separate dict.
_RECORD_PROPERTIES = {
    "recipient_email": {"type": "string"},
    "recipient_name": {"type": "string"},
    "subject": {"type": "string"},
    "body": {"type": "string"},
    "body_format": {"type": "string", "enum": BODY_FORMATS},
    "cc": {"type": "array", "items": {"type": "string"}},
    "bcc": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number"},
}

RECORD_SCHEMA = {
    "type": "object",
    "properties": _RECORD_PROPERTIES,
    "required": ["recipient_email", "subject", "body", "confidence"],
    "additionalProperties": False,
}

EMAIL_RECORDS_SCHEMA = {
    "type": "object",
    "properties": {"records": {"type": "array", "items": RECORD_SCHEMA}},
    "required": ["records"],
    "additionalProperties": False,
}

COLUMN_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        f: {"type": "string"}
        for f in ["recipient_email", "recipient_name", "subject", "body", "cc", "bcc"]
    },
    "required": ["recipient_email", "body"],
    "additionalProperties": False,
}


def schema_field_names() -> set[str]:
    """Property names in the constrained record schema (for the drift test)."""
    return set(_RECORD_PROPERTIES.keys())
