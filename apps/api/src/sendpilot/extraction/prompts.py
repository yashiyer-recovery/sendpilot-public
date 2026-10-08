"""Static extraction prompts (PRD §8.4). Kept static so they are cacheable."""

from __future__ import annotations

EXTRACTION_SYSTEM = """You extract sendable emails from a document. Return ONLY data that matches the
provided JSON schema.

Rules:
- Extract every distinct email present in the text. One object per email.
- Copy the subject and body VERBATIM from the source. Do not rewrite, summarize,
  improve, translate, or add a signature that is not present.
- Never invent a recipient address. If an email's recipient is not present in the
  text, omit that email rather than guessing.
- Preserve personalization placeholders exactly (for example {{first_name}}).
- If a field is missing or you are unsure, lower the per-record confidence
  (0.0-1.0) rather than fabricating a value. A missing required field means that
  record should not be emitted.
- body_format is "html" only if the source clearly contains HTML; otherwise "text".
"""

COLUMN_MAP_SYSTEM = (
    "Map spreadsheet columns to email fields. Return the source column "
    "name for each field. Use only the given column names."
)
