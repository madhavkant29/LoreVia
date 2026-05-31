"""Add Supabase auth id mapping to users.

Revision ID: 20260527_add_users_supabase_auth_id
Revises: 20260525_add_admin_principals
Create Date: 2026-05-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_add_users_supabase_auth_id"
down_revision: str | Sequence[str] | None = "20260525_add_admin_principals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "supabase_auth_id" not in columns:
        op.add_column("users", sa.Column("supabase_auth_id", postgresql.UUID(as_uuid=True), nullable=True))

    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "uq_users_supabase_auth_id" not in unique_constraints:
        op.create_unique_constraint("uq_users_supabase_auth_id", "users", ["supabase_auth_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "uq_users_supabase_auth_id" in unique_constraints:
        op.drop_constraint("uq_users_supabase_auth_id", "users", type_="unique")

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "supabase_auth_id" in columns:
        op.drop_column("users", "supabase_auth_id")
