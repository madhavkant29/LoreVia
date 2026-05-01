"""Add source discriminator for Obsidian vault notes.

Revision ID: 20260430_obsidian_note_source
Revises: 20260429_obsidian_notes
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_obsidian_note_source"
down_revision: str | None = "20260429_obsidian_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "book_obsidian_notes"
OLD_CONSTRAINT = "uq_book_obsidian_notes_user_book_path"
NEW_CONSTRAINT = "uq_book_obsidian_notes_user_book_path_source"


def _constraint_names(inspector: sa.Inspector) -> set[str]:
    return {
        constraint_name
        for constraint in inspector.get_unique_constraints(TABLE_NAME)
        if (constraint_name := constraint.get("name")) is not None
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "source" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("source", sa.String(), nullable=True, server_default="character_bible"),
        )
        op.execute(sa.text(f"UPDATE {TABLE_NAME} SET source = 'character_bible' WHERE source IS NULL"))
        op.alter_column(TABLE_NAME, "source", nullable=False, server_default="character_bible")
        inspector = sa.inspect(bind)

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if "ix_book_obsidian_notes_source" not in indexes:
        op.create_index("ix_book_obsidian_notes_source", TABLE_NAME, ["source"])

    constraints = _constraint_names(inspector)
    if NEW_CONSTRAINT not in constraints:
        op.create_unique_constraint(NEW_CONSTRAINT, TABLE_NAME, ["user_id", "book_id", "path", "source"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    if "ix_book_obsidian_notes_source" in indexes:
        op.drop_index("ix_book_obsidian_notes_source", table_name=TABLE_NAME)

    constraints = _constraint_names(inspector)
    if NEW_CONSTRAINT in constraints:
        op.drop_constraint(NEW_CONSTRAINT, TABLE_NAME, type_="unique")
        inspector = sa.inspect(bind)
        constraints = _constraint_names(inspector)
    if OLD_CONSTRAINT not in constraints:
        op.create_unique_constraint(OLD_CONSTRAINT, TABLE_NAME, ["user_id", "book_id", "path"])

    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if "source" in columns:
        op.drop_column(TABLE_NAME, "source")
