"""Reconcile social messaging and book moderation schema drift.

Revision ID: 20260519_reconcile_social_and_book_schema_drift
Revises: 20260519_remove_beta_read_awarded_at_residue
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260519_reconcile_social_and_book_schema_drift"
down_revision: str | None = "20260519_remove_beta_read_awarded_at_residue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _has_books_takedown_fk(inspector: sa.Inspector) -> bool:
    for foreign_key in inspector.get_foreign_keys("books"):
        constrained_columns = foreign_key.get("constrained_columns") or []
        if constrained_columns == ["takedown_by_user_id"] and foreign_key.get("referred_table") == "users":
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables and "messaging_permission" in _column_names(inspector, "users"):
        op.execute(sa.text("UPDATE users SET messaging_permission = 'anyone' WHERE messaging_permission IS NULL"))
        op.alter_column(
            "users",
            "messaging_permission",
            existing_type=sa.String(),
            existing_server_default=sa.text("'anyone'"),
            nullable=False,
        )

    inspector = sa.inspect(bind)
    if "friend_requests" in _table_names(inspector):
        indexes = _index_names(inspector, "friend_requests")
        for index_name, columns in [
            ("ix_friend_requests_created_at", ["created_at"]),
            ("ix_friend_requests_responded_at", ["responded_at"]),
            ("ix_friend_requests_updated_at", ["updated_at"]),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "friend_requests", columns, unique=False)

    inspector = sa.inspect(bind)
    if "direct_conversations" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_conversations")
        for index_name, columns in [
            ("ix_direct_conversations_created_at", ["created_at"]),
            ("ix_direct_conversations_updated_at", ["updated_at"]),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "direct_conversations", columns, unique=False)

    inspector = sa.inspect(bind)
    if "direct_messages" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_messages")
        if "ix_direct_messages_created_at" not in indexes:
            op.create_index("ix_direct_messages_created_at", "direct_messages", ["created_at"], unique=False)

    inspector = sa.inspect(bind)
    if "books" in _table_names(inspector) and "takedown_by_user_id" in _column_names(inspector, "books"):
        if not _has_books_takedown_fk(inspector):
            op.create_foreign_key(
                "fk_books_takedown_by_user_id_users",
                "books",
                "users",
                ["takedown_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "books" in tables:
        foreign_keys = {foreign_key.get("name") for foreign_key in inspector.get_foreign_keys("books")}
        if "fk_books_takedown_by_user_id_users" in foreign_keys:
            op.drop_constraint("fk_books_takedown_by_user_id_users", "books", type_="foreignkey")

    inspector = sa.inspect(bind)
    if "direct_messages" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_messages")
        if "ix_direct_messages_created_at" in indexes:
            op.drop_index("ix_direct_messages_created_at", table_name="direct_messages")

    inspector = sa.inspect(bind)
    if "direct_conversations" in _table_names(inspector):
        indexes = _index_names(inspector, "direct_conversations")
        for index_name in [
            "ix_direct_conversations_updated_at",
            "ix_direct_conversations_created_at",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="direct_conversations")

    inspector = sa.inspect(bind)
    if "friend_requests" in _table_names(inspector):
        indexes = _index_names(inspector, "friend_requests")
        for index_name in [
            "ix_friend_requests_updated_at",
            "ix_friend_requests_responded_at",
            "ix_friend_requests_created_at",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="friend_requests")

    inspector = sa.inspect(bind)
    if "users" in _table_names(inspector) and "messaging_permission" in _column_names(inspector, "users"):
        op.alter_column(
            "users",
            "messaging_permission",
            existing_type=sa.String(),
            existing_server_default=sa.text("'anyone'"),
            nullable=True,
        )
