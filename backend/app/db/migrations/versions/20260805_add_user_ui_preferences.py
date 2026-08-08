"""Add account-scoped UI preference tables.

Revision ID: 20260805_add_user_ui_preferences
Revises: 20260802_continuity_created_idx
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_add_user_ui_preferences"
down_revision: str | Sequence[str] | None = "20260802_continuity_created_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GLOBAL_INDEXES: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "ix_user_ui_preferences_user_updated": (
        "user_ui_preferences",
        ("user_id", "updated_at"),
        False,
    ),
}

BOOK_INDEXES: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "ix_user_book_ui_preferences_user_updated": (
        "user_book_ui_preferences",
        ("user_id", "updated_at"),
        False,
    ),
    "ix_user_book_ui_preferences_book": ("user_book_ui_preferences", ("book_id",), False),
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table)
        if isinstance(name := index.get("name"), str)
    }


def _constraint_names(inspector: sa.Inspector, table: str) -> set[str]:
    names = {
        name
        for constraint in inspector.get_unique_constraints(table)
        if isinstance(name := constraint.get("name"), str)
    }
    names.update(
        name
        for constraint in inspector.get_foreign_keys(table)
        if isinstance(name := constraint.get("name"), str)
    )
    return names


def _create_index_if_missing(
    inspector: sa.Inspector, name: str, table: str, columns: tuple[str, ...], unique: bool
) -> None:
    existing = _index_names(inspector, table) | _constraint_names(inspector, table)
    if name not in existing:
        op.create_index(name, table, list(columns), unique=unique)


def _jsonb_default(value: str) -> sa.TextClause:
    return sa.text(f"'{value}'::jsonb")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = _inspector()
    tables = set(inspector.get_table_names())

    if "user_ui_preferences" not in tables:
        op.create_table(
            "user_ui_preferences",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("complexity_mode", sa.String(), nullable=False, server_default="focused"),
            sa.Column(
                "dashboard_visibility_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "dashboard_order_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("[]"),
            ),
            sa.Column(
                "public_tool_visibility_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column("density", sa.String(), nullable=False, server_default="comfortable"),
            sa.Column(
                "reader_toolbar_density", sa.String(), nullable=False, server_default="standard"
            ),
            sa.Column(
                "locked_tool_presentation", sa.String(), nullable=False, server_default="compact"
            ),
            sa.Column(
                "default_workspace_shell", sa.String(), nullable=False, server_default="reader"
            ),
            sa.Column(
                "mobile_actions_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("[]"),
            ),
            sa.Column(
                "guidance_dismissals_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "recommendation_snoozes_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint("user_id", name="uq_user_ui_preferences_user_id"),
        )

    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "user_ui_preferences" in tables:
        for name, (table, columns, unique) in GLOBAL_INDEXES.items():
            _create_index_if_missing(inspector, name, table, columns, unique)

    if "user_book_ui_preferences" not in tables:
        op.create_table(
            "user_book_ui_preferences",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("book_preset", sa.String(), nullable=False, server_default="draft"),
            sa.Column("advanced_tool_override", sa.String(), nullable=True),
            sa.Column(
                "hidden_book_tools_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("[]"),
            ),
            sa.Column(
                "overview_cards_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "reader_actions_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("[]"),
            ),
            sa.Column(
                "mobile_actions_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("[]"),
            ),
            sa.Column(
                "panel_state_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "timeline_collapsed_sections_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=_jsonb_default("{}"),
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
            sa.UniqueConstraint(
                "user_id", "book_id", name="uq_user_book_ui_preferences_user_book"
            ),
        )

    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "user_book_ui_preferences" in tables:
        for name, (table, columns, unique) in BOOK_INDEXES.items():
            _create_index_if_missing(inspector, name, table, columns, unique)

    if {"books", "user_book_ui_preferences"}.issubset(tables):
        while True:
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO user_book_ui_preferences (
                        id,
                        user_id,
                        book_id,
                        schema_version,
                        revision,
                        book_preset,
                        advanced_tool_override,
                        hidden_book_tools_json,
                        overview_cards_json,
                        reader_actions_json,
                        mobile_actions_json,
                        panel_state_json,
                        timeline_collapsed_sections_json
                    )
                    SELECT
                        gen_random_uuid(),
                        books.user_id,
                        books.id,
                        1,
                        1,
                        'all',
                        NULL,
                        '[]'::jsonb,
                        '{}'::jsonb,
                        '[]'::jsonb,
                        '[]'::jsonb,
                        '{}'::jsonb,
                        '{}'::jsonb
                    FROM books
                    WHERE books.user_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM user_book_ui_preferences
                        WHERE user_book_ui_preferences.user_id = books.user_id
                        AND user_book_ui_preferences.book_id = books.id
                    )
                    ORDER BY books.id
                    LIMIT :batch_size
                    """
                ),
                {"batch_size": 10_000},
            )
            if result.rowcount == 0:
                break

    if "users" in tables and "user_ui_preferences" in tables:
        while True:
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO user_ui_preferences (
                        id,
                        user_id,
                        schema_version,
                        revision,
                        complexity_mode,
                        dashboard_visibility_json,
                        dashboard_order_json,
                        public_tool_visibility_json,
                        density,
                        reader_toolbar_density,
                        locked_tool_presentation,
                        default_workspace_shell,
                        mobile_actions_json,
                        guidance_dismissals_json,
                        recommendation_snoozes_json
                    )
                    SELECT
                        gen_random_uuid(),
                        users.id,
                        1,
                        1,
                        'standard',
                        '{}'::jsonb,
                        '[]'::jsonb,
                        '{}'::jsonb,
                        'comfortable',
                        'standard',
                        'compact',
                        'reader',
                        '[]'::jsonb,
                        '{}'::jsonb,
                        '{}'::jsonb
                    FROM users
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM user_ui_preferences
                        WHERE user_ui_preferences.user_id = users.id
                    )
                    ORDER BY users.id
                    LIMIT :batch_size
                    """
                ),
                {"batch_size": 10_000},
            )
            if result.rowcount == 0:
                break


def downgrade() -> None:
    inspector = _inspector()
    tables = set(inspector.get_table_names())

    if "user_book_ui_preferences" in tables:
        indexes = _index_names(inspector, "user_book_ui_preferences")
        constraints = _constraint_names(inspector, "user_book_ui_preferences")
        for name in reversed(tuple(BOOK_INDEXES.keys())):
            if name in indexes and name not in constraints:
                op.drop_index(name, table_name="user_book_ui_preferences")
        op.drop_table("user_book_ui_preferences")

    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "user_ui_preferences" in tables:
        indexes = _index_names(inspector, "user_ui_preferences")
        constraints = _constraint_names(inspector, "user_ui_preferences")
        for name in reversed(tuple(GLOBAL_INDEXES.keys())):
            if name in indexes and name not in constraints:
                op.drop_index(name, table_name="user_ui_preferences")
        op.drop_table("user_ui_preferences")
