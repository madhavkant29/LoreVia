"""Add explicit manual flag for characters.

Revision ID: 20260514_add_manual_character_flag
Revises: 20260514_add_beta_read_assignments, 20260514_add_chapter_structure_version, 20260514_add_user_writing_activities
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260514_add_manual_character_flag"
down_revision: str | Sequence[str] | None = (
    "20260514_add_beta_read_assignments",
    "20260514_add_chapter_structure_version",
    "20260514_add_user_writing_activities",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("characters")}
    if "is_manual" not in columns:
        op.add_column(
            "characters",
            sa.Column(
                "is_manual",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("characters")}
    if "is_manual" in columns:
        op.drop_column("characters", "is_manual")
