import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.utils.logging import get_logger
from app.utils.migration_utils import (
    CORE_APPLICATION_TABLES,
    redact_database_target,
    should_reset_local_alembic_state,
)

log = get_logger("lorevia.bootstrap_db")


def _alembic_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "alembic", *args]


def _database_url() -> str:
    return settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def _existing_tables() -> set[str]:
    engine = create_engine(_database_url())
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def _run_alembic(*args: str) -> int:
    completed = subprocess.run(_alembic_command(*args), cwd=ROOT, check=False)
    return completed.returncode


def main() -> int:
    log.info("bootstrap_db_start", extra={"database": redact_database_target(settings.DATABASE_URL)})

    existing_tables = _existing_tables()
    if should_reset_local_alembic_state(existing_tables):
        log.warning(
            "bootstrap_db_reset_alembic_state",
            extra={
                "existing_tables": sorted(existing_tables),
                "missing_core_tables": sorted(CORE_APPLICATION_TABLES - existing_tables),
            },
        )
        stamp_exit = _run_alembic("stamp", "base")
        if stamp_exit != 0:
            return stamp_exit

    upgrade_exit = _run_alembic("upgrade", "head")
    if upgrade_exit != 0:
        return upgrade_exit

    final_tables = _existing_tables()
    missing_core_tables = CORE_APPLICATION_TABLES - final_tables
    if missing_core_tables:
        log.error(
            "bootstrap_db_missing_core_tables",
            extra={
                "existing_tables": sorted(final_tables),
                "missing_core_tables": sorted(missing_core_tables),
            },
        )
        return 1

    log.info("bootstrap_db_complete", extra={"existing_tables": sorted(final_tables)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
