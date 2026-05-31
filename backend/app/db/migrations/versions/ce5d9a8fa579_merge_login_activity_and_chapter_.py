"""merge login activity and chapter restore lifecycle heads

Revision ID: ce5d9a8fa579
Revises: 20260529_add_chapter_version_restore_lifecycle, 20260529_drop_users_login_activity_dates
Create Date: 2026-05-30 08:16:55.154161
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'ce5d9a8fa579'
down_revision: Union[str, None] = ('20260529_add_chapter_version_restore_lifecycle', '20260529_drop_users_login_activity_dates')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# For new tables in the public schema:
# - Backend-only tables: do not grant anon/authenticated Data API access.
# - Frontend/Data API tables: use app.utils.migration_utils helpers for explicit grants, RLS, and policies.
# Example imports:
# from app.utils.migration_utils import (
#     create_policy_if_missing,
#     enable_row_level_security,
#     grant_supabase_data_api_sequence_access,
#     grant_supabase_data_api_table_access,
# )

def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
