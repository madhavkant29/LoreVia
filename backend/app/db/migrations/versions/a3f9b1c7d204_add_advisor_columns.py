"""add last_seen_chapter and mention_count to characters

Revision ID: a3f9b1c7d204
Revises: (first migration)
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f9b1c7d204"
down_revision = None   # first migration — no predecessor
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
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
    op.drop_column("characters", "mention_count")
    op.drop_column("characters", "last_seen_chapter")
