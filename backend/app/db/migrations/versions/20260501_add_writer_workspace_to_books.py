"""Add writer workspace storage to books.

Revision ID: 20260501_add_writer_workspace_to_books
Revises: 20260501_add_obsidian_note_graph
Create Date: 2026-05-01 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260501_add_writer_workspace_to_books"
down_revision: str | None = "20260501_add_obsidian_note_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("books")}
    if "writer_workspace" not in columns:
        op.add_column(
            "books",
            sa.Column(
                "writer_workspace",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("books")}
    if "writer_workspace" in columns:
        op.drop_column("books", "writer_workspace")
