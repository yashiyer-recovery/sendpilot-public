"""Column-name aliases for the tabular path (shared, dependency-free)."""

from __future__ import annotations

ALIASES: dict[str, list[str]] = {
    "recipient_email": ["recipient_email", "email", "e-mail", "to", "recipient", "address", "mail"],
    "recipient_name": ["recipient_name", "name", "first name", "first_name", "full name", "contact"],
    "subject": ["subject", "title", "subject line", "subject_line"],
    "body": ["body", "message", "content", "email body", "email_body", "note"],
    "cc": ["cc"],
    "bcc": ["bcc"],
}
