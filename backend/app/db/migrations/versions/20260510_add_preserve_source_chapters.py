"""Add preserve_source_chapters to books.

Revision ID: 20260510_add_preserve_source_chapters
Revises: 20260510_add_rewarded_ad_sessions
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260510_add_preserve_source_chapters"
down_revision: str | None = "20260510_add_rewarded_ad_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("books")}
    if "preserve_source_chapters" not in columns:
        op.add_column(
            "books",
            sa.Column(
                "preserve_source_chapters",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("books")}
    if "preserve_source_chapters" in columns:
        op.drop_column("books", "preserve_source_chapters")
