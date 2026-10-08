"""Log redaction — PII/secrets must never reach the logs (PRD §16, §20)."""

from __future__ import annotations

import json

from sendpilot.logging import redact_processor


def test_secrets_dropped():
    out = redact_processor(None, "info", {
        "event": "token.refresh",
        "access_token": "ya29.super-secret",
        "refresh_token": "1//rt-secret",
    })
    assert out["access_token"] == "[REDACTED]"
    assert out["refresh_token"] == "[REDACTED]"
    assert "super-secret" not in json.dumps(out)


def test_recipient_email_masked():
    out = redact_processor(None, "info", {"event": "send", "recipient_email": "jane@acme.com"})
    assert "jane@acme.com" not in json.dumps(out)
    assert out["recipient_email"].startswith("j***@")


def test_email_in_message_masked():
    out = redact_processor(None, "info", {"event": "delivered to bob@globex.io"})
    assert "bob@globex.io" not in json.dumps(out)
