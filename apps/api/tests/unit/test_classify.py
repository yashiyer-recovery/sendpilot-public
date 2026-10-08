"""Document-shape classifier (PRD §8.2)."""

from __future__ import annotations

import pandas as pd

from sendpilot.extraction.classify import classify_shape
from sendpilot.ingestion.extract_text import DocumentText


def test_tabular():
    df = pd.DataFrame({"email": ["a@x.com", "b@y.com"], "subject": ["s", "s"]})
    assert classify_shape(DocumentText(text="", kind="table", tables=[df])) == "tabular"


def test_single_draft():
    doc = DocumentText(text="To: a@x.com\nSubject: hi\nbody here", kind="document")
    assert classify_shape(doc) == "single_draft"


def test_repeated_blocks():
    text = "To: a@x.com\nSubject: s1\nb1\n---\nTo: b@y.com\nSubject: s2\nb2"
    assert classify_shape(DocumentText(text=text, kind="document")) == "repeated_blocks"
