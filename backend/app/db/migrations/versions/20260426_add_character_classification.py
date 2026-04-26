"""add character classification fields

Revision ID: 20260426_char_type
Revises: 20240424_screenplay_support
Create Date: 2026-04-26 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260426_char_type"
down_revision = "20240424_screenplay_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "characters" not in tables:
        return

    # Add character_type column
    op.add_column("characters", sa.Column("character_type", sa.String(), nullable=True))
    
    # Add character_type_score column
    op.add_column("characters", sa.Column("character_type_score", sa.Integer(), nullable=True))
    
    # Add subtype_scores column
    op.add_column("characters", sa.Column("subtype_scores", postgresql.JSONB(), nullable=True, server_default="{}"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "characters" not in tables:
        return

    op.drop_column("characters", "subtype_scores")
    op.drop_column("characters", "character_type_score")
    op.drop_column("characters", "character_type")
