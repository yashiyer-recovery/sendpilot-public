"""Merge-field rendering, unsubscribe tokens, idempotency keys."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sendpilot.campaign.merge import MissingMergeField, render
from sendpilot.compliance.unsubscribe import sign_unsubscribe, verify_unsubscribe
from sendpilot.config import settings
from sendpilot.sending.idempotency import idem_key


def _record(**kw):
    base = dict(
        org_id="org1", recipient_email="a@x.com", subject="Hi {{first_name}}",
        body="Welcome!", merge_fields={"first_name": "Al"},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _org():
    return SimpleNamespace(physical_address="123 Main St")


def test_render_substitutes_and_appends_footer():
    original = settings.unsubscribe_footer
    settings.unsubscribe_footer = True
    try:
        subject, body = render(_record(), _org())
        assert subject == "Hi Al"
        assert "Welcome!" in body
        assert "Unsubscribe" in body
        assert "123 Main St" in body
    finally:
        settings.unsubscribe_footer = original


def test_render_footer_disabled_leaves_body_clean():
    original = settings.unsubscribe_footer
    settings.unsubscribe_footer = False
    try:
        subject, body = render(_record(), _org())
        assert subject == "Hi Al"
        assert body == "Welcome!"  # no footer, no raw HTML, no localhost link
    finally:
        settings.unsubscribe_footer = original


def test_render_missing_merge_field():
    with pytest.raises(MissingMergeField):
        render(_record(merge_fields={}), _org())


def test_unsubscribe_token_roundtrip():
    token = sign_unsubscribe("org1", "a@x.com")
    assert verify_unsubscribe(token) == ("org1", "a@x.com")


def test_unsubscribe_tamper_rejected():
    token = sign_unsubscribe("org1", "a@x.com")
    body, sig = token.split(".", 1)
    assert verify_unsubscribe(f"{body}x.{sig}") is None
    assert verify_unsubscribe("garbage") is None


def test_idem_key_deterministic_and_unique():
    assert idem_key("c", "r", 0) == idem_key("c", "r", 0)
    assert idem_key("c", "r", 0) != idem_key("c", "r", 1)
    assert idem_key("c", "r1", 0) != idem_key("c", "r2", 0)
