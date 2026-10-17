"""Store source-matched prose section hierarchy for new imports.

Revision ID: 20261017_book_sections
Revises: 20260919_subscription_lifecycle
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "20261017_book_sections"
down_revision: str | Sequence[str] | None = "20260919_subscription_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "book_sections" not in set(inspector.get_table_names()):
        op.create_table(
            "book_sections",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("book_id", UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True),
            sa.Column("chapter_id", UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_section_id", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("source_label", sa.String(200), nullable=True),
            sa.Column("source_location", sa.String(255), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False),
            sa.Column("start_block", sa.Integer(), nullable=False),
            sa.Column("end_block", sa.Integer(), nullable=False),
            sa.Column("include_in_analysis", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("warnings", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.UniqueConstraint("chapter_id", name="uq_book_sections_chapter_id"),
        )
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("book_sections")}
    if "ix_book_sections_book_id" not in indexes:
        op.create_index("ix_book_sections_book_id", "book_sections", ["book_id"])
    if "ix_book_sections_book_order" not in indexes:
        op.create_index("ix_book_sections_book_order", "book_sections", ["book_id", "display_order"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "book_sections" in set(inspector.get_table_names()):
        indexes = {index["name"] for index in inspector.get_indexes("book_sections")}
        if "ix_book_sections_book_order" in indexes:
            op.drop_index("ix_book_sections_book_order", table_name="book_sections")
        if "ix_book_sections_book_id" in indexes:
            op.drop_index("ix_book_sections_book_id", table_name="book_sections")
        op.drop_table("book_sections")
