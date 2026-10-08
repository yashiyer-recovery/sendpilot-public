"""Deterministic narrative extraction via the fake client (PRD §8.8 example)."""

from __future__ import annotations

from sendpilot.extraction.llm.fake_client import FakeLLMClient


def test_two_drafts():
    text = (
        "To: jane@acme.com\nSubject: Onboarding question\nHi Jane, loved the demo.\n"
        "---\n"
        "To: sam@globex.io (Sam Lee)\nSubject: Following up\nHi Sam, circling back."
    )
    recs, tokens_in, tokens_out = FakeLLMClient().extract_records(text, "doc")
    assert len(recs) == 2
    assert recs[0].recipient_email == "jane@acme.com"
    assert recs[0].subject == "Onboarding question"
    assert "loved the demo" in recs[0].body
    assert recs[1].recipient_email == "sam@globex.io"
    assert recs[1].recipient_name == "Sam Lee"
    assert tokens_in == 0 and tokens_out == 0


def test_map_columns():
    mapping = FakeLLMClient().map_columns(["Email", "Subject Line", "Message"], [])
    assert mapping["recipient_email"] == "Email"
    assert mapping["subject"] == "Subject Line"
    assert mapping["body"] == "Message"
