from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "db"}

_UPGRADE_BLOCK_PATTERN = re.compile(
    r"(?ms)^def upgrade\(\)(?: -> None)?:\n(?P<body>.*?)(?=^def downgrade\(\)(?: -> None)?:|\Z)"
)
_DESTRUCTIVE_UPGRADE_PATTERNS = (
    re.compile(r"\bop\.drop_table\s*\("),
    re.compile(r"\bop\.drop_column\s*\("),
    re.compile(r"\bop\.drop_index\s*\("),
    re.compile(r"\bop\.drop_constraint\s*\("),
    re.compile(r"\bBase\.metadata\.drop_all\s*\("),
    re.compile(r"(?i)\bop\.execute\(\s*[\"']\s*DROP\b"),
)


def is_local_database_url(database_url: str) -> bool:
    parsed = urlsplit(database_url)
    host = parsed.hostname or ""
    return not host or host in LOCAL_DATABASE_HOSTS or host.endswith(".local")


def redact_database_target(database_url: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "<unknown>"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    database = parsed.path.lstrip("/") or "<unknown>"
    return f"{parsed.scheme}://{host}/{database}"


def resolve_alembic_database_url(
    explicit_url: str | None,
    fallback_url: str,
) -> tuple[str, bool]:
    if explicit_url:
        return explicit_url, True
    if not is_local_database_url(fallback_url):
        raise ValueError(
            "Refusing to use app settings DATABASE_URL for a remote Alembic run. "
            "Set ALEMBIC_DATABASE_URL explicitly for non-local databases."
        )
    return fallback_url, False


def destructive_upgrade_revisions(versions_dir: Path) -> list[Path]:
    offending: list[Path] = []
    for path in sorted(versions_dir.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        match = _UPGRADE_BLOCK_PATTERN.search(text)
        if not match:
            continue

        body = match.group("body")
        if any(pattern.search(body) for pattern in _DESTRUCTIVE_UPGRADE_PATTERNS):
            offending.append(path)

    return offending
