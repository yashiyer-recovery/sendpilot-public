"""Claude-backed extraction via structured outputs (PRD §8, §15.1).

Uses the Messages API with ``output_config.format`` (grammar-constrained JSON),
so responses are schema-valid by construction — no fragile parsing/retry. Notes
validated against the current API:
- model ids: claude-haiku-4-5 / claude-sonnet-4-6 / claude-opus-4-8
- ``temperature`` is NOT sent (it 400s on opus-4-8); structured outputs + a
  deterministic prompt give stable extraction.
- the static system prompt carries ``cache_control`` for prompt caching.
"""

from __future__ import annotations

import json

import anthropic

from ..prompts import COLUMN_MAP_SYSTEM, EXTRACTION_SYSTEM
from ..schema import COLUMN_MAP_SCHEMA, EMAIL_RECORDS_SCHEMA, EmailRecord

# Model tiering (PRD §15.2): cheap for column mapping, default for narrative,
# escalate to opus on low-confidence chunks (handled by the orchestrator).
MODEL_BY_DIFFICULTY = {
    "easy": "claude-haiku-4-5",
    "medium": "claude-sonnet-4-6",
    "hard": "claude-opus-4-8",
}


def _first_text(resp) -> str:
    return next(b.text for b in resp.content if b.type == "text")


class AnthropicLLMClient:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def extract_records(
        self, text: str, document_id: str, difficulty: str = "medium"
    ) -> tuple[list[EmailRecord], int, int]:
        model = MODEL_BY_DIFFICULTY.get(difficulty, "claude-sonnet-4-6")
        resp = self._client.messages.create(
            model=model,
            max_tokens=8192,
            system=[{"type": "text", "text": EXTRACTION_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": EMAIL_RECORDS_SCHEMA}},
        )
        payload = json.loads(_first_text(resp))
        records: list[EmailRecord] = []
        for r in payload["records"]:
            r["source_ref"] = {"document_id": document_id, "location": "narrative"}
            records.append(EmailRecord(**r))
        return records, resp.usage.input_tokens, resp.usage.output_tokens

    def map_columns(self, columns: list[str], sample_rows: list[dict]) -> dict[str, str]:
        resp = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=COLUMN_MAP_SYSTEM,
            messages=[{"role": "user",
                       "content": json.dumps({"columns": columns, "sample": sample_rows})}],
            output_config={"format": {"type": "json_schema", "schema": COLUMN_MAP_SCHEMA}},
        )
        return json.loads(_first_text(resp))
