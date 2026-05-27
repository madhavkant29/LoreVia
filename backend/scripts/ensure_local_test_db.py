from __future__ import annotations

import sys
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.utils.migration_utils import is_safe_test_database_url, redact_database_target
from app.utils.logging import get_logger

log = get_logger("lorevia.ensure_local_test_db")

def _raw_test_database_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL")


def _admin_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/postgres", parsed.query, parsed.fragment))


def main() -> int:
    test_database_url = _raw_test_database_url()
    if not test_database_url:
        log.info("ensure_local_test_db_skip", extra={"reason": "TEST_DATABASE_URL is not set"})
        return 0

    if not is_safe_test_database_url(settings.DATABASE_URL, test_database_url):
        log.info(
            "ensure_local_test_db_skip",
            extra={
                "reason": "TEST_DATABASE_URL is not a safe local test database target",
                "database": redact_database_target(test_database_url),
            },
        )
        return 0

    parsed = urlsplit(test_database_url)
    database_name = parsed.path.lstrip("/")
    if not database_name:
        log.error("ensure_local_test_db_missing_name")
        return 1

    admin_url = _admin_database_url(test_database_url)
    try:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
                    log.info(
                        "ensure_local_test_db_created",
                        extra={"database": redact_database_target(test_database_url)},
                    )
                else:
                    log.info(
                        "ensure_local_test_db_exists",
                        extra={"database": redact_database_target(test_database_url)},
                    )
    except Exception:
        log.exception(
            "ensure_local_test_db_failed",
            extra={
                "database": redact_database_target(test_database_url),
                "admin_database": redact_database_target(admin_url),
            },
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
