"""Repair missing beta read assignment JSONB columns.

Revision ID: 20260516_repair_beta_read_assignment_jsonb_columns
Revises: 20260515_add_chapter_content_version
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260516_repair_beta_read_assignment_jsonb_columns"
down_revision: str | None = "20260515_add_chapter_content_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "beta_read_assignments" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("beta_read_assignments")}

    if "author_questions_json" not in columns:
        op.add_column(
            "beta_read_assignments",
            sa.Column(
                "author_questions_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    if "feedback_payload" not in columns:
        op.add_column(
            "beta_read_assignments",
            sa.Column(
                "feedback_payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "beta_read_assignments" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("beta_read_assignments")}

    if "feedback_payload" in columns:
        op.drop_column("beta_read_assignments", "feedback_payload")

    if "author_questions_json" in columns:
        op.drop_column("beta_read_assignments", "author_questions_json")
