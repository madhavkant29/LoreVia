"""Add user writing goal and login streak fields.

Revision ID: 20260507_add_user_goal_and_login_streak
Revises: 20260507_add_novel_scene_metadata
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260507_add_user_goal_and_login_streak"
down_revision: str | None = "20260507_add_novel_scene_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "daily_word_goal" not in columns:
        op.add_column("users", sa.Column("daily_word_goal", sa.Integer(), nullable=False, server_default="1000"))
    if "today_word_count" not in columns:
        op.add_column("users", sa.Column("today_word_count", sa.Integer(), nullable=False, server_default="0"))
    if "today_word_count_date" not in columns:
        op.add_column("users", sa.Column("today_word_count_date", sa.Date(), nullable=True))
    if "last_login_at" not in columns:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    if "last_login_date" not in columns:
        op.add_column("users", sa.Column("last_login_date", sa.Date(), nullable=True))
    if "login_streak_days" not in columns:
        op.add_column("users", sa.Column("login_streak_days", sa.Integer(), nullable=False, server_default="0"))
    if "longest_login_streak_days" not in columns:
        op.add_column("users", sa.Column("longest_login_streak_days", sa.Integer(), nullable=False, server_default="0"))
    if "login_activity_dates" not in columns:
        op.add_column("users", sa.Column("login_activity_dates", sa.ARRAY(sa.Date()), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    for column_name in (
        "login_activity_dates",
        "longest_login_streak_days",
        "login_streak_days",
        "last_login_date",
        "last_login_at",
        "today_word_count_date",
        "today_word_count",
        "daily_word_goal",
    ):
        if column_name in columns:
            op.drop_column("users", column_name)
