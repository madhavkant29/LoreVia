"""merge character arc tracker and plot thread lifecycle heads

Revision ID: 6d6a849ebcbb
Revises: 20260511_add_character_arc_tracker_fields, 20260511_expand_plot_thread_lifecycle
Create Date: 2026-05-11 11:42:04.561697
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '6d6a849ebcbb'
down_revision: Union[str, None] = ('20260511_add_character_arc_tracker_fields', '20260511_expand_plot_thread_lifecycle')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
