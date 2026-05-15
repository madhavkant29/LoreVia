"""merge beta read chapter structure and writing activity heads

Revision ID: 1a70eda4d48c
Revises: 20260514_add_beta_read_assignments, 20260514_add_chapter_structure_version, 20260514_add_user_writing_activities
Create Date: 2026-05-14 01:10:31.613857
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '1a70eda4d48c'
down_revision: Union[str, None] = ('20260514_add_beta_read_assignments', '20260514_add_chapter_structure_version', '20260514_add_user_writing_activities')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
