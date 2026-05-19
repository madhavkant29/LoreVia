"""Add public book safety, reporting, and moderation fields.

Revision ID: 20260519_add_public_book_safety_moderation
Revises: 20260518_add_analysis_state_and_character_metadata
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260519_add_public_book_safety_moderation"
down_revision: str | None = "20260518_add_analysis_state_and_character_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = _column_names(inspector, "books")
        indexes = _index_names(inspector, "books")
        unique_constraints = _unique_constraint_names(inspector, "books")
        book_columns: list[tuple[str, sa.Column]] = [
            ("public_status", sa.Column("public_status", sa.String(), nullable=False, server_default="draft")),
            ("public_slug", sa.Column("public_slug", sa.String(), nullable=True)),
            ("published_at", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)),
            ("public_visibility", sa.Column("public_visibility", sa.String(), nullable=False, server_default="private")),
            ("rights_confirmation", sa.Column("rights_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
            ("rights_confirmation_at", sa.Column("rights_confirmation_at", sa.DateTime(timezone=True), nullable=True)),
            ("rights_confirmation_ip_hash", sa.Column("rights_confirmation_ip_hash", sa.String(), nullable=True)),
            ("rights_confirmation_user_agent", sa.Column("rights_confirmation_user_agent", sa.Text(), nullable=True)),
            ("content_source_type", sa.Column("content_source_type", sa.String(), nullable=False, server_default="user_original")),
            ("moderation_status", sa.Column("moderation_status", sa.String(), nullable=False, server_default="clean")),
            ("moderation_reason", sa.Column("moderation_reason", sa.Text(), nullable=True)),
            ("takedown_reason", sa.Column("takedown_reason", sa.Text(), nullable=True)),
            ("takedown_at", sa.Column("takedown_at", sa.DateTime(timezone=True), nullable=True)),
            ("takedown_by_user_id", sa.Column("takedown_by_user_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("public_upload_counted_at", sa.Column("public_upload_counted_at", sa.DateTime(timezone=True), nullable=True)),
            ("source_title", sa.Column("source_title", sa.String(), nullable=True)),
            ("source_author", sa.Column("source_author", sa.String(), nullable=True)),
            ("source_public_domain_note", sa.Column("source_public_domain_note", sa.Text(), nullable=True)),
            ("source_url", sa.Column("source_url", sa.Text(), nullable=True)),
        ]
        for column_name, column in book_columns:
            if column_name not in columns:
                op.add_column("books", column)
        if "takedown_by_user_id" in _column_names(inspector, "books"):
            foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("books")}
            if "fk_books_takedown_by_user_id_users" not in foreign_keys:
                op.create_foreign_key(
                    "fk_books_takedown_by_user_id_users",
                    "books",
                    "users",
                    ["takedown_by_user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "books")
        unique_constraints = _unique_constraint_names(inspector, "books")
        for index_name, column_name in [
            ("ix_books_public_status", "public_status"),
            ("ix_books_public_slug", "public_slug"),
            ("ix_books_published_at", "published_at"),
            ("ix_books_public_visibility", "public_visibility"),
            ("ix_books_content_source_type", "content_source_type"),
            ("ix_books_moderation_status", "moderation_status"),
            ("ix_books_takedown_at", "takedown_at"),
            ("ix_books_takedown_by_user_id", "takedown_by_user_id"),
            ("ix_books_public_upload_counted_at", "public_upload_counted_at"),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "books", [column_name], unique=False)
        if "uq_books_public_slug" not in unique_constraints:
            op.create_unique_constraint("uq_books_public_slug", "books", ["public_slug"])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "content_reports" not in tables:
        op.create_table(
            "content_reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("reporter_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reporter_email", sa.String(), nullable=True),
            sa.Column("reporter_ip_hash", sa.String(), nullable=True),
            sa.Column("reported_book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reported_author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("report_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("copyright_owner_name", sa.String(), nullable=True),
            sa.Column("copyright_work_description", sa.Text(), nullable=True),
            sa.Column("copyright_original_url", sa.Text(), nullable=True),
            sa.Column("reported_content_url", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
        )
    inspector = sa.inspect(bind)
    if "content_reports" in inspector.get_table_names():
        indexes = _index_names(inspector, "content_reports")
        for index_name, columns in [
            ("ix_content_reports_reporter_user_id", ["reporter_user_id"]),
            ("ix_content_reports_reporter_email", ["reporter_email"]),
            ("ix_content_reports_reporter_ip_hash", ["reporter_ip_hash"]),
            ("ix_content_reports_reported_book_id", ["reported_book_id"]),
            ("ix_content_reports_reported_author_user_id", ["reported_author_user_id"]),
            ("ix_content_reports_report_type", ["report_type"]),
            ("ix_content_reports_status", ["status"]),
            ("ix_content_reports_created_at", ["created_at"]),
            ("ix_content_reports_updated_at", ["updated_at"]),
            ("ix_content_reports_resolved_at", ["resolved_at"]),
            ("ix_content_reports_resolved_by_user_id", ["resolved_by_user_id"]),
            ("ix_content_reports_book_status_created_at", ["reported_book_id", "status", "created_at"]),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "content_reports", columns, unique=False)

    if "creator_strikes" not in tables:
        op.create_table(
            "creator_strikes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
            sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_reports.id", ondelete="SET NULL"), nullable=True),
            sa.Column("strike_type", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
    inspector = sa.inspect(bind)
    if "creator_strikes" in inspector.get_table_names():
        indexes = _index_names(inspector, "creator_strikes")
        for index_name, columns in [
            ("ix_creator_strikes_user_id", ["user_id"]),
            ("ix_creator_strikes_book_id", ["book_id"]),
            ("ix_creator_strikes_report_id", ["report_id"]),
            ("ix_creator_strikes_strike_type", ["strike_type"]),
            ("ix_creator_strikes_severity", ["severity"]),
            ("ix_creator_strikes_created_at", ["created_at"]),
            ("ix_creator_strikes_created_by_user_id", ["created_by_user_id"]),
            ("ix_creator_strikes_expires_at", ["expires_at"]),
            ("ix_creator_strikes_is_active", ["is_active"]),
            ("ix_creator_strikes_user_active_created_at", ["user_id", "is_active", "created_at"]),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "creator_strikes", columns, unique=False)

    if "moderation_actions" not in tables:
        op.create_table(
            "moderation_actions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
            sa.Column("report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_reports.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("previous_status", sa.String(), nullable=True),
            sa.Column("new_status", sa.String(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
        )
    inspector = sa.inspect(bind)
    if "moderation_actions" in inspector.get_table_names():
        indexes = _index_names(inspector, "moderation_actions")
        for index_name, columns in [
            ("ix_moderation_actions_actor_user_id", ["actor_user_id"]),
            ("ix_moderation_actions_target_user_id", ["target_user_id"]),
            ("ix_moderation_actions_book_id", ["book_id"]),
            ("ix_moderation_actions_report_id", ["report_id"]),
            ("ix_moderation_actions_action_type", ["action_type"]),
            ("ix_moderation_actions_created_at", ["created_at"]),
            ("ix_moderation_actions_book_created_at", ["book_id", "created_at"]),
            ("ix_moderation_actions_report_created_at", ["report_id", "created_at"]),
        ]:
            if index_name not in indexes:
                op.create_index(index_name, "moderation_actions", columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "moderation_actions" in tables:
        indexes = _index_names(inspector, "moderation_actions")
        for index_name in [
            "ix_moderation_actions_report_created_at",
            "ix_moderation_actions_book_created_at",
            "ix_moderation_actions_created_at",
            "ix_moderation_actions_action_type",
            "ix_moderation_actions_report_id",
            "ix_moderation_actions_book_id",
            "ix_moderation_actions_target_user_id",
            "ix_moderation_actions_actor_user_id",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="moderation_actions")
        op.drop_table("moderation_actions")

    inspector = sa.inspect(bind)
    if "creator_strikes" in inspector.get_table_names():
        indexes = _index_names(inspector, "creator_strikes")
        for index_name in [
            "ix_creator_strikes_user_active_created_at",
            "ix_creator_strikes_is_active",
            "ix_creator_strikes_expires_at",
            "ix_creator_strikes_created_by_user_id",
            "ix_creator_strikes_created_at",
            "ix_creator_strikes_severity",
            "ix_creator_strikes_strike_type",
            "ix_creator_strikes_report_id",
            "ix_creator_strikes_book_id",
            "ix_creator_strikes_user_id",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="creator_strikes")
        op.drop_table("creator_strikes")

    inspector = sa.inspect(bind)
    if "content_reports" in inspector.get_table_names():
        indexes = _index_names(inspector, "content_reports")
        for index_name in [
            "ix_content_reports_book_status_created_at",
            "ix_content_reports_resolved_by_user_id",
            "ix_content_reports_resolved_at",
            "ix_content_reports_updated_at",
            "ix_content_reports_created_at",
            "ix_content_reports_status",
            "ix_content_reports_report_type",
            "ix_content_reports_reported_author_user_id",
            "ix_content_reports_reported_book_id",
            "ix_content_reports_reporter_ip_hash",
            "ix_content_reports_reporter_email",
            "ix_content_reports_reporter_user_id",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="content_reports")
        op.drop_table("content_reports")

    inspector = sa.inspect(bind)
    if "books" in inspector.get_table_names():
        indexes = _index_names(inspector, "books")
        unique_constraints = _unique_constraint_names(inspector, "books")
        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("books")}
        if "fk_books_takedown_by_user_id_users" in foreign_keys:
            op.drop_constraint("fk_books_takedown_by_user_id_users", "books", type_="foreignkey")
        if "uq_books_public_slug" in unique_constraints:
            op.drop_constraint("uq_books_public_slug", "books", type_="unique")
        for index_name in [
            "ix_books_public_upload_counted_at",
            "ix_books_takedown_by_user_id",
            "ix_books_takedown_at",
            "ix_books_moderation_status",
            "ix_books_content_source_type",
            "ix_books_public_visibility",
            "ix_books_published_at",
            "ix_books_public_slug",
            "ix_books_public_status",
        ]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="books")
        columns = _column_names(inspector, "books")
        for column_name in [
            "source_url",
            "source_public_domain_note",
            "source_author",
            "source_title",
            "public_upload_counted_at",
            "takedown_by_user_id",
            "takedown_at",
            "takedown_reason",
            "moderation_reason",
            "moderation_status",
            "content_source_type",
            "rights_confirmation_user_agent",
            "rights_confirmation_ip_hash",
            "rights_confirmation_at",
            "rights_confirmation",
            "public_visibility",
            "published_at",
            "public_slug",
            "public_status",
        ]:
            if column_name in columns:
                op.drop_column("books", column_name)
