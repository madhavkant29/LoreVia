"""add saved book notes for author workspace

Revision ID: 9b7f41d5c2aa
Revises: f4c9e12a6b31
Create Date: 2026-04-23 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9b7f41d5c2aa"
down_revision = "f4c9e12a6b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "book_notes" in tables:
        return

    has_users = "users" in tables
    has_books = "books" in tables

    fk_constraints = []
    if has_users:
        fk_constraints.append(sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))
    if has_books:
        fk_constraints.append(sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"))

    op.create_table(
        "book_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *fk_constraints,
    )
    op.create_index("ix_book_notes_user_id", "book_notes", ["user_id"])
    op.create_index("ix_book_notes_book_id", "book_notes", ["book_id"])
    op.create_index("ix_book_notes_chapter_number", "book_notes", ["chapter_number"])
    op.create_index("ix_book_notes_created_at", "book_notes", ["created_at"])
    op.create_index("ix_book_notes_updated_at", "book_notes", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "book_notes" not in tables:
        return

    op.drop_index("ix_book_notes_updated_at", table_name="book_notes")
    op.drop_index("ix_book_notes_created_at", table_name="book_notes")
    op.drop_index("ix_book_notes_chapter_number", table_name="book_notes")
    op.drop_index("ix_book_notes_book_id", table_name="book_notes")
    op.drop_index("ix_book_notes_user_id", table_name="book_notes")
    op.drop_table("book_notes")
