"""Add durable backend-only world analysis snapshots and source observations.

Revision ID: 20260912_add_world_analysis_snapshots
Revises: 20260912_add_reader_events
Create Date: 2026-09-12

The tables are intentionally not granted through the Supabase Data API. They
hold service-owned refresh state and derived source observations; source data
is backfilled by bounded refresh workers rather than this schema revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260912_add_world_analysis_snapshots"
down_revision: str | Sequence[str] | None = "20260912_add_reader_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for column in inspector.get_columns(table_name)
        if isinstance(name := column.get("name"), str)
    }


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_building_documents" in tables:
        columns = _column_names(inspector, "world_building_documents")
        if "content_sha256" not in columns:
            op.add_column(
                "world_building_documents",
                sa.Column("content_sha256", sa.String(length=64), nullable=True),
            )
        inspector = sa.inspect(bind)
        indexes = _index_names(inspector, "world_building_documents")
        if "ix_world_building_documents_content_sha256" not in indexes:
            op.create_index(
                "ix_world_building_documents_content_sha256",
                "world_building_documents",
                ["content_sha256"],
            )

    if "world_source_observations" not in tables:
        op.create_table(
            "world_source_observations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "generation_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("book_data_generations.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "world_document_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("world_building_documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "chapter_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chapters.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source_kind", sa.String(length=32), nullable=False),
            sa.Column("source_key", sa.String(length=255), nullable=False),
            sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("candidate_key", sa.String(length=128), nullable=False),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    inspector = sa.inspect(bind)
    observation_indexes = _index_names(inspector, "world_source_observations")
    for index_name, columns, unique, where in (
        (
            "ix_world_source_observations_book_source",
            ["book_id", "source_kind", "source_key"],
            False,
            None,
        ),
        (
            "ix_world_source_observations_document_generation",
            ["world_document_id", "generation_id"],
            False,
            None,
        ),
        (
            "uq_world_source_observations_generation_candidate",
            ["book_id", "generation_id", "source_kind", "source_key", "candidate_key"],
            True,
            sa.text("generation_id IS NOT NULL"),
        ),
        (
            "uq_world_source_observations_unversioned_candidate",
            ["book_id", "source_kind", "source_key", "candidate_key"],
            True,
            sa.text("generation_id IS NULL"),
        ),
    ):
        if index_name not in observation_indexes:
            op.create_index(
                index_name,
                "world_source_observations",
                columns,
                unique=unique,
                postgresql_where=where,
            )

    if "world_analysis_states" not in tables:
        op.create_table(
            "world_analysis_states",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "series_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("series.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("scope", sa.String(length=16), nullable=False),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default="queued",
            ),
            sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
            sa.Column(
                "payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("refresh_job_id", sa.String(length=128), nullable=True),
            sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(length=128), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "(book_id IS NOT NULL AND series_id IS NULL) OR "
                "(book_id IS NULL AND series_id IS NOT NULL)",
                name="ck_world_analysis_states_exactly_one_target",
            ),
        )

    inspector = sa.inspect(bind)
    state_indexes = _index_names(inspector, "world_analysis_states")
    for index_name, columns, unique, where in (
        (
            "uq_world_analysis_states_book",
            ["book_id"],
            True,
            sa.text("book_id IS NOT NULL"),
        ),
        (
            "uq_world_analysis_states_series",
            ["series_id"],
            True,
            sa.text("series_id IS NOT NULL"),
        ),
        (
            "ix_world_analysis_states_status_updated",
            ["status", "updated_at"],
            False,
            None,
        ),
    ):
        if index_name not in state_indexes:
            op.create_index(
                index_name,
                "world_analysis_states",
                columns,
                unique=unique,
                postgresql_where=where,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_analysis_states" in tables:
        indexes = _index_names(inspector, "world_analysis_states")
        for index_name in (
            "ix_world_analysis_states_status_updated",
            "uq_world_analysis_states_series",
            "uq_world_analysis_states_book",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="world_analysis_states")
        op.drop_table("world_analysis_states")

    if "world_source_observations" in tables:
        indexes = _index_names(inspector, "world_source_observations")
        for index_name in (
            "uq_world_source_observations_unversioned_candidate",
            "uq_world_source_observations_generation_candidate",
            "ix_world_source_observations_document_generation",
            "ix_world_source_observations_book_source",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="world_source_observations")
        op.drop_table("world_source_observations")

    if "world_building_documents" in tables:
        columns = _column_names(inspector, "world_building_documents")
        if "content_sha256" in columns:
            indexes = _index_names(inspector, "world_building_documents")
            if "ix_world_building_documents_content_sha256" in indexes:
                op.drop_index(
                    "ix_world_building_documents_content_sha256",
                    table_name="world_building_documents",
                )
            op.drop_column("world_building_documents", "content_sha256")
