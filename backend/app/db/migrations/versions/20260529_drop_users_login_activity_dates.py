"""Drop login_activity_dates ARRAY column from users table.

Revision ID: 20260529_drop_users_login_activity_dates
Revises: 20260529_add_user_login_activity_table
Create Date: 2026-05-29 00:00:00.000000

Phase 4 of decoupling login activity from the users table.
Run this migration ONLY after verifying the user_login_activity table is working
correctly and all reads have been switched to the new table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260529_drop_users_login_activity_dates"
down_revision: str | Sequence[str] | None = "20260529_add_user_login_activity_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "login_activity_dates" in columns:
        op.drop_column("users", "login_activity_dates")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "login_activity_dates" not in columns:
        op.add_column("users", sa.Column("login_activity_dates", sa.ARRAY(sa.Date()), nullable=True))
