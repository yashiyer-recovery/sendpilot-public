"""Template merge-field rendering + unsubscribe footer (PRD §13.1)."""

from __future__ import annotations

import re

from ..compliance.unsubscribe import add_unsubscribe_footer
from ..config import settings

TOKEN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class MissingMergeField(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


def _substitute(text: str, merge_fields: dict) -> str:
    def repl(m: re.Match[str]) -> str:
        val = merge_fields.get(m.group(1))
        if val is None:
            raise MissingMergeField(m.group(1))
        return val

    return TOKEN.sub(repl, text)


def render(record, org) -> tuple[str, str]:
    """Render (subject, body) for an EmailRecord row. Raises MissingMergeField.

    Refuses to send on a missing required token; appends the compliant footer.
    """
    merge = dict(record.merge_fields or {})
    subject = _substitute(record.subject or "", merge)
    body = _substitute(record.body or "", merge)
    if settings.unsubscribe_footer:
        body = add_unsubscribe_footer(
            body, str(record.org_id), record.recipient_email or "", org.physical_address,
            getattr(record, "body_format", "html"),
        )
    return subject, body
