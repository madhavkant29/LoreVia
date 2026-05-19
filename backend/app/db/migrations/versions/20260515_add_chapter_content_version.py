"""Add chapter content versioning for optimistic manuscript saves.

Revision ID: 20260515_add_chapter_content_version
Revises: 20260515_normalize_collab_beta_state
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260515_add_chapter_content_version"
down_revision: str | None = "20260515_normalize_collab_beta_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "content_version" not in chapter_columns:
            op.add_column(
                "chapters",
                sa.Column(
                    "content_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="1",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapters" in tables:
        chapter_columns = {column["name"] for column in inspector.get_columns("chapters")}
        if "content_version" in chapter_columns:
            op.drop_column("chapters", "content_version")
