"""Verify Alembic migrations against a disposable local database.

Run from the repository root:
    docker compose -f docker-compose-local.yml exec -T api python scripts/verify_migrations_temp_db.py

The script creates a unique temporary database on the same local Postgres server,
runs upgrade -> downgrade -> upgrade, verifies Alembic current/head, and drops the
temporary database. It refuses non-local targets.
"""

from __future__ import annotations

import os
import sys
import uuid
from argparse import ArgumentParser
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.utils.migration_utils import is_local_database_url, redact_database_target


def _sync_url(url: str | URL) -> str:
    value = url if isinstance(url, URL) else make_url(url)
    drivername = value.drivername
    if drivername == "postgresql":
        drivername = "postgresql+psycopg"
    return value.set(drivername=drivername).render_as_string(hide_password=False)


def _maintenance_url(app_url: URL) -> URL:
    return app_url.set(database="postgres")


def _temporary_database_url(app_url: URL, database_name: str) -> URL:
    return app_url.set(database=database_name)


def _create_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(
        _sync_url(maintenance_url),
        isolation_level="AUTOCOMMIT",
        connect_args={"prepare_threshold": None},
    )
    try:
        with engine.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{database_name}"'))
    finally:
        engine.dispose()


def _drop_database(maintenance_url: URL, database_name: str) -> None:
    engine = sa.create_engine(
        _sync_url(maintenance_url),
        isolation_level="AUTOCOMMIT",
        connect_args={"prepare_threshold": None},
    )
    try:
        with engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        engine.dispose()


@contextmanager
def _temporary_alembic_environment(database_url: URL) -> Iterator[None]:
    previous = {
        "ALEMBIC_DATABASE_URL": os.environ.get("ALEMBIC_DATABASE_URL"),
        "ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES": os.environ.get("ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES"),
        "ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES": os.environ.get(
            "ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES"
        ),
    }
    os.environ["ALEMBIC_DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    os.environ["ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES"] = "1"
    os.environ["ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES"] = "1"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def _script_directory(config: Config) -> ScriptDirectory:
    return ScriptDirectory.from_config(config)


def _heads(config: Config) -> list[str]:
    return sorted(_script_directory(config).get_heads())


def _default_downgrade_target(config: Config) -> str:
    heads = _heads(config)
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, got {heads}.")
    revision = _script_directory(config).get_revision(heads[0])
    down_revision = revision.down_revision
    if isinstance(down_revision, tuple):
        raise RuntimeError(f"Expected single-parent Alembic head {heads[0]}, got {down_revision}.")
    if not down_revision:
        return "base"
    return down_revision


def _parse_args() -> str:
    parser = ArgumentParser()
    parser.add_argument(
        "--downgrade-target",
        default=None,
        help=(
            "Revision to downgrade to between upgrade runs. Defaults to the "
            "current head's immediate parent. Use 'base' for a full historical "
            "downgrade gate."
        ),
    )
    args = parser.parse_args()
    return args.downgrade_target or ""


def _current(database_url: URL) -> list[str]:
    engine = sa.create_engine(
        _sync_url(database_url),
        connect_args={"prepare_threshold": None},
    )
    try:
        with engine.connect() as connection:
            if not sa.inspect(connection).has_table("alembic_version"):
                return []
            return sorted(
                connection.execute(sa.text("SELECT version_num FROM alembic_version"))
                .scalars()
                .all()
            )
    finally:
        engine.dispose()


def main() -> int:
    requested_downgrade_target = _parse_args()
    app_url = make_url(settings.DATABASE_URL)
    app_url_text = app_url.render_as_string(hide_password=False)
    if not is_local_database_url(app_url_text):
        print(
            "Refusing migration gate against non-local database "
            f"{redact_database_target(app_url_text)}.",
            file=sys.stderr,
        )
        return 2

    database_name = f"lorevia_migration_gate_{uuid.uuid4().hex[:12]}"
    maintenance_url = _maintenance_url(app_url)
    temp_url = _temporary_database_url(app_url, database_name)
    config = _alembic_config()
    heads = _heads(config)
    downgrade_target = requested_downgrade_target or _default_downgrade_target(config)

    print(f"Creating temporary database {database_name}.")
    _create_database(maintenance_url, database_name)
    try:
        with _temporary_alembic_environment(temp_url):
            print("Running alembic upgrade head.")
            command.upgrade(config, "head")
            first_current = _current(temp_url)
            print(f"Current after first upgrade: {first_current}")

            print(f"Running alembic downgrade {downgrade_target}.")
            command.downgrade(config, downgrade_target)
            downgraded_current = _current(temp_url)
            print(f"Current after downgrade: {downgraded_current}")

            print("Running alembic upgrade head again.")
            command.upgrade(config, "head")
            final_current = _current(temp_url)
            print(f"Current after final upgrade: {final_current}")

        if first_current != heads or final_current != heads:
            print(
                f"Alembic current/head mismatch: heads={heads}, "
                f"first={first_current}, final={final_current}",
                file=sys.stderr,
            )
            return 1
        expected_downgraded_current = [] if downgrade_target == "base" else [downgrade_target]
        if downgraded_current != expected_downgraded_current:
            print(
                f"Expected Alembic revision {expected_downgraded_current} "
                f"after downgrade {downgrade_target}, got {downgraded_current}.",
                file=sys.stderr,
            )
            return 1
        print("Temporary migration gate passed.")
        return 0
    finally:
        print(f"Dropping temporary database {database_name}.")
        _drop_database(maintenance_url, database_name)


if __name__ == "__main__":
    raise SystemExit(main())
