"""Add chapter version restore lifecycle fields.

Revision ID: 20260529_add_chapter_version_restore_lifecycle
Revises: 20260528_add_character_approval_workflow
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_add_chapter_version_restore_lifecycle"
down_revision: str | Sequence[str] | None = "20260528_add_character_approval_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chapter_versions" not in tables:
        return

    columns = _column_names(inspector, "chapter_versions")
    if "restore_status" not in columns:
        op.add_column("chapter_versions", sa.Column("restore_status", sa.String(), nullable=True))
    if "restore_error" not in columns:
        op.add_column("chapter_versions", sa.Column("restore_error", sa.Text(), nullable=True))
    if "restore_task_id" not in columns:
        op.add_column("chapter_versions", sa.Column("restore_task_id", sa.String(), nullable=True))
    if "restore_started_at" not in columns:
        op.add_column("chapter_versions", sa.Column("restore_started_at", sa.DateTime(timezone=True), nullable=True))
    if "restore_completed_at" not in columns:
        op.add_column("chapter_versions", sa.Column("restore_completed_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "chapter_versions")
    if "ix_chapter_versions_restore_status" not in indexes:
        op.create_index("ix_chapter_versions_restore_status", "chapter_versions", ["restore_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chapter_versions" not in tables:
        return

    indexes = _index_names(inspector, "chapter_versions")
    if "ix_chapter_versions_restore_status" in indexes:
        op.drop_index("ix_chapter_versions_restore_status", table_name="chapter_versions")

    columns = _column_names(inspector, "chapter_versions")
    for column_name in (
        "restore_completed_at",
        "restore_started_at",
        "restore_task_id",
        "restore_error",
        "restore_status",
    ):
        if column_name in columns:
            op.drop_column("chapter_versions", column_name)
