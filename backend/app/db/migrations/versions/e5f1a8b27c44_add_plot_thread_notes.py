"""add private note field to plot threads

Revision ID: e5f1a8b27c44
Revises: d8a4c6b9e201
Create Date: 2026-04-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f1a8b27c44"
down_revision = "d8a4c6b9e201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("plot_threads")}
    if "note" not in columns:
        op.add_column("plot_threads", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("plot_threads")}
    if "note" in columns:
        op.drop_column("plot_threads", "note")
