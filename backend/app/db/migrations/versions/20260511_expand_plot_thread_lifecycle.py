"""expand plot thread lifecycle tracking

Revision ID: 20260511_expand_plot_thread_lifecycle
Revises: 20260510_add_preserve_source_chapters
Create Date: 2026-05-11 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20260511_expand_plot_thread_lifecycle"
down_revision = "20260510_add_preserve_source_chapters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "plot_threads" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("plot_threads")}
    if "last_mentioned_at" not in columns:
        op.add_column("plot_threads", sa.Column("last_mentioned_at", sa.Integer(), nullable=True))
    if "mention_count" not in columns:
        op.add_column(
            "plot_threads",
            sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        )

    bind.execute(sa.text("UPDATE plot_threads SET last_mentioned_at = COALESCE(last_mentioned_at, introduced_at)"))
    bind.execute(sa.text("UPDATE plot_threads SET mention_count = COALESCE(mention_count, 1)"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "plot_threads" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("plot_threads")}
    if "mention_count" in columns:
        op.drop_column("plot_threads", "mention_count")
    if "last_mentioned_at" in columns:
        op.drop_column("plot_threads", "last_mentioned_at")
