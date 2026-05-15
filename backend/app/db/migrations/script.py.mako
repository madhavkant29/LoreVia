"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

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
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
