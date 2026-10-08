"""LLM client protocol (PRD §8.4).

Synchronous on purpose: the whole extraction pipeline (parse, classify, tabular,
narrative) is CPU/IO-blocking and is run off the event loop in a thread by the
orchestrator. A :class:`FakeLLMClient` lets tests and key-less dev exercise the
narrative path; the tabular path never needs the model.
"""

from __future__ import annotations

from typing import Protocol

from ..schema import EmailRecord


class LLMClient(Protocol):
    def map_columns(self, columns: list[str], sample_rows: list[dict]) -> dict[str, str]:
        """Map spreadsheet column names to EmailRecord fields."""
        ...

    def extract_records(
        self, text: str, document_id: str, difficulty: str = "medium"
    ) -> tuple[list[EmailRecord], int, int]:
        """Extract records from prose. Returns (records, tokens_in, tokens_out)."""
        ...
