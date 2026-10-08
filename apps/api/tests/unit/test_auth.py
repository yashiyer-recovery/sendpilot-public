"""Session signing + RBAC (PRD §4.2)."""

from __future__ import annotations

from sendpilot.auth import Principal, has_role, issue_session, verify_session


def test_session_roundtrip():
    p = Principal(org_id="org-1", user_id="user-1", role="admin")
    assert verify_session(issue_session(p)) == p


def test_tampered_session_rejected():
    p = Principal(org_id="org-1", user_id="user-1", role="member")
    token = issue_session(p)
    body, sig = token.split(".", 1)
    assert verify_session(f"{body}x.{sig}") is None
    assert verify_session("garbage") is None
    assert verify_session(None) is None


def test_rbac_ordering():
    owner = Principal("o", "u", "owner")
    member = Principal("o", "u", "member")
    assert has_role(owner, "admin")
    assert has_role(owner, "member")
    assert not has_role(member, "admin")
    assert has_role(member, "member")
