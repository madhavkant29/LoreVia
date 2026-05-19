import asyncio
import os
import sys
from pathlib import Path

from alembic import context
import sqlalchemy as sa
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base  # noqa
from app.utils.migration_utils import (
    destructive_downgrade_revisions,
    destructive_upgrade_revisions,
    is_local_database_url,
    redact_database_target,
    resolve_alembic_database_url,
)
from app.utils.logging import get_logger

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
                if any(table_name in tables for table_name in ("rewarded_ad_sessions", "referrals", "point_ledger_entries")):
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

            return True
    finally:
        engine.dispose()

if any(arg == "upgrade" for arg in sys.argv[1:]):
    offending_revisions = [
        path
        for path in destructive_upgrade_revisions(versions_dir)
        if _destructive_upgrade_still_has_runtime_impact(path)
    ]
    if offending_revisions and os.getenv("ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES") != "1":
        offending_paths = ", ".join(str(path.name) for path in offending_revisions)
        raise RuntimeError(
            "Refusing to run migrations because destructive operations were found in upgrade() blocks: "
            f"{offending_paths}. Remove them or set ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES=1 only if you "
            "explicitly intend to drop data."
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


def do_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=lambda obj, name, type_, reflected, compare_to: not (
            type_ == "table" and reflected and getattr(obj, "schema", None) not in (None, "public")
        ),
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
        include_object=lambda obj, name, type_, reflected, compare_to: not (
            type_ == "table" and reflected and getattr(obj, "schema", None) not in (None, "public")
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
