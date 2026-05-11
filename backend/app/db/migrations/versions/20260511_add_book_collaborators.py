"""Add story-aware book collaborators.

Revision ID: 20260511_add_book_collaborators
Revises: 6d6a849ebcbb
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260511_add_book_collaborators"
down_revision: str | None = "6d6a849ebcbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_collaborators" not in tables:
        op.create_table(
            "book_collaborators",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("invited_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("role", sa.String(), server_default="viewer", nullable=False),
            sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=True),
            sa.Column("invite_status", sa.String(), server_default="active", nullable=False),
            sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["invited_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "email", name="uq_book_collaborators_book_email"),
        )
        tables.add("book_collaborators")

    if "book_collaborators" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("book_collaborators")}
        if "ix_book_collaborators_book_id" not in indexes:
            op.create_index("ix_book_collaborators_book_id", "book_collaborators", ["book_id"])
        if "ix_book_collaborators_email" not in indexes:
            op.create_index("ix_book_collaborators_email", "book_collaborators", ["email"])
        if "ix_book_collaborators_invited_user_id" not in indexes:
            op.create_index("ix_book_collaborators_invited_user_id", "book_collaborators", ["invited_user_id"])
        if "ix_book_collaborators_invite_status" not in indexes:
            op.create_index("ix_book_collaborators_invite_status", "book_collaborators", ["invite_status"])
        if "ix_book_collaborators_invited_at" not in indexes:
            op.create_index("ix_book_collaborators_invited_at", "book_collaborators", ["invited_at"])
        if "ix_book_collaborators_role" not in indexes:
            op.create_index("ix_book_collaborators_role", "book_collaborators", ["role"])
        if "ix_book_collaborators_updated_at" not in indexes:
            op.create_index("ix_book_collaborators_updated_at", "book_collaborators", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_collaborators" in tables:
        op.drop_table("book_collaborators")
