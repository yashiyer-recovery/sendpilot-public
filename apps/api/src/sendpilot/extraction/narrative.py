"""Narrative path — chunk, extract per chunk via Claude, escalate low-confidence.

Runs synchronously (off the event loop, in the orchestrator's thread).
"""

from __future__ import annotations

from .chunk import chunk_text
from .llm import get_llm_client
from .schema import EmailRecord

LOW_CONFIDENCE = 0.7


def extract_narrative_records(text: str, document_id: str) -> tuple[list[EmailRecord], int, int]:
    client = get_llm_client()
    records: list[EmailRecord] = []
    tokens_in = tokens_out = 0
    for chunk in chunk_text(text):
        recs, ti, to = client.extract_records(chunk, document_id, difficulty="medium")
        tokens_in += ti
        tokens_out += to
        # Escalate a chunk whose records came back low-confidence (PRD §15.2).
        if recs and min(r.confidence for r in recs) < LOW_CONFIDENCE:
            recs2, ti2, to2 = client.extract_records(chunk, document_id, difficulty="hard")
            tokens_in += ti2
            tokens_out += to2
            if recs2:
                recs = recs2
        records.extend(recs)
    return records, tokens_in, tokens_out
