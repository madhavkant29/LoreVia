"""Add character candidate adjudication metadata.

Revision ID: 20260611_add_character_candidate_adjudication
Revises: 20260611_complex_relationship_labels
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260611_add_character_candidate_adjudication"
down_revision: str | Sequence[str] | None = "20260611_complex_relationship_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    constraints = [
        *inspector.get_unique_constraints(table_name),
        *inspector.get_foreign_keys(table_name),
    ]
    return {
        name
        for constraint in constraints
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "character_candidates" not in tables:
        return

    columns = _column_names(inspector, "character_candidates")
    if "chapter_id" not in columns:
        op.add_column("character_candidates", sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "scene_id" not in columns:
        op.add_column("character_candidates", sa.Column("scene_id", postgresql.UUID(as_uuid=True), nullable=True))
    if "display_name" not in columns:
        op.add_column("character_candidates", sa.Column("display_name", sa.String(), nullable=True))
    if "mention_count" not in columns:
        op.add_column("character_candidates", sa.Column("mention_count", sa.Integer(), nullable=True))
    if "chapter_count" not in columns:
        op.add_column("character_candidates", sa.Column("chapter_count", sa.Integer(), nullable=True))
    if "evidence_windows" not in columns:
        op.add_column("character_candidates", sa.Column("evidence_windows", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if "entity_type" not in columns:
        op.add_column("character_candidates", sa.Column("entity_type", sa.String(), nullable=True))
    if "adjudication_status" not in columns:
        op.add_column("character_candidates", sa.Column("adjudication_status", sa.String(), nullable=True))
    if "character_score" not in columns:
        op.add_column("character_candidates", sa.Column("character_score", sa.Integer(), nullable=True))
    if "rejection_reason" not in columns:
        op.add_column("character_candidates", sa.Column("rejection_reason", sa.String(), nullable=True))

    constraints = _constraint_names(inspector, "character_candidates")
    if "fk_character_candidates_chapter_id" not in constraints and "chapters" in tables:
        op.create_foreign_key(
            "fk_character_candidates_chapter_id",
            "character_candidates",
            "chapters",
            ["chapter_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "fk_character_candidates_scene_id" not in constraints and "novel_scenes" in tables:
        op.create_foreign_key(
            "fk_character_candidates_scene_id",
            "character_candidates",
            "novel_scenes",
            ["scene_id"],
            ["id"],
            ondelete="SET NULL",
        )

    indexes = _index_names(inspector, "character_candidates")
    for index_name, column_names in (
        ("ix_character_candidates_chapter_id", ["chapter_id"]),
        ("ix_character_candidates_scene_id", ["scene_id"]),
        ("ix_character_candidates_book_adjudication", ["book_id", "adjudication_status"]),
        ("ix_character_candidates_book_entity_type", ["book_id", "entity_type"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "character_candidates", column_names, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "character_candidates" not in tables:
        return

    indexes = _index_names(inspector, "character_candidates")
    for index_name in (
        "ix_character_candidates_book_entity_type",
        "ix_character_candidates_book_adjudication",
        "ix_character_candidates_scene_id",
        "ix_character_candidates_chapter_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="character_candidates")

    constraints = _constraint_names(inspector, "character_candidates")
    for constraint_name in (
        "fk_character_candidates_scene_id",
        "fk_character_candidates_chapter_id",
    ):
        if constraint_name in constraints:
            op.drop_constraint(constraint_name, "character_candidates", type_="foreignkey")

    columns = _column_names(inspector, "character_candidates")
    for column_name in (
        "rejection_reason",
        "character_score",
        "adjudication_status",
        "entity_type",
        "evidence_windows",
        "chapter_count",
        "mention_count",
        "display_name",
        "scene_id",
        "chapter_id",
    ):
        if column_name in columns:
            op.drop_column("character_candidates", column_name)
