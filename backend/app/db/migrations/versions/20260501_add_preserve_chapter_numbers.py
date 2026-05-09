"""Add preserve_chapter_numbers to books.

Revision ID: 20260501_add_preserve_chapter_numbers
Revises: 20260501_add_obsidian_note_graph
Create Date: 2026-05-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260501_add_preserve_chapter_numbers"
down_revision: str | None = "20260501_add_obsidian_note_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("books")}
    if "preserve_chapter_numbers" not in columns:
        op.add_column(
            "books",
            sa.Column(
                "preserve_chapter_numbers",
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
    if "preserve_chapter_numbers" in columns:
        op.drop_column("books", "preserve_chapter_numbers")
