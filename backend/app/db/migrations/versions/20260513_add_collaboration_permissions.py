"""Add explicit collaboration permissions.

Revision ID: 20260513_add_collaboration_permissions
Revises: 20260511_add_book_collaborators
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260513_add_collaboration_permissions"
down_revision: str | None = "20260511_add_book_collaborators"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_collaborators" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("book_collaborators")}
    if "permissions" not in columns:
        op.add_column(
            "book_collaborators",
            sa.Column(
                "permissions",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default="{}",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_collaborators" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("book_collaborators")}
    if "permissions" in columns:
        op.drop_column("book_collaborators", "permissions")
