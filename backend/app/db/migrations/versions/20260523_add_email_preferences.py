"""Add email preferences table for promotional email compliance.

Revision ID: 20260523_add_email_preferences
Revises: 20260522_merge_forum_and_relationship_heads
Create Date: 2026-05-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260523_add_email_preferences"
down_revision: str | Sequence[str] | None = "20260522_merge_forum_and_relationship_heads"
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


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for constraint in inspector.get_unique_constraints(table_name)
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "email_preferences" not in tables:
        op.create_table(
            "email_preferences",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("product_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("marketing", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("unsubscribed_all", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_email_preferences_user_id"),
            sa.UniqueConstraint("email", name="uq_email_preferences_email"),
        )

    inspector = sa.inspect(bind)
    if "email_preferences" not in _table_names(inspector):
        return

    columns = _column_names(inspector, "email_preferences")
    if "unsubscribed_at" not in columns:
        op.add_column("email_preferences", sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))

    indexes = _index_names(inspector, "email_preferences")
    for index_name, column_names in (
        ("ix_email_preferences_user_id", ["user_id"]),
        ("ix_email_preferences_email", ["email"]),
        ("ix_email_preferences_created_at", ["created_at"]),
        ("ix_email_preferences_updated_at", ["updated_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "email_preferences", column_names)

    constraints = _unique_constraint_names(inspector, "email_preferences")
    if "uq_email_preferences_user_id" not in constraints:
        op.create_unique_constraint("uq_email_preferences_user_id", "email_preferences", ["user_id"])
    if "uq_email_preferences_email" not in constraints:
        op.create_unique_constraint("uq_email_preferences_email", "email_preferences", ["email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "email_preferences" not in tables:
        return

    indexes = _index_names(inspector, "email_preferences")
    for index_name in (
        "ix_email_preferences_updated_at",
        "ix_email_preferences_created_at",
        "ix_email_preferences_email",
        "ix_email_preferences_user_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="email_preferences")

    op.drop_table("email_preferences")
