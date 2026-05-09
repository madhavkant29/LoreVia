"""Add world canonical identities for persistent alias resolution.

Revision ID: 20260503_add_world_canonical_identities
Revises: 20260501_add_manuscript_workspace_and_voice_profiles
Create Date: 2026-05-03 00:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260503_add_world_canonical_identities"
down_revision: str | None = "20260501_add_manuscript_workspace_and_voice_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    indexes = (
        {index["name"] for index in inspector.get_indexes("world_canonical_identities")}
        if "world_canonical_identities" in tables
        else set()
    )

    if "world_canonical_identities" not in tables:
        op.create_table(
            "world_canonical_identities",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=True),
            sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="author_override"),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        indexes = set()

    for index_name, columns in (
        ("ix_world_canonical_identities_book_id", ["book_id"]),
        ("ix_world_canonical_identities_canonical_name", ["canonical_name"]),
        ("ix_world_canonical_identities_entity_type", ["entity_type"]),
        ("ix_world_canonical_identities_source", ["source"]),
        ("ix_world_canonical_identities_created_at", ["created_at"]),
        ("ix_world_canonical_identities_updated_at", ["updated_at"]),
    ):
        if index_name not in indexes:
            op.create_index(index_name, "world_canonical_identities", columns)
            indexes.add(index_name)

    tables = set(inspector.get_table_names())
    if "world_canonical_identities" in tables and "world_notes" in tables:
        note_rows = bind.execute(
            sa.text(
                """
                SELECT id, book_id, title, body, context_label, suggested_fix, created_at, updated_at
                FROM world_notes
                WHERE note_type = 'canon_override'
                """
            )
        ).mappings().all()
        existing = {
            (str(row.book_id), str(row.canonical_name).strip().lower())
            for row in bind.execute(
                sa.text("SELECT book_id, canonical_name FROM world_canonical_identities")
            ).mappings().all()
        }
        for row in note_rows:
            try:
                payload = json.loads(row["body"] or "{}")
            except Exception:
                payload = {}
            canonical_name = " ".join(str(payload.get("canonical_name") or row["title"] or "").split()).strip()
            if not canonical_name:
                continue
            dedupe_key = (str(row["book_id"]), canonical_name.lower())
            if dedupe_key in existing:
                continue
            aliases = [alias for alias in (payload.get("aliases") or []) if str(alias).strip()]
            bind.execute(
                sa.text(
                    """
                    INSERT INTO world_canonical_identities
                        (id, book_id, canonical_name, entity_type, aliases, source, confidence, notes, metadata_json, created_at, updated_at)
                    VALUES
                        (:id, :book_id, :canonical_name, :entity_type, :aliases, 'author_override', :confidence, :notes, CAST(:metadata_json AS jsonb), :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(row["id"]),
                    "book_id": str(row["book_id"]),
                    "canonical_name": canonical_name,
                    "entity_type": " ".join(str(payload.get("entity_type") or row["context_label"] or "").split()).strip() or None,
                    "aliases": aliases or None,
                    "confidence": 0.99,
                    "notes": " ".join(str(payload.get("notes") or row["suggested_fix"] or "").split()).strip() or None,
                    "metadata_json": json.dumps({"migrated_from_world_note": True}),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                },
            )
            existing.add(dedupe_key)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "world_canonical_identities" not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("world_canonical_identities")}
    for index_name in (
        "ix_world_canonical_identities_updated_at",
        "ix_world_canonical_identities_created_at",
        "ix_world_canonical_identities_source",
        "ix_world_canonical_identities_entity_type",
        "ix_world_canonical_identities_canonical_name",
        "ix_world_canonical_identities_book_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="world_canonical_identities")
    op.drop_table("world_canonical_identities")
