"""MIME builder — text + HTML + threading headers (PRD §11.2)."""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from .provider import OutboundEmail


def build_mime_message(email: OutboundEmail) -> tuple[MIMEMultipart, str]:
    root = MIMEMultipart("alternative")
    root["From"] = email.from_email
    root["To"] = email.to
    if email.cc:
        root["Cc"] = ", ".join(email.cc)
    root["Subject"] = email.subject
    root["Date"] = formatdate(localtime=True)
    msg_id = make_msgid()
    root["Message-ID"] = msg_id
    if email.in_reply_to:  # threading for follow-ups
        root["In-Reply-To"] = email.in_reply_to
        root["References"] = (email.references or "") + " " + email.in_reply_to
    if email.body_format == "html":
        root.attach(MIMEText(_html_to_text(email.body), "plain", "utf-8"))
        root.attach(MIMEText(email.body, "html", "utf-8"))
    else:
        root.attach(MIMEText(email.body, "plain", "utf-8"))
    return root, msg_id


def build_mime(email: OutboundEmail) -> tuple[bytes, str]:
    root, msg_id = build_mime_message(email)
    return root.as_bytes(), msg_id


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser").get_text("\n")
