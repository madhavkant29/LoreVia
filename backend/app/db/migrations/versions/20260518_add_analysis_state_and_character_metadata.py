"""Add chapter analysis state and character analysis metadata.

Revision ID: 20260518_add_analysis_state_and_character_metadata
Revises: 20260518_add_direct_messages_and_friend_permissions
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260518_add_analysis_state_and_character_metadata"
down_revision: str | None = "20260518_add_direct_messages_and_friend_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "analysis_state" not in chapter_columns:
            op.add_column(
                "chapters",
                sa.Column(
                    "analysis_state",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )

    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "analysis_metadata" not in character_columns:
            op.add_column(
                "characters",
                sa.Column(
                    "analysis_metadata",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "analysis_state" in chapter_columns:
            op.drop_column("chapters", "analysis_state")

    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "analysis_metadata" in character_columns:
            op.drop_column("characters", "analysis_metadata")
