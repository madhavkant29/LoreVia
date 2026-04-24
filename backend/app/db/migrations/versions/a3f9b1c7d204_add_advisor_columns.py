"""add last_seen_chapter and mention_count to characters

Revision ID: a3f9b1c7d204
Revises: (first migration)
Create Date: 2026-04-18
"""
import sqlalchemy as sa
from alembic import op

revision = "a3f9b1c7d204"
down_revision = None   # first migration — no predecessor
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("characters")}

    if "last_seen_chapter" not in columns:
        op.add_column(
            "characters",
            sa.Column("last_seen_chapter", sa.Integer(), nullable=True),
        )
    if "mention_count" not in columns:
        op.add_column(
            "characters",
            sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("characters")}
    if "mention_count" in columns:
        op.drop_column("characters", "mention_count")
    if "last_seen_chapter" in columns:
        op.drop_column("characters", "last_seen_chapter")
