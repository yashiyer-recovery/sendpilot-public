"""Per-task tenant context.

Worker tasks have no HTTP request, so the RLS org scope MUST be set explicitly
from the task's ``org_id`` argument. EVERY task acquires its DB session through
:func:`task_session` — a task that queries outside it either sees nothing or
(if misconfigured) risks crossing tenants. This is correctness-critical.
"""

from __future__ import annotations

from ..db.session import org_session

# The org-scoped session context manager is exactly the RLS wrapper tasks need.
task_session = org_session

__all__ = ["task_session"]
