"""Add manuscript workspace scenes and character voice profiles.

Revision ID: 20260501_add_manuscript_workspace_and_voice_profiles
Revises: 20260501_add_book_work_type
Create Date: 2026-05-01 21:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260501_add_manuscript_workspace_and_voice_profiles"
down_revision: str | None = "20260501_add_book_work_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    names: set[str] = set()
    for index in inspector.get_indexes(table_name):
        name = index.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "novel_scenes" not in tables:
        op.create_table(
            "novel_scenes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("html_body", sa.Text(), nullable=True),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="unassigned"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(), nullable=False, server_default="manual"),
            sa.Column("origin_chapter_number", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("book_id", "path", name="uq_novel_scenes_book_path"),
        )
        op.create_index("ix_novel_scenes_book_id", "novel_scenes", ["book_id"])
        op.create_index("ix_novel_scenes_chapter_id", "novel_scenes", ["chapter_id"])
        op.create_index("ix_novel_scenes_chapter_number", "novel_scenes", ["chapter_number"])
        op.create_index("ix_novel_scenes_path", "novel_scenes", ["path"])
        op.create_index("ix_novel_scenes_status", "novel_scenes", ["status"])
        op.create_index("ix_novel_scenes_created_at", "novel_scenes", ["created_at"])
        op.create_index("ix_novel_scenes_updated_at", "novel_scenes", ["updated_at"])

    if "character_voice_profiles" not in tables:
        op.create_table(
            "character_voice_profiles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("character_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("characters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sample_dialogue_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sample_word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_sentence_length", sa.Integer(), nullable=True),
            sa.Column("avg_word_length_x100", sa.Integer(), nullable=True),
            sa.Column("contraction_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("question_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("exclamation_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("ellipsis_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("dash_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("uppercase_rate_x1000", sa.Integer(), nullable=True),
            sa.Column("formality_score_x1000", sa.Integer(), nullable=True),
            sa.Column("lexical_complexity_x1000", sa.Integer(), nullable=True),
            sa.Column("emotional_intensity_x1000", sa.Integer(), nullable=True),
            sa.Column("dominant_markers", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb")),
            sa.Column("signature_phrases", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("character_id", name="uq_character_voice_profiles_character_id"),
        )
        op.create_index("ix_character_voice_profiles_book_id", "character_voice_profiles", ["book_id"])
        op.create_index("ix_character_voice_profiles_character_id", "character_voice_profiles", ["character_id"])
        op.create_index("ix_character_voice_profiles_updated_at", "character_voice_profiles", ["updated_at"])

    if "chapter_versions" in tables:
        columns = {column["name"] for column in inspector.get_columns("chapter_versions")}
        indexes = _index_names(inspector, "chapter_versions")
        if "snapshot_kind" not in columns:
            op.add_column(
                "chapter_versions",
                sa.Column("snapshot_kind", sa.String(), nullable=True, server_default="manual"),
            )
            op.execute(sa.text("UPDATE chapter_versions SET snapshot_kind = 'manual' WHERE snapshot_kind IS NULL"))
            op.alter_column("chapter_versions", "snapshot_kind", nullable=False, server_default="manual")
        if "restored_from_version_id" not in columns:
            op.add_column(
                "chapter_versions",
                sa.Column("restored_from_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.create_foreign_key(
                "fk_chapter_versions_restored_from_version_id",
                "chapter_versions",
                "chapter_versions",
                ["restored_from_version_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "ix_chapter_versions_snapshot_kind" not in indexes:
            op.create_index("ix_chapter_versions_snapshot_kind", "chapter_versions", ["snapshot_kind"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "chapter_versions" in tables:
        columns = {column["name"] for column in inspector.get_columns("chapter_versions")}
        indexes = _index_names(inspector, "chapter_versions")
        if "ix_chapter_versions_snapshot_kind" in indexes:
            op.drop_index("ix_chapter_versions_snapshot_kind", table_name="chapter_versions")
        if "restored_from_version_id" in columns:
            foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("chapter_versions") if fk.get("name")}
            if "fk_chapter_versions_restored_from_version_id" in foreign_keys:
                op.drop_constraint("fk_chapter_versions_restored_from_version_id", "chapter_versions", type_="foreignkey")
            op.drop_column("chapter_versions", "restored_from_version_id")
        if "snapshot_kind" in columns:
            op.drop_column("chapter_versions", "snapshot_kind")

    if "character_voice_profiles" in tables:
        op.drop_index("ix_character_voice_profiles_updated_at", table_name="character_voice_profiles")
        op.drop_index("ix_character_voice_profiles_character_id", table_name="character_voice_profiles")
        op.drop_index("ix_character_voice_profiles_book_id", table_name="character_voice_profiles")
        op.drop_table("character_voice_profiles")

    if "novel_scenes" in tables:
        op.drop_index("ix_novel_scenes_updated_at", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_created_at", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_status", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_path", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_chapter_number", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_chapter_id", table_name="novel_scenes")
        op.drop_index("ix_novel_scenes_book_id", table_name="novel_scenes")
        op.drop_table("novel_scenes")
