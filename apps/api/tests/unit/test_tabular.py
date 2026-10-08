"""Deterministic tabular extraction — the Excel email/subject/body path (PRD §8.3)."""

from __future__ import annotations

import pandas as pd

from sendpilot.extraction.tabular import extract_tabular


def test_email_subject_body_columns():
    df = pd.DataFrame(
        {"email": ["a@x.com", "b@y.com"], "subject": ["S1", "S2"], "body": ["B1", "B2"]}
    )
    recs = extract_tabular(df, "doc1")
    assert len(recs) == 2
    assert recs[0].recipient_email == "a@x.com"
    assert recs[0].subject == "S1"
    assert recs[0].body == "B1"
    assert recs[0].confidence == 0.99
    assert recs[0].source_ref == {"document_id": "doc1", "location": "row 2"}


def test_email_detected_by_value_shape():
    # Header isn't an obvious email alias; the column is found by value shape.
    df = pd.DataFrame({"contact_addr": ["a@x.com"], "message": ["hello"]})
    recs = extract_tabular(df, "d")
    assert recs[0].recipient_email == "a@x.com"
    assert recs[0].body == "hello"
