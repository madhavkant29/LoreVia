"""Add beta read feedback questions and review items.

Revision ID: 20260514_add_beta_read_feedback
Revises: 1a70eda4d48c
Create Date: 2026-05-14 09:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_beta_read_feedback"
down_revision: str | None = "1a70eda4d48c"
branch_labels = None
depends_on = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" in tables:
        assignment_columns = _column_names(inspector, "beta_read_assignments")
        if "required_feedback_item_count" not in assignment_columns:
            op.add_column(
                "beta_read_assignments",
                sa.Column("required_feedback_item_count", sa.Integer(), nullable=False, server_default="1"),
            )

    if "beta_read_questions" not in tables:
        op.create_table(
            "beta_read_questions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "assignment_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("beta_read_assignments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "author_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        tables.add("beta_read_questions")

    if "beta_read_feedback_items" not in tables:
        op.create_table(
            "beta_read_feedback_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "assignment_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("beta_read_assignments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "author_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "reader_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "question_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("beta_read_questions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "scene_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("novel_scenes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("reaction", sa.String(), nullable=True),
            sa.Column("anchor_text", sa.Text(), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        tables.add("beta_read_feedback_items")

    if "beta_read_questions" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_questions")
        for name, columns in (
            ("ix_beta_read_questions_assignment_id", ["assignment_id"]),
            ("ix_beta_read_questions_book_id", ["book_id"]),
            ("ix_beta_read_questions_author_user_id", ["author_user_id"]),
            ("ix_beta_read_questions_created_at", ["created_at"]),
            ("ix_beta_read_questions_updated_at", ["updated_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "beta_read_questions", columns)

    if "beta_read_feedback_items" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_feedback_items")
        for name, columns in (
            ("ix_beta_read_feedback_items_assignment_id", ["assignment_id"]),
            ("ix_beta_read_feedback_items_book_id", ["book_id"]),
            ("ix_beta_read_feedback_items_author_user_id", ["author_user_id"]),
            ("ix_beta_read_feedback_items_reader_user_id", ["reader_user_id"]),
            ("ix_beta_read_feedback_items_question_id", ["question_id"]),
            ("ix_beta_read_feedback_items_scene_id", ["scene_id"]),
            ("ix_beta_read_feedback_items_kind", ["kind"]),
            ("ix_beta_read_feedback_items_chapter_number", ["chapter_number"]),
            ("ix_beta_read_feedback_items_created_at", ["created_at"]),
            ("ix_beta_read_feedback_items_updated_at", ["updated_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "beta_read_feedback_items", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_feedback_items" in tables:
        indexes = _index_names(inspector, "beta_read_feedback_items")
        for index_name in (
            "ix_beta_read_feedback_items_updated_at",
            "ix_beta_read_feedback_items_created_at",
            "ix_beta_read_feedback_items_chapter_number",
            "ix_beta_read_feedback_items_kind",
            "ix_beta_read_feedback_items_scene_id",
            "ix_beta_read_feedback_items_question_id",
            "ix_beta_read_feedback_items_reader_user_id",
            "ix_beta_read_feedback_items_author_user_id",
            "ix_beta_read_feedback_items_book_id",
            "ix_beta_read_feedback_items_assignment_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="beta_read_feedback_items")
        op.drop_table("beta_read_feedback_items")

    if "beta_read_questions" in tables:
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_questions")
        for index_name in (
            "ix_beta_read_questions_updated_at",
            "ix_beta_read_questions_created_at",
            "ix_beta_read_questions_author_user_id",
            "ix_beta_read_questions_book_id",
            "ix_beta_read_questions_assignment_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="beta_read_questions")
        op.drop_table("beta_read_questions")

    if "beta_read_assignments" in tables:
        inspector = sa.inspect(bind)
        assignment_columns = _column_names(inspector, "beta_read_assignments")
        if "required_feedback_item_count" in assignment_columns:
            op.drop_column("beta_read_assignments", "required_feedback_item_count")
