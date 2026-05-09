import asyncio
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

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

offending_revisions = destructive_upgrade_revisions(Path(__file__).resolve().parent / "versions")
if offending_revisions and os.getenv("ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES") != "1":
    offending_paths = ", ".join(str(path.name) for path in offending_revisions)
    raise RuntimeError(
        "Refusing to run migrations because destructive operations were found in upgrade() blocks: "
        f"{offending_paths}. Remove them or set ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES=1 only if you "
        "explicitly intend to drop data."
    )

if any(arg == "downgrade" for arg in sys.argv[1:]):
    destructive_downgrades = destructive_downgrade_revisions(Path(__file__).resolve().parent / "versions")
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
    cfg = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
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
