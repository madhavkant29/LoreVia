"""Add indexes for bounded direct-message reads.

Revision ID: 20260912_social_read_path_indexes
Revises: 20260912_workspace_search_indexes
Create Date: 2026-09-12

The indexes support cursor pages for direct conversations/messages and the
set-based unread-message update. They are backend-only indexes and do not
change Data API exposure.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260912_social_read_path_indexes"
down_revision: str | Sequence[str] | None = "20260912_workspace_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "direct_conversations" in tables:
        indexes = _index_names(inspector, "direct_conversations")
        for index_name, participant_column in (
            ("ix_direct_conversations_a_activity_id", "participant_a_user_id"),
            ("ix_direct_conversations_b_activity_id", "participant_b_user_id"),
        ):
            if index_name not in indexes:
                op.create_index(
                    index_name,
                    "direct_conversations",
                    [
                        participant_column,
                        sa.text("COALESCE(last_message_at, created_at) DESC"),
                        sa.text("id DESC"),
                    ],
                )

    if "direct_messages" in tables:
        indexes = _index_names(inspector, "direct_messages")
        if "ix_direct_messages_conversation_created_id" not in indexes:
            op.create_index(
                "ix_direct_messages_conversation_created_id",
                "direct_messages",
                ["conversation_id", "created_at", "id"],
            )
        if "ix_direct_messages_recipient_unread_conversation" not in indexes:
            op.create_index(
                "ix_direct_messages_recipient_unread_conversation",
                "direct_messages",
                ["recipient_user_id", "conversation_id"],
                postgresql_where=sa.text("recipient_read_at IS NULL"),
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    indexes: tuple[tuple[str, str], ...] = (
        ("direct_messages", "ix_direct_messages_recipient_unread_conversation"),
        ("direct_messages", "ix_direct_messages_conversation_created_id"),
        ("direct_conversations", "ix_direct_conversations_b_activity_id"),
        ("direct_conversations", "ix_direct_conversations_a_activity_id"),
    )
    for table_name, index_name in indexes:
        if table_name in tables and index_name in _index_names(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)
