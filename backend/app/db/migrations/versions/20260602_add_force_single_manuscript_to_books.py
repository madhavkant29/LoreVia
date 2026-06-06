"""Add force_single_manuscript column to books.

When True, all parsed chapters are merged into a single manuscript chapter
during ingestion, skipping chapter detection. Used by the "Import as single
file" fallback when the parser confidence is low or the user prefers it.

Revision ID: 20260602_add_force_single_manuscript_to_books
Revises: 20260602_add_import_structure_to_books
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260602_add_force_single_manuscript_to_books"
down_revision: str | Sequence[str] | None = "20260602_add_import_structure_to_books"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "force_single_manuscript" not in columns:
            op.add_column(
                "books",
                sa.Column(
                    "force_single_manuscript",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "force_single_manuscript" in columns:
            op.drop_column("books", "force_single_manuscript")
