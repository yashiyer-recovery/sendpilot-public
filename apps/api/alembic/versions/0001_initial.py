"""initial schema — extensions, enum types, all tables, app-role grants

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op

from sendpilot.db.base import Base
from sendpilot.db.enums import PG_ENUMS

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Non-superuser role the application connects as (created by the db init script).
APP_ROLE = "sendpilot_app"


def upgrade() -> None:
    bind = op.get_bind()

    # Extensions (CITEXT for case-insensitive email, pgcrypto for gen_random_uuid()).
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Enum types — created explicitly so models can reference them (create_type=False).
    for name, enum in PG_ENUMS:
        values = ", ".join("'%s'" % v.value for v in enum)
        op.execute("CREATE TYPE %s AS ENUM (%s)" % (name, values))

    # Tables — created from the ORM metadata so DB and models match exactly.
    Base.metadata.create_all(bind=bind)

    # Least-privilege DML for the app role. RLS (migration 0002) still applies to it.
    op.execute("GRANT USAGE ON SCHEMA public TO %s" % APP_ROLE)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %s"
               % APP_ROLE)
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %s" % APP_ROLE)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    for name, _ in reversed(PG_ENUMS):
        op.execute("DROP TYPE IF EXISTS %s" % name)
