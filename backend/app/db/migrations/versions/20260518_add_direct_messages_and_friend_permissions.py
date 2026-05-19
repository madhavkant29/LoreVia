"""Add direct messages and friend permissions.

Revision ID: 20260518_add_direct_messages_and_friend_permissions
Revises: 20260518_repair_beta_read_assignment_awarded_at_drift
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260518_add_direct_messages_and_friend_permissions"
down_revision: str | None = "20260518_repair_beta_read_assignment_awarded_at_drift"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name) if index.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        columns = _column_names(inspector, "users")
        if "messaging_permission" not in columns:
            op.add_column("users", sa.Column("messaging_permission", sa.String(), nullable=True, server_default="anyone"))

    if "friend_requests" not in tables:
        op.create_table(
            "friend_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("addressee_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("requester_user_id", "addressee_user_id", name="uq_friend_requests_direction"),
        )

    inspector = sa.inspect(bind)
    if "friend_requests" in _table_names(inspector):
        indexes = _index_names(inspector, "friend_requests")
        if "ix_friend_requests_requester_user_id" not in indexes:
            op.create_index("ix_friend_requests_requester_user_id", "friend_requests", ["requester_user_id"])
        if "ix_friend_requests_addressee_user_id" not in indexes:
            op.create_index("ix_friend_requests_addressee_user_id", "friend_requests", ["addressee_user_id"])
        if "ix_friend_requests_status" not in indexes:
            op.create_index("ix_friend_requests_status", "friend_requests", ["status"])

    if "direct_conversations" not in _table_names(sa.inspect(bind)):
        op.create_table(
            "direct_conversations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("participant_a_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("participant_b_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("participant_a_user_id", "participant_b_user_id", name="uq_direct_conversations_pair"),
        )

    inspector = sa.inspect(bind)
    if "direct_conversations" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_conversations")
        if "ix_direct_conversations_participant_a_user_id" not in indexes:
            op.create_index("ix_direct_conversations_participant_a_user_id", "direct_conversations", ["participant_a_user_id"])
        if "ix_direct_conversations_participant_b_user_id" not in indexes:
            op.create_index("ix_direct_conversations_participant_b_user_id", "direct_conversations", ["participant_b_user_id"])
        if "ix_direct_conversations_last_message_at" not in indexes:
            op.create_index("ix_direct_conversations_last_message_at", "direct_conversations", ["last_message_at"])

    if "direct_messages" not in _table_names(sa.inspect(bind)):
        op.create_table(
            "direct_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("direct_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("recipient_read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    inspector = sa.inspect(bind)
    if "direct_messages" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_messages")
        if "ix_direct_messages_conversation_id" not in indexes:
            op.create_index("ix_direct_messages_conversation_id", "direct_messages", ["conversation_id"])
        if "ix_direct_messages_sender_user_id" not in indexes:
            op.create_index("ix_direct_messages_sender_user_id", "direct_messages", ["sender_user_id"])
        if "ix_direct_messages_recipient_user_id" not in indexes:
            op.create_index("ix_direct_messages_recipient_user_id", "direct_messages", ["recipient_user_id"])
        if "ix_direct_messages_recipient_read_at" not in indexes:
            op.create_index("ix_direct_messages_recipient_read_at", "direct_messages", ["recipient_read_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "direct_messages" in tables:
        for index_name in (
            "ix_direct_messages_recipient_read_at",
            "ix_direct_messages_recipient_user_id",
            "ix_direct_messages_sender_user_id",
            "ix_direct_messages_conversation_id",
        ):
            if index_name in _index_names(sa.inspect(bind), "direct_messages"):
                op.drop_index(index_name, table_name="direct_messages")
        op.drop_table("direct_messages")

    if "direct_conversations" in _table_names(sa.inspect(bind)):
        for index_name in (
            "ix_direct_conversations_last_message_at",
            "ix_direct_conversations_participant_b_user_id",
            "ix_direct_conversations_participant_a_user_id",
        ):
            if index_name in _index_names(sa.inspect(bind), "direct_conversations"):
                op.drop_index(index_name, table_name="direct_conversations")
        op.drop_table("direct_conversations")

    if "friend_requests" in _table_names(sa.inspect(bind)):
        for index_name in (
            "ix_friend_requests_status",
            "ix_friend_requests_addressee_user_id",
            "ix_friend_requests_requester_user_id",
        ):
            if index_name in _index_names(sa.inspect(bind), "friend_requests"):
                op.drop_index(index_name, table_name="friend_requests")
        op.drop_table("friend_requests")

    if "users" in _table_names(sa.inspect(bind)):
        columns = _column_names(sa.inspect(bind), "users")
        if "messaging_permission" in columns:
            op.drop_column("users", "messaging_permission")
