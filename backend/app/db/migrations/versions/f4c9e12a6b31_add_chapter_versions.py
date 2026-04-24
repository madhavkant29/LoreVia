"""add chapter versions for manuscript revision history

Revision ID: f4c9e12a6b31
Revises: e5f1a8b27c44
Create Date: 2026-04-22 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4c9e12a6b31"
down_revision = "e5f1a8b27c44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chapter_versions" in tables:
        return

    op.create_table(
        "chapter_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("s3_key", sa.String(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chapter_versions_book_id", "chapter_versions", ["book_id"])
    op.create_index("ix_chapter_versions_chapter_id", "chapter_versions", ["chapter_id"])
    op.create_index("ix_chapter_versions_chapter_number", "chapter_versions", ["chapter_number"])
    op.create_index("ix_chapter_versions_created_at", "chapter_versions", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chapter_versions" not in tables:
        return

    op.drop_index("ix_chapter_versions_created_at", table_name="chapter_versions")
    op.drop_index("ix_chapter_versions_chapter_number", table_name="chapter_versions")
    op.drop_index("ix_chapter_versions_chapter_id", table_name="chapter_versions")
    op.drop_index("ix_chapter_versions_book_id", table_name="chapter_versions")
    op.drop_table("chapter_versions")
