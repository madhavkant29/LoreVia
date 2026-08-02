"""Add word-processing and source-storage allowance accounting.

Revision ID: 20260620_add_processing_allowances
Revises: 20260612_add_missing_user_metadata_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260620_add_processing_allowances"
down_revision: str | Sequence[str] | None = "20260612_add_missing_user_metadata_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    book_columns = {column["name"] for column in inspector.get_columns("books")}
    if "source_size_bytes" not in book_columns:
        op.add_column("books", sa.Column("source_size_bytes", sa.Integer(), nullable=True))

    world_columns = {column["name"] for column in inspector.get_columns("world_building_documents")}
    if "source_size_bytes" not in world_columns:
        op.add_column(
            "world_building_documents", sa.Column("source_size_bytes", sa.Integer(), nullable=True)
        )

    chapter_indexes = {index["name"] for index in inspector.get_indexes("chapters")}
    if "ix_chapters_book_id_number" not in chapter_indexes:
        op.create_index("ix_chapters_book_id_number", "chapters", ["book_id", "number"])

    if "processing_usage_events" not in tables:
        op.create_table(
            "processing_usage_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("usage_kind", sa.String(), nullable=False),
            sa.Column("source_id", sa.String(), nullable=False),
            sa.Column("word_count", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), server_default="reserved", nullable=False),
            sa.Column(
                "reserved_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "usage_kind", "source_id", name="uq_processing_usage_events_source"
            ),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("processing_usage_events")}
    for name, columns in (
        ("ix_processing_usage_events_user_id", ["user_id"]),
        ("ix_processing_usage_events_book_id", ["book_id"]),
        ("ix_processing_usage_events_usage_kind", ["usage_kind"]),
        ("ix_processing_usage_events_task_id", ["task_id"]),
        ("ix_processing_usage_events_status", ["status"]),
        ("ix_processing_usage_events_created_at", ["created_at"]),
        ("ix_processing_usage_events_user_status_reserved", ["user_id", "status", "reserved_at"]),
    ):
        if name not in indexes:
            op.create_index(name, "processing_usage_events", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "processing_usage_events" in tables:
        op.drop_table("processing_usage_events")

    if "chapters" in tables:
        chapter_indexes = {index["name"] for index in inspector.get_indexes("chapters")}
        if "ix_chapters_book_id_number" in chapter_indexes:
            op.drop_index("ix_chapters_book_id_number", table_name="chapters")

    inspector = sa.inspect(bind)
    if "world_building_documents" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("world_building_documents")}
        if "source_size_bytes" in columns:
            op.drop_column("world_building_documents", "source_size_bytes")
    if "books" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "source_size_bytes" in columns:
            op.drop_column("books", "source_size_bytes")
