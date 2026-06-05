"""add_missing_rate_limit_override_columns

Revision ID: 61eb02473fa9
Revises: 20260602_add_force_single_manuscript_to_books
Create Date: 2026-06-03 21:23:06.630548
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '61eb02473fa9'
down_revision: Union[str, None] = '20260602_add_force_single_manuscript_to_books'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('user_rate_limit_overrides')}

    for col_name in [
        'advisor_per_day',
        'uploads_per_hour',
        'public_publish_per_hour',
        'public_unpublish_per_hour',
        'manuscript_imports_per_hour',
        'world_building_uploads_per_hour',
        'world_building_ai_per_hour',
    ]:
        if col_name not in columns:
            op.add_column(
                'user_rate_limit_overrides',
                sa.Column(col_name, sa.Integer(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('user_rate_limit_overrides')}

    for col_name in [
        'advisor_per_day',
        'uploads_per_hour',
        'public_publish_per_hour',
        'public_unpublish_per_hour',
        'manuscript_imports_per_hour',
        'world_building_uploads_per_hour',
        'world_building_ai_per_hour',
    ]:
        if col_name in columns:
            op.drop_column('user_rate_limit_overrides', col_name)
