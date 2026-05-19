"""Normalize collaboration access and beta-read submission state.

Revision ID: 20260515_normalize_collab_beta_state
Revises: 20260514_add_public_forum_reputation_profiles
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260515_normalize_collab_beta_state"
down_revision: str | None = "20260514_add_public_forum_reputation_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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

    if "book_collaborators" in tables:
        columns = _column_names(inspector, "book_collaborators")
        collaborator_columns: list[sa.Column] = [
            sa.Column("scope_chapter_start", sa.Integer(), nullable=True),
            sa.Column("scope_chapter_end", sa.Integer(), nullable=True),
            sa.Column("scope_character_bible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("scope_continuity_report", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("scope_reader_confusion_report", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_edit_manuscript", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_view_story_bible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_run_ai_scans", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_export", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_comment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("permission_can_view_selected_chapters_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        ]
        for column in collaborator_columns:
            if column.name not in columns:
                op.add_column("book_collaborators", column)

        op.execute(
            sa.text(
                """
                UPDATE book_collaborators
                SET
                    scope_chapter_start = CASE
                        WHEN scope ? 'chapter_start' AND nullif(scope->>'chapter_start', '') IS NOT NULL
                            THEN (scope->>'chapter_start')::integer
                        ELSE NULL
                    END,
                    scope_chapter_end = CASE
                        WHEN scope ? 'chapter_end' AND nullif(scope->>'chapter_end', '') IS NOT NULL
                            THEN (scope->>'chapter_end')::integer
                        ELSE NULL
                    END,
                    scope_character_bible = COALESCE((scope->>'character_bible')::boolean, false),
                    scope_continuity_report = COALESCE((scope->>'continuity_report')::boolean, false),
                    scope_reader_confusion_report = COALESCE((scope->>'reader_confusion_report')::boolean, false),
                    permission_can_edit_manuscript = COALESCE((permissions->>'can_edit_manuscript')::boolean, false),
                    permission_can_view_story_bible = COALESCE((permissions->>'can_view_story_bible')::boolean, false),
                    permission_can_run_ai_scans = COALESCE((permissions->>'can_run_ai_scans')::boolean, false),
                    permission_can_export = COALESCE((permissions->>'can_export')::boolean, false),
                    permission_can_comment = COALESCE((permissions->>'can_comment')::boolean, false),
                    permission_can_view_selected_chapters_only = COALESCE((permissions->>'can_view_selected_chapters_only')::boolean, false)
                """
            )
        )

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" in tables:
        columns = _column_names(inspector, "beta_read_assignments")
        assignment_columns: list[sa.Column] = [
            sa.Column("submitted_progress_pct", sa.Float(), nullable=True),
            sa.Column("submitted_chapters_total", sa.Integer(), nullable=True),
            sa.Column("submitted_chapters_read_count", sa.Integer(), nullable=True),
            sa.Column("submitted_comment_count", sa.Integer(), nullable=True),
            sa.Column("submitted_feedback_item_count", sa.Integer(), nullable=True),
            sa.Column("submitted_answer_count", sa.Integer(), nullable=True),
            sa.Column("submitted_rating_sentiment", sa.String(), nullable=True),
            sa.Column("submitted_before_deadline", sa.Boolean(), nullable=True),
            sa.Column("late_feedback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        ]
        for column in assignment_columns:
            if column.name not in columns:
                op.add_column("beta_read_assignments", column)

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_submitted_rating_sentiment" not in indexes:
            op.create_index(
                "ix_beta_read_assignments_submitted_rating_sentiment",
                "beta_read_assignments",
                ["submitted_rating_sentiment"],
            )

        op.execute(
            sa.text(
                """
                UPDATE beta_read_assignments
                SET
                    submitted_progress_pct = CASE
                        WHEN submission_metadata ? 'progress_pct' THEN (submission_metadata->>'progress_pct')::double precision
                        ELSE NULL
                    END,
                    submitted_chapters_total = CASE
                        WHEN submission_metadata ? 'chapters_total' THEN (submission_metadata->>'chapters_total')::integer
                        ELSE NULL
                    END,
                    submitted_chapters_read_count = CASE
                        WHEN submission_metadata ? 'chapters_read_count' THEN (submission_metadata->>'chapters_read_count')::integer
                        ELSE NULL
                    END,
                    submitted_comment_count = CASE
                        WHEN submission_metadata ? 'comment_count' THEN (submission_metadata->>'comment_count')::integer
                        ELSE NULL
                    END,
                    submitted_feedback_item_count = CASE
                        WHEN submission_metadata ? 'feedback_item_count' THEN (submission_metadata->>'feedback_item_count')::integer
                        ELSE NULL
                    END,
                    submitted_answer_count = CASE
                        WHEN submission_metadata ? 'answer_count' THEN (submission_metadata->>'answer_count')::integer
                        ELSE NULL
                    END,
                    submitted_rating_sentiment = nullif(submission_metadata->>'rating_sentiment', ''),
                    submitted_before_deadline = CASE
                        WHEN submission_metadata ? 'submitted_before_deadline' THEN (submission_metadata->>'submitted_before_deadline')::boolean
                        ELSE NULL
                    END,
                    late_feedback = COALESCE((submission_metadata->>'late_feedback')::boolean, false)
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "beta_read_assignments" in tables:
        indexes = _index_names(inspector, "beta_read_assignments")
        if "ix_beta_read_assignments_submitted_rating_sentiment" in indexes:
            op.drop_index("ix_beta_read_assignments_submitted_rating_sentiment", table_name="beta_read_assignments")

        columns = _column_names(inspector, "beta_read_assignments")
        for column_name in (
            "late_feedback",
            "submitted_before_deadline",
            "submitted_rating_sentiment",
            "submitted_answer_count",
            "submitted_feedback_item_count",
            "submitted_comment_count",
            "submitted_chapters_read_count",
            "submitted_chapters_total",
            "submitted_progress_pct",
        ):
            if column_name in columns:
                op.drop_column("beta_read_assignments", column_name)

    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_collaborators" in tables:
        columns = _column_names(inspector, "book_collaborators")
        for column_name in (
            "permission_can_view_selected_chapters_only",
            "permission_can_comment",
            "permission_can_export",
            "permission_can_run_ai_scans",
            "permission_can_view_story_bible",
            "permission_can_edit_manuscript",
            "scope_reader_confusion_report",
            "scope_continuity_report",
            "scope_character_bible",
            "scope_chapter_end",
            "scope_chapter_start",
        ):
            if column_name in columns:
                op.drop_column("book_collaborators", column_name)
