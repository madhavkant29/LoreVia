"""Add user_login_activity table and backfill from users.login_activity_dates.

Revision ID: 20260529_add_user_login_activity_table
Revises: 20260529_add_missing_fk_indexes
Create Date: 2026-05-29 00:00:00.000000

Phase 1 of decoupling login activity from the users table:
- Creates user_login_activity table with (user_id, login_date) index.
- Backfills existing data from the users.login_activity_dates ARRAY column.
- The old ARRAY column is preserved during this phase for dual-write safety.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260529_add_user_login_activity_table"
down_revision: str | Sequence[str] | None = "20260529_add_missing_fk_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    columns = {col["name"] for col in inspector.get_columns("users")} if "users" in tables else set()

    # Create the table if it doesn't exist
    if "user_login_activity" not in tables:
        op.create_table(
            "user_login_activity",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("login_date", sa.Date(), nullable=False),
            sa.Column("ip_hash", sa.String(), nullable=True),
            sa.Column("device_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Create index if it doesn't exist
    indexes = {idx["name"] for idx in inspector.get_indexes("user_login_activity")}
    if "ix_user_login_activity_user_date" not in indexes:
        op.create_index(
            "ix_user_login_activity_user_date",
            "user_login_activity",
            ["user_id", "login_date"],
        )

    # Backfill from users.login_activity_dates array
    if "users" in tables and "login_activity_dates" in columns:
        bind.execute(
            sa.text(
                """INSERT INTO user_login_activity (id, user_id, login_date)
                   SELECT gen_random_uuid(), u.id, unnest_date
                   FROM users u,
                        LATERAL unnest(u.login_activity_dates) AS unnest_date
                   WHERE u.login_activity_dates IS NOT NULL
                     AND cardinality(u.login_activity_dates) > 0"""
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_login_activity" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("user_login_activity")}
        if "ix_user_login_activity_user_date" in indexes:
            op.drop_index("ix_user_login_activity_user_date", table_name="user_login_activity")
        op.drop_table("user_login_activity")
