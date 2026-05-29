"""add advisor_suggestion_jobs table for async scan pattern

Revision ID: a1b2c3d4e5f6
Revises: f4c9e12a6b31
Create Date: 2026-05-29 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "f4c9e12a6b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "advisor_suggestion_jobs" in tables:
        return

    has_users = "users" in tables
    has_books = "books" in tables

    fk_constraints = []
    if has_users:
        fk_constraints.append(sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"))
    if has_books:
        fk_constraints.append(sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"))

    op.create_table(
        "advisor_suggestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("cache_key", sa.String(), nullable=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *fk_constraints,
    )
    op.create_index("ix_advisor_suggestion_jobs_user_id", "advisor_suggestion_jobs", ["user_id"])
    op.create_index("ix_advisor_suggestion_jobs_book_id", "advisor_suggestion_jobs", ["book_id"])
    op.create_index("ix_advisor_suggestion_jobs_status", "advisor_suggestion_jobs", ["status"])
    op.create_index("ix_advisor_suggestion_jobs_cache_key", "advisor_suggestion_jobs", ["cache_key"])
    op.create_index("ix_advisor_suggestion_jobs_error_code", "advisor_suggestion_jobs", ["error_code"])
    op.create_index("ix_advisor_suggestion_jobs_created_at", "advisor_suggestion_jobs", ["created_at"])
    op.create_index("ix_advisor_suggestion_jobs_updated_at", "advisor_suggestion_jobs", ["updated_at"])
    op.create_index("ix_advisor_suggestion_jobs_expires_at", "advisor_suggestion_jobs", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "advisor_suggestion_jobs" not in tables:
        return

    op.drop_index("ix_advisor_suggestion_jobs_expires_at", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_updated_at", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_created_at", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_error_code", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_cache_key", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_status", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_book_id", table_name="advisor_suggestion_jobs")
    op.drop_index("ix_advisor_suggestion_jobs_user_id", table_name="advisor_suggestion_jobs")
    op.drop_table("advisor_suggestion_jobs")
