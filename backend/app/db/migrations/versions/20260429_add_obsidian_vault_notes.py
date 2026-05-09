"""Add persisted Obsidian vault notes.

Revision ID: 20260429_obsidian_notes
Revises: 20260429_rebuild_public_schema
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260429_obsidian_notes"
down_revision: str | None = "20260429_rebuild_public_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "book_obsidian_notes" not in tables:
        op.create_table(
            "book_obsidian_notes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "book_id", "path", name="uq_book_obsidian_notes_user_book_path"),
        )
        inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("book_obsidian_notes")}
    if "user_id" in columns:
        indexes = {idx["name"] for idx in inspector.get_indexes("book_obsidian_notes")}
        if "ix_book_obsidian_notes_user_id" not in indexes:
            op.create_index("ix_book_obsidian_notes_user_id", "book_obsidian_notes", ["user_id"])
        if "ix_book_obsidian_notes_book_id" not in indexes:
            op.create_index("ix_book_obsidian_notes_book_id", "book_obsidian_notes", ["book_id"])
        if "ix_book_obsidian_notes_path" not in indexes:
            op.create_index("ix_book_obsidian_notes_path", "book_obsidian_notes", ["path"])
        if "ix_book_obsidian_notes_created_at" not in indexes:
            op.create_index("ix_book_obsidian_notes_created_at", "book_obsidian_notes", ["created_at"])
        if "ix_book_obsidian_notes_updated_at" not in indexes:
            op.create_index("ix_book_obsidian_notes_updated_at", "book_obsidian_notes", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "book_obsidian_notes" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("book_obsidian_notes")}
    for index_name in [
        "ix_book_obsidian_notes_updated_at",
        "ix_book_obsidian_notes_created_at",
        "ix_book_obsidian_notes_path",
        "ix_book_obsidian_notes_book_id",
        "ix_book_obsidian_notes_user_id",
    ]:
        if index_name in indexes:
            op.drop_index(index_name, table_name="book_obsidian_notes")
    op.drop_table("book_obsidian_notes")
