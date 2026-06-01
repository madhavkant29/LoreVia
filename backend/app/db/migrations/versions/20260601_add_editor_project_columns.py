"""Add is_editor_project to books and edited_by_author to character_relationships / plot_threads.

Revision ID: 20260601_add_editor_project_columns
Revises: 20260530_remove_orphaned_indexes
Create Date: 2026-06-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260601_add_editor_project_columns"
down_revision: str | Sequence[str] | None = "20260530_remove_orphaned_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "is_editor_project" not in columns:
            op.add_column(
                "books",
                sa.Column(
                    "is_editor_project",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

    if "character_relationships" in tables:
        columns = {column["name"] for column in inspector.get_columns("character_relationships")}
        if "edited_by_author" not in columns:
            op.add_column(
                "character_relationships",
                sa.Column(
                    "edited_by_author",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

    if "plot_threads" in tables:
        columns = {column["name"] for column in inspector.get_columns("plot_threads")}
        if "edited_by_author" not in columns:
            op.add_column(
                "plot_threads",
                sa.Column(
                    "edited_by_author",
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
        if "is_editor_project" in columns:
            op.drop_column("books", "is_editor_project")

    if "character_relationships" in tables:
        columns = {column["name"] for column in inspector.get_columns("character_relationships")}
        if "edited_by_author" in columns:
            op.drop_column("character_relationships", "edited_by_author")

    if "plot_threads" in tables:
        columns = {column["name"] for column in inspector.get_columns("plot_threads")}
        if "edited_by_author" in columns:
            op.drop_column("plot_threads", "edited_by_author")
