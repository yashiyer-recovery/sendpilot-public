"""EmailRecord contract: pydantic model is the source of truth for the LLM schema."""

from __future__ import annotations

from sendpilot.extraction.schema import (
    EMAIL_RECORDS_SCHEMA,
    RECORD_SCHEMA,
    EmailRecord,
    schema_field_names,
)


def test_schema_props_are_model_fields():
    # No drift: every constrained-schema property exists on the model.
    assert schema_field_names() <= set(EmailRecord.model_fields)


def test_record_schema_is_strict():
    assert RECORD_SCHEMA["additionalProperties"] is False
    assert set(RECORD_SCHEMA["required"]) == {"recipient_email", "subject", "body", "confidence"}
    assert EMAIL_RECORDS_SCHEMA["additionalProperties"] is False


def test_no_open_objects():
    # Strict structured outputs forbid open additionalProperties.
    for prop in RECORD_SCHEMA["properties"].values():
        if prop.get("type") == "object":
            assert prop.get("additionalProperties") is False


def test_sample_record_round_trips():
    sample = {"recipient_email": "a@b.com", "subject": "hi", "body": "yo", "confidence": 0.9}
    rec = EmailRecord(**sample)
    assert rec.recipient_email == "a@b.com"
    assert rec.body_format == "text"
    assert rec.validation_status == "needs_review"
