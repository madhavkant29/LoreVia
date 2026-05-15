"""Add beta read assignments and reader penalty tracking.

Revision ID: 20260514_add_beta_read_assignments
Revises: 20260513_add_collaboration_permissions
Create Date: 2026-05-14 02:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260514_add_beta_read_assignments"
down_revision: str | None = "20260513_add_collaboration_permissions"
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

    if "beta_read_assignments" not in tables:
        op.create_table(
            "beta_read_assignments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reader_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("collaborator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_collaborators.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reader_email", sa.String(), nullable=False),
            sa.Column("state", sa.String(), nullable=False, server_default="active"),
            sa.Column("scope_kind", sa.String(), nullable=False, server_default="full_book"),
            sa.Column("task_label", sa.String(), nullable=False),
            sa.Column("section_label", sa.String(), nullable=True),
            sa.Column("chapter_start", sa.Integer(), nullable=True),
            sa.Column("chapter_end", sa.Integer(), nullable=True),
            sa.Column("window_days", sa.Integer(), nullable=False),
            sa.Column("reward_points", sa.Integer(), nullable=False),
            sa.Column("required_progress_pct", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("required_comment_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("require_final_feedback", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("author_questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("access_granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("first_opened_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("awarded_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("final_feedback", sa.Text(), nullable=True),
            sa.Column("feedback_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("submission_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reminder_6h_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("missed_reason", sa.String(), nullable=True),
            sa.Column("counted_toward_missed_streak", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_reason", sa.String(), nullable=True),
            sa.Column("disqualified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disqualified_reason", sa.String(), nullable=True),
            sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        tables.add("beta_read_assignments")

    if "beta_read_assignments" in tables:
        columns = _column_names(inspector, "beta_read_assignments")
        if "author_questions_json" not in columns:
            op.add_column(
                "beta_read_assignments",
                sa.Column("author_questions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            )
        if "feedback_payload" not in columns:
            op.add_column(
                "beta_read_assignments",
                sa.Column("feedback_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            )
        indexes = _index_names(inspector, "beta_read_assignments")
        for name, columns in (
            ("ix_beta_read_assignments_book_id", ["book_id"]),
            ("ix_beta_read_assignments_author_user_id", ["author_user_id"]),
            ("ix_beta_read_assignments_reader_user_id", ["reader_user_id"]),
            ("ix_beta_read_assignments_collaborator_id", ["collaborator_id"]),
            ("ix_beta_read_assignments_reader_email", ["reader_email"]),
            ("ix_beta_read_assignments_state", ["state"]),
            ("ix_beta_read_assignments_starts_at", ["starts_at"]),
            ("ix_beta_read_assignments_expires_at", ["expires_at"]),
            ("ix_beta_read_assignments_access_granted_at", ["access_granted_at"]),
            ("ix_beta_read_assignments_first_opened_at", ["first_opened_at"]),
            ("ix_beta_read_assignments_submitted_at", ["submitted_at"]),
            ("ix_beta_read_assignments_completed_at", ["completed_at"]),
            ("ix_beta_read_assignments_awarded_at", ["awarded_at"]),
            ("ix_beta_read_assignments_reminder_24h_sent_at", ["reminder_24h_sent_at"]),
            ("ix_beta_read_assignments_reminder_6h_sent_at", ["reminder_6h_sent_at"]),
            ("ix_beta_read_assignments_missed_reason", ["missed_reason"]),
            ("ix_beta_read_assignments_revoked_at", ["revoked_at"]),
            ("ix_beta_read_assignments_disqualified_at", ["disqualified_at"]),
            ("ix_beta_read_assignments_state_changed_at", ["state_changed_at"]),
            ("ix_beta_read_assignments_created_at", ["created_at"]),
            ("ix_beta_read_assignments_updated_at", ["updated_at"]),
        ):
            if name not in indexes:
                op.create_index(name, "beta_read_assignments", columns)

    if "users" in tables:
        columns = _column_names(inspector, "users")
        if "consecutive_missed_beta_reads" not in columns:
            op.add_column("users", sa.Column("consecutive_missed_beta_reads", sa.Integer(), nullable=False, server_default="0"))
        if "beta_read_penalty_status" not in columns:
            op.add_column("users", sa.Column("beta_read_penalty_status", sa.String(), nullable=False, server_default="none"))
        if "beta_read_penalty_required_at" not in columns:
            op.add_column("users", sa.Column("beta_read_penalty_required_at", sa.DateTime(timezone=True), nullable=True))

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "users")
        if "ix_users_beta_read_penalty_required_at" not in indexes:
            op.create_index("ix_users_beta_read_penalty_required_at", "users", ["beta_read_penalty_required_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "users" in tables:
        indexes = _index_names(inspector, "users")
        if "ix_users_beta_read_penalty_required_at" in indexes:
            op.drop_index("ix_users_beta_read_penalty_required_at", table_name="users")

        columns = _column_names(inspector, "users")
        if "beta_read_penalty_required_at" in columns:
            op.drop_column("users", "beta_read_penalty_required_at")
        if "beta_read_penalty_status" in columns:
            op.drop_column("users", "beta_read_penalty_status")
        if "consecutive_missed_beta_reads" in columns:
            op.drop_column("users", "consecutive_missed_beta_reads")

    if "beta_read_assignments" in tables:
        columns = _column_names(inspector, "beta_read_assignments")
        if "feedback_payload" in columns:
            op.drop_column("beta_read_assignments", "feedback_payload")
        if "author_questions_json" in columns:
            op.drop_column("beta_read_assignments", "author_questions_json")
        indexes = _index_names(inspector, "beta_read_assignments")
        for index_name in (
            "ix_beta_read_assignments_updated_at",
            "ix_beta_read_assignments_created_at",
            "ix_beta_read_assignments_state_changed_at",
            "ix_beta_read_assignments_disqualified_at",
            "ix_beta_read_assignments_revoked_at",
            "ix_beta_read_assignments_missed_reason",
            "ix_beta_read_assignments_reminder_6h_sent_at",
            "ix_beta_read_assignments_reminder_24h_sent_at",
            "ix_beta_read_assignments_awarded_at",
            "ix_beta_read_assignments_completed_at",
            "ix_beta_read_assignments_submitted_at",
            "ix_beta_read_assignments_first_opened_at",
            "ix_beta_read_assignments_access_granted_at",
            "ix_beta_read_assignments_expires_at",
            "ix_beta_read_assignments_starts_at",
            "ix_beta_read_assignments_state",
            "ix_beta_read_assignments_reader_email",
            "ix_beta_read_assignments_collaborator_id",
            "ix_beta_read_assignments_reader_user_id",
            "ix_beta_read_assignments_author_user_id",
            "ix_beta_read_assignments_book_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="beta_read_assignments")
        op.drop_table("beta_read_assignments")
