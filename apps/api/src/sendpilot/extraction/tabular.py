"""Deterministic tabular path — header detection + column mapping (PRD §8.3).

Header names are matched heuristically; only ambiguous/missing headers trigger a
single small LLM call to map columns. The mapping is then applied to every row
with no further model cost — this is what keeps high-volume lists cheap.
"""

from __future__ import annotations

import re

import pandas as pd

from .aliases import ALIASES
from .llm import get_llm_client
from .schema import EmailRecord

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _heuristic_map(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for field, names in ALIASES.items():
        for col in df.columns:
            if col in used:
                continue
            if str(col).strip().lower() in names:
                mapping[field] = col
                used.add(col)
                break
    # Fallback: detect the email column by value shape.
    if "recipient_email" not in mapping:
        for col in df.columns:
            vals = [v for v in df[col].astype(str) if v.strip()]
            if vals and sum(bool(EMAIL_RE.fullmatch(v.strip())) for v in vals) / len(vals) > 0.6:
                mapping["recipient_email"] = col
                break
    return mapping


def extract_tabular(df: pd.DataFrame, document_id: str) -> list[EmailRecord]:
    mapping = _heuristic_map(df)
    # Only call the model if the heuristics missed the essentials.
    if "recipient_email" not in mapping or "body" not in mapping:
        llm_map = get_llm_client().map_columns(
            [str(c) for c in df.columns], df.head(3).to_dict("records")
        )
        # Trust the heuristic mapping where present; fill gaps from the LLM.
        for field, col in llm_map.items():
            mapping.setdefault(field, col)

    def cell(row, field: str) -> str:
        col = mapping.get(field)
        return str(row.get(col, "")).strip() if col else ""

    records: list[EmailRecord] = []
    for i, row in df.iterrows():
        records.append(
            EmailRecord(
                recipient_email=cell(row, "recipient_email"),
                recipient_name=cell(row, "recipient_name") or None,
                subject=cell(row, "subject"),
                body=cell(row, "body"),
                body_format="text",
                cc=[v for v in [cell(row, "cc")] if v],
                bcc=[v for v in [cell(row, "bcc")] if v],
                source_ref={"document_id": document_id, "location": f"row {int(i) + 2}"},
                confidence=0.99 if {"recipient_email", "body"} <= mapping.keys() else 0.6,
            )
        )
    return records
