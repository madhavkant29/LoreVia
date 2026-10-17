import asyncio
import os
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base  # noqa
from app.utils.logging import get_logger
from app.utils.migration_utils import (
    destructive_downgrade_revisions,
    destructive_upgrade_revisions,
    is_local_database_url,
    parse_revision_allowlist,
    redact_database_target,
    resolve_alembic_database_url,
    revision_paths_excluding_allowlist,
    unapplied_revision_paths,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

config = context.config
log = get_logger("alembic")
versions_dir = Path(__file__).resolve().parent / "versions"
db_url, _explicit_url = resolve_alembic_database_url(
    os.getenv("ALEMBIC_DATABASE_URL"),
    settings.DATABASE_URL,
)
log.info("alembic_target", extra={"database": redact_database_target(db_url)})
if not is_local_database_url(db_url) and os.getenv("ALEMBIC_CONFIRM_REMOTE") != "YES_I_AM_SURE":
    raise RuntimeError(
        "Refusing to run Alembic against a remote database without explicit confirmation. "
        "Set ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE to continue."
    )


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _destructive_upgrade_still_has_runtime_impact(path: Path) -> bool:
    engine = create_engine(
        db_url.replace("postgresql://", "postgresql+psycopg://"),
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )
    try:
        with engine.connect() as connection:
            inspector = sa.inspect(connection)
            tables = _table_names(inspector)

            if path.name == "20260517_finalize_subscription_events_and_remove_monetization.py":
                if any(
                    table_name in tables
                    for table_name in ("rewarded_ad_sessions", "referrals", "point_ledger_entries")
                ):
                    return True

                if "users" in tables and "referral_code" in _column_names(inspector, "users"):
                    return True

                if "beta_read_assignments" in tables:
                    columns = _column_names(inspector, "beta_read_assignments")
                    indexes = _index_names(inspector, "beta_read_assignments")
                    if (
                        "ix_beta_read_assignments_awarded_at" in indexes
                        or "awarded_at" in columns
                        or "awarded_points" in columns
                        or "reward_points" in columns
                    ):
                        return True

                return False

            if path.name == "20260519_remove_beta_read_awarded_at_residue.py":
                if "beta_read_assignments" not in tables:
                    return False

                columns = _column_names(inspector, "beta_read_assignments")
                indexes = _index_names(inspector, "beta_read_assignments")
                return "awarded_at" in columns or "ix_beta_read_assignments_awarded_at" in indexes

            if path.name == "20260516_normalize_unique_constraints.py":
                if "rewarded_ad_sessions" not in tables:
                    return False
                indexes = _index_names(inspector, "rewarded_ad_sessions")
                if "ix_rewarded_ad_sessions_claim_token" not in indexes:
                    return False
                # Only impactful if the index exists and is not owned by a constraint
                result = connection.execute(
                    sa.text(
                        "SELECT 1 FROM pg_constraint con "
                        "JOIN pg_class idx ON idx.oid = con.conindid "
                        "JOIN pg_namespace nsp ON nsp.oid = idx.relnamespace "
                        "WHERE nsp.nspname = 'public' "
                        "AND idx.relname = 'ix_rewarded_ad_sessions_claim_token' "
                        "LIMIT 1"
                    )
                )
                return result.scalar() is None

            if path.name == "20260517_allow_multiple_public_forum_posts_per_book.py":
                if "book_forum_posts" not in tables:
                    return False
                unique_constraints = {
                    name
                    for constraint in inspector.get_unique_constraints("book_forum_posts")
                    if isinstance(name := constraint.get("name"), str)
                }
                return "uq_book_forum_posts_book" in unique_constraints

            if path.name == "20260517_drop_redundant_subscription_event_index.py":
                if "subscription_events" not in tables:
                    return False
                indexes = _index_names(inspector, "subscription_events")
                return "ix_subscription_events_source_event_id" in indexes

            if path.name == "20260529_drop_users_login_activity_dates.py":
                if "users" not in tables:
                    return False
                return "login_activity_dates" in _column_names(inspector, "users")

            if path.name == "20260530_remove_orphaned_indexes.py":
                impact = False
                for index_name, table_name in (
                    ("ix_book_chunks_chunk_index", "book_chunks"),
                    ("ix_character_relationships_character_a_id", "character_relationships"),
                    ("ix_character_relationships_character_b_id", "character_relationships"),
                    ("ix_character_relationships_from_chapter", "character_relationships"),
                    ("ix_character_relationships_to_chapter", "character_relationships"),
                    ("ix_character_states_at_chapter", "character_states"),
                    ("ix_characters_book_visibility_approval", "characters"),
                    ("ix_characters_first_chapter", "characters"),
                    ("ix_characters_last_seen_chapter", "characters"),
                    ("ix_characters_name", "characters"),
                    ("ix_characters_role", "characters"),
                    ("ix_novel_scenes_book_id_chapter_number_status", "novel_scenes"),
                    ("ix_reading_progress_book_id", "reading_progress"),
                    ("ix_reading_sessions_book_id", "reading_sessions"),
                    ("ix_wiki_entries_entry_type", "wiki_entries"),
                    ("ix_world_elements_book_id_element_type", "world_elements"),
                ):
                    if table_name in tables and index_name in _index_names(inspector, table_name):
                        impact = True
                        break
                if not impact and "users" in tables:
                    if "login_activity_dates" in _column_names(inspector, "users"):
                        impact = True
                return impact

            return True
    finally:
        engine.dispose()


if any(arg == "upgrade" for arg in sys.argv[1:]):
    destructive_revisions = destructive_upgrade_revisions(versions_dir)
    script_directory = ScriptDirectory.from_config(config)
    revision_engine = create_engine(
        db_url.replace("postgresql://", "postgresql+psycopg://"),
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )
    try:
        with revision_engine.connect() as revision_connection:
            current_heads = MigrationContext.configure(revision_connection).get_current_heads()
    finally:
        revision_engine.dispose()
    destructive_revisions = unapplied_revision_paths(
        destructive_revisions,
        script_directory=script_directory,
        current_heads=current_heads,
    )
    offending_revisions = [
        path
        for path in destructive_revisions
        if _destructive_upgrade_still_has_runtime_impact(path)
    ]
    allowed_revision_ids = parse_revision_allowlist(
        os.getenv("ALEMBIC_ALLOWED_DESTRUCTIVE_UPGRADE_REVISIONS")
    )
    offending_revisions = revision_paths_excluding_allowlist(
        offending_revisions,
        script_directory=script_directory,
        allowed_revision_ids=allowed_revision_ids,
    )
    if offending_revisions and os.getenv("ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES") != "1":
        offending_paths = ", ".join(str(path.name) for path in offending_revisions)
        raise RuntimeError(
            "Refusing to run migrations because destructive operations were found in upgrade() blocks: "
            f"{offending_paths}. Remove them, add exact reviewed revision IDs to "
            "ALEMBIC_ALLOWED_DESTRUCTIVE_UPGRADE_REVISIONS, or set "
            "ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES=1 only if you explicitly intend to drop data."
        )

if any(arg == "downgrade" for arg in sys.argv[1:]):
    destructive_downgrades = destructive_downgrade_revisions(versions_dir)
    if destructive_downgrades and os.getenv("ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES") != "1":
        offending_paths = ", ".join(str(path.name) for path in destructive_downgrades)
        raise RuntimeError(
            "Refusing to run Alembic downgrade because destructive operations were found in "
            "downgrade() blocks: "
            f"{offending_paths}. Downgrades that drop tables, columns, or indexes are disabled by "
            "default to protect the database. Set ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES=1 only if you "
            "explicitly intend to remove data."
        )
config.set_main_option(
    "sqlalchemy.url",
    db_url.replace("%", "%%").replace("postgresql://", "postgresql+psycopg://"),
)

target_metadata = Base.metadata


_UNSTABLE_EXPRESSION_INDEXES = {
    ("book_vault_notes", "ix_book_vault_notes_text_search"),
    ("novel_scenes", "ix_novel_scenes_text_search"),
}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and getattr(obj, "schema", None) not in (None, "public"):
        return False
    # PostgreSQL deparses these tsvector expressions differently from their
    # SQLAlchemy text forms, causing Alembic 1.13 to report false drop/add pairs.
    if (
        type_ == "index"
        and (getattr(getattr(obj, "table", None), "name", None), name)
        in _UNSTABLE_EXPRESSION_INDEXES
    ):
        return False
    return True


def do_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        connect_args={"prepare_threshold": None},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
