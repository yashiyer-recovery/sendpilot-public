"""Deterministic, key-less LLM stand-in for dev + tests.

Mirrors the real client's behavior closely enough to exercise the narrative path
and the column-map fallback without an Anthropic key.
"""

from __future__ import annotations

import re

from ..aliases import ALIASES  # reuse the same alias table as the heuristic mapper
from ..schema import EmailRecord

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TO_RE = re.compile(r"(?im)^\s*to\s*:\s*(.+)$")
_SUBJECT_RE = re.compile(r"(?im)^\s*subject\s*:\s*(.+)$")


class FakeLLMClient:
    def map_columns(self, columns: list[str], sample_rows: list[dict]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        used: set[str] = set()
        for field, names in ALIASES.items():
            for col in columns:
                if col in used:
                    continue
                if str(col).strip().lower() in names:
                    mapping[field] = col
                    used.add(col)
                    break
        return mapping

    def extract_records(
        self, text: str, document_id: str, difficulty: str = "medium"
    ) -> tuple[list[EmailRecord], int, int]:
        # Split into blocks on blank-line or '---' separators; one email per block.
        blocks = re.split(r"\n\s*-{3,}\s*\n|\n\s*\n", text.strip())
        records: list[EmailRecord] = []
        for block in blocks:
            if not block.strip():
                continue
            to_match = _TO_RE.search(block)
            email_match = EMAIL_RE.search(to_match.group(1)) if to_match else EMAIL_RE.search(block)
            if not email_match:
                continue
            subject_match = _SUBJECT_RE.search(block)
            # Body = everything after the Subject line (or after the To line).
            anchor = subject_match or to_match
            body = block[anchor.end():].strip() if anchor else block.strip()
            name = None
            if to_match:
                name_m = re.search(r"\(([^)]+)\)", to_match.group(1))
                name = name_m.group(1).strip() if name_m else None
            records.append(
                EmailRecord(
                    recipient_email=email_match.group(0),
                    recipient_name=name,
                    subject=subject_match.group(1).strip() if subject_match else "",
                    body=body,
                    body_format="text",
                    source_ref={"document_id": document_id, "location": "narrative"},
                    confidence=0.5,
                )
            )
        return records, 0, 0
