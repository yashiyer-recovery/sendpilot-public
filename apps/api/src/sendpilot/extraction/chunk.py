"""Chunking + dedupe for large narrative documents (PRD §8.5)."""

from __future__ import annotations

from .schema import EmailRecord


def chunk_text(text: str, max_chars: int = 16000) -> list[str]:
    blocks: list[str] = []
    cur: list[str] = []
    size = 0
    for block in text.split("\n\n"):
        if size + len(block) > max_chars and cur:
            blocks.append("\n\n".join(cur))
            cur, size = [], 0
        cur.append(block)
        size += len(block) + 2
    if cur:
        blocks.append("\n\n".join(cur))
    return blocks


def dedupe(records: list[EmailRecord]) -> list[EmailRecord]:
    seen: set[tuple[str, str]] = set()
    out: list[EmailRecord] = []
    for r in records:
        key = ((r.recipient_email or "").lower(), (r.subject or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
