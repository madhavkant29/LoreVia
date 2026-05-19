"""Add per-user LLM usage events.

Revision ID: 20260514_add_llm_usage_events
Revises: 20260514_add_user_writing_activities
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_llm_usage_events"
down_revision: str | None = "20260514_add_user_writing_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "llm_usage_events" not in tables:
        op.create_table(
            "llm_usage_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("provider", sa.String(), nullable=False, server_default="openai"),
            sa.Column("model", sa.String(), nullable=False),
            sa.Column("operation", sa.String(), nullable=False),
            sa.Column("feature", sa.String(), nullable=False),
            sa.Column("request_id", sa.String(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("llm_usage_events")

    if "llm_usage_events" not in tables:
        return

    columns = _column_names(inspector, "llm_usage_events")
    if "cached" not in columns:
        op.add_column("llm_usage_events", sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    indexes = _index_names(inspector, "llm_usage_events")
    for index_name, columns_list in (
        ("ix_llm_usage_events_user_id", ["user_id"]),
        ("ix_llm_usage_events_book_id", ["book_id"]),
        ("ix_llm_usage_events_provider", ["provider"]),
        ("ix_llm_usage_events_model", ["model"]),
        ("ix_llm_usage_events_operation", ["operation"]),
        ("ix_llm_usage_events_feature", ["feature"]),
        ("ix_llm_usage_events_request_id", ["request_id"]),
        ("ix_llm_usage_events_created_at", ["created_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "llm_usage_events", columns_list)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "llm_usage_events" in tables:
        op.drop_table("llm_usage_events")
