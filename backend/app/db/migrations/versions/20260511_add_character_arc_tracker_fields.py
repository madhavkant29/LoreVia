"""Add author-grade character arc tracker fields.

Revision ID: 20260511_add_character_arc_tracker_fields
Revises: 20260510_add_preserve_source_chapters
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260511_add_character_arc_tracker_fields"
down_revision: str | None = "20260510_add_preserve_source_chapters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "goal" not in character_columns:
            op.add_column("characters", sa.Column("goal", sa.String(), nullable=True))
        if "lie_they_believe" not in character_columns:
            op.add_column("characters", sa.Column("lie_they_believe", sa.String(), nullable=True))
        if "backstory_wound" not in character_columns:
            op.add_column("characters", sa.Column("backstory_wound", sa.String(), nullable=True))
        if "arc_type" not in character_columns:
            op.add_column("characters", sa.Column("arc_type", sa.String(), nullable=True))

    if "character_states" in tables:
        state_columns = {column["name"] for column in inspector.get_columns("character_states")}
        if "motivations_snapshot" not in state_columns:
            op.add_column(
                "character_states",
                sa.Column("motivations_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            )
        if "fears_snapshot" not in state_columns:
            op.add_column(
                "character_states",
                sa.Column("fears_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "character_states" in tables:
        state_columns = {column["name"] for column in inspector.get_columns("character_states")}
        if "fears_snapshot" in state_columns:
            op.drop_column("character_states", "fears_snapshot")
        if "motivations_snapshot" in state_columns:
            op.drop_column("character_states", "motivations_snapshot")

    if "characters" in tables:
        character_columns = {column["name"] for column in inspector.get_columns("characters")}
        if "arc_type" in character_columns:
            op.drop_column("characters", "arc_type")
        if "backstory_wound" in character_columns:
            op.drop_column("characters", "backstory_wound")
        if "lie_they_believe" in character_columns:
            op.drop_column("characters", "lie_they_believe")
        if "goal" in character_columns:
            op.drop_column("characters", "goal")
