"""Document-shape classifier (PRD §8.2).

Cheap heuristics decide most cases; an LLM tiebreaker (in the orchestrator) is
used only when the shape is ``unknown``.
"""

from __future__ import annotations

import re

from ..ingestion.extract_text import DocumentText

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def classify_shape(doc: DocumentText) -> str:
    if doc.kind == "table" and doc.tables:
        df = doc.tables[0]
        # A table is 'tabular' if some column is mostly email-shaped.
        for col in df.columns:
            vals = [v for v in df[col].astype(str) if v.strip()]
            if vals and sum(bool(EMAIL_RE.fullmatch(v.strip())) for v in vals) / len(vals) > 0.6:
                return "tabular"

    emails = EMAIL_RE.findall(doc.text)
    labels = len(re.findall(r"(?im)^\s*(to|subject|body)\s*:", doc.text))
    if len(set(emails)) >= 2 and labels >= 2:
        return "repeated_blocks"
    if len(set(emails)) <= 1:
        return "single_draft"
    return "unknown"  # -> LLM tiebreak in the orchestrator
