"""row-level security — tenant isolation policies (PRD §5.3)

Revision ID: 0002_rls
Revises: 0001_initial
Create Date: 2026-06-22

Every tenant-scoped table is isolated on ``app.current_org``. ``FORCE ROW LEVEL
SECURITY`` ensures even the table owner is subject to the policy (defence in
depth). The ``app.system`` clause is the only escape hatch, used by trusted
bootstrap/system code (signup, login lookup, cron) via ``system_session()``.

``current_setting(..., true)`` (missing_ok) means a query that forgets to set the
GUC is DENIED (NULL → no match), never errors and never leaks.
"""
from __future__ import annotations

from alembic import op

from sendpilot.db.models import TENANT_TABLES

revision = "0002_rls"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_ORG_PREDICATE = (
    "org_id = nullif(current_setting('app.current_org', true), '')::uuid "
    "OR current_setting('app.system', true) = 'on'"
)
_ID_PREDICATE = (
    "id = nullif(current_setting('app.current_org', true), '')::uuid "
    "OR current_setting('app.system', true) = 'on'"
)
# sequence_step has no org_id; scope it through its campaign (itself RLS-protected).
_SEQ_PREDICATE = "campaign_id IN (SELECT id FROM campaign)"


def _enable(table: str, predicate: str) -> None:
    op.execute("ALTER TABLE %s ENABLE ROW LEVEL SECURITY" % table)
    op.execute("ALTER TABLE %s FORCE ROW LEVEL SECURITY" % table)
    op.execute(
        "CREATE POLICY tenant_isolation ON %s USING (%s) WITH CHECK (%s)"
        % (table, predicate, predicate)
    )


def upgrade() -> None:
    op.execute("ALTER TABLE organization ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON organization USING (%s) WITH CHECK (%s)"
        % (_ID_PREDICATE, _ID_PREDICATE)
    )
    for table in TENANT_TABLES:
        _enable(table, _ORG_PREDICATE)
    _enable("sequence_step", _SEQ_PREDICATE)


def downgrade() -> None:
    for table in ["sequence_step", *TENANT_TABLES, "organization"]:
        op.execute("DROP POLICY IF EXISTS tenant_isolation ON %s" % table)
        op.execute("ALTER TABLE %s DISABLE ROW LEVEL SECURITY" % table)
