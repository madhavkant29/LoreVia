"""Add flexible metadata to novel scenes.

Revision ID: 20260507_add_novel_scene_metadata
Revises: 20260506_remove_cover_processing_fields
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_add_novel_scene_metadata"
down_revision = "20260506_remove_cover_processing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "novel_scenes" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("novel_scenes")}
    if "metadata" not in columns:
        op.add_column(
            "novel_scenes",
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "novel_scenes" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("novel_scenes")}
    if "metadata" in columns:
        op.drop_column("novel_scenes", "metadata")
