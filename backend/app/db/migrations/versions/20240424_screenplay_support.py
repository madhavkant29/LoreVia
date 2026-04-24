"""Add screenplay support - scenes and dialogue tables

Revision ID: 20240424_screenplay_support
Revises: 20240320_initial_schema
Create Date: 2024-04-24 17:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20240424_screenplay_support'
down_revision: str | None = '9b7f41d5c2aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "scenes" in tables and "dialogue" in tables:
        return

    # Update book.format to include screenplay
    # Note: This will be added manually after the enum exists
    # op.execute("ALTER TYPE book_format ADD VALUE 'screenplay'")

    has_books = "books" in tables
    has_chapters = "chapters" in tables

    # Create scenes table
    scene_fks = []
    if has_books:
        scene_fks.append(sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='CASCADE'))
    if has_chapters:
        scene_fks.append(sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='SET NULL'))

    if "scenes" not in tables:
        op.create_table('scenes',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('book_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('chapter_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('number', sa.Integer(), nullable=False),
            sa.Column('heading', sa.String(), nullable=False),
            sa.Column('location', sa.String(), nullable=True),
            sa.Column('time_of_day', sa.String(), nullable=True),
            sa.Column('interior', sa.Boolean(), nullable=False, default=False),
            sa.Column('exterior', sa.Boolean(), nullable=False, default=False),
            sa.Column('scene_number', sa.String(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), nullable=True),
            sa.Column('page_number', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            *scene_fks,
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_scenes_book_id'), 'scenes', ['book_id'], unique=False)
        op.create_index(op.f('ix_scenes_chapter_id'), 'scenes', ['chapter_id'], unique=False)

    # Create dialogue table
    has_scenes = "scenes" in tables
    dialogue_fks = []
    if has_scenes:
        dialogue_fks.append(sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='CASCADE'))

    if "dialogue" not in tables:
        op.create_table('dialogue',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('scene_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('character_name', sa.String(), nullable=False),
            sa.Column('character_extension', sa.String(), nullable=True),
            sa.Column('dialogue_text', sa.Text(), nullable=False),
            sa.Column('parenthetical', sa.String(), nullable=True),
            sa.Column('line_number', sa.Integer(), nullable=False),
            sa.Column('word_count', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            *dialogue_fks,
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_dialogue_scene_id'), 'dialogue', ['scene_id'], unique=False)


def downgrade() -> None:
    # Drop dialogue table
    op.drop_index(op.f('ix_dialogue_scene_id'), table_name='dialogue')
    op.drop_table('dialogue')
    
    # Drop scenes table
    op.drop_index(op.f('ix_scenes_chapter_id'), table_name='scenes')
    op.drop_index(op.f('ix_scenes_book_id'), table_name='scenes')
    op.drop_table('scenes')
    
    # Note: We don't remove 'screenplay' from book_format enum as PostgreSQL doesn't 
    # support removing enum values easily. This is harmless if the value isn't used.
