from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlsplit

from alembic import op

LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "db"}
CORE_APPLICATION_TABLES = frozenset({"users", "books", "chapters"})
SUPABASE_DATA_API_RW_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")
SUPABASE_DATA_API_SEQUENCE_PRIVILEGES = ("USAGE", "SELECT")
SUPABASE_POLICY_COMMANDS = frozenset({"ALL", "SELECT", "INSERT", "UPDATE", "DELETE"})

_UPGRADE_BLOCK_PATTERN = re.compile(
    r"(?ms)^def upgrade\(\)(?: -> None)?:\n(?P<body>.*?)(?=^def downgrade\(\)(?: -> None)?:|\Z)"
)
_DOWNGRADE_BLOCK_PATTERN = re.compile(
    r"(?ms)^def downgrade\(\)(?: -> None)?:\n(?P<body>.*?)(?=\Z)"
)
_DESTRUCTIVE_UPGRADE_PATTERNS = (
    re.compile(r"\bop\.drop_table\s*\("),
    re.compile(r"\bop\.drop_column\s*\("),
    re.compile(r"\bBase\.metadata\.drop_all\s*\("),
    re.compile(r"(?i)\bop\.execute\(\s*[\"']\s*DROP\b"),
)
_DESTRUCTIVE_DOWNGRADE_PATTERNS = _DESTRUCTIVE_UPGRADE_PATTERNS


def _quote_identifier(identifier: str) -> str:
    if not identifier:
        raise ValueError("Identifier cannot be empty.")
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _normalize_privileges(privileges: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(privilege.strip().upper() for privilege in privileges if privilege and privilege.strip())
    if not normalized:
        raise ValueError("At least one privilege is required.")
    return normalized


def _qualified_name(schema: str, object_name: str) -> str:
    return f"{_quote_identifier(schema)}.{_quote_identifier(object_name)}"


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


def destructive_downgrade_revisions(versions_dir: Path) -> list[Path]:
    offending: list[Path] = []
    for path in sorted(versions_dir.glob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        match = _DOWNGRADE_BLOCK_PATTERN.search(text)
        if not match:
            continue

        body = match.group("body")
        if any(pattern.search(body) for pattern in _DESTRUCTIVE_DOWNGRADE_PATTERNS):
            offending.append(path)

    return offending


def should_reset_local_alembic_state(existing_tables: set[str]) -> bool:
    return "alembic_version" in existing_tables and not CORE_APPLICATION_TABLES.issubset(existing_tables)


def grant_supabase_data_api_table_access(
    table_name: str,
    *,
    schema: str = "public",
    authenticated_privileges: Iterable[str] = SUPABASE_DATA_API_RW_PRIVILEGES,
    service_role_privileges: Iterable[str] = SUPABASE_DATA_API_RW_PRIVILEGES,
    anon_privileges: Iterable[str] = (),
) -> None:
    grant_table_privileges(
        table_name,
        grantee="authenticated",
        schema=schema,
        privileges=authenticated_privileges,
    )
    grant_table_privileges(
        table_name,
        grantee="service_role",
        schema=schema,
        privileges=service_role_privileges,
    )
    anon_privileges_tuple = tuple(anon_privileges)
    if anon_privileges_tuple:
        grant_table_privileges(
            table_name,
            grantee="anon",
            schema=schema,
            privileges=anon_privileges_tuple,
        )


def grant_supabase_data_api_sequence_access(
    sequence_name: str,
    *,
    schema: str = "public",
    authenticated_privileges: Iterable[str] = SUPABASE_DATA_API_SEQUENCE_PRIVILEGES,
    service_role_privileges: Iterable[str] = SUPABASE_DATA_API_SEQUENCE_PRIVILEGES,
    anon_privileges: Iterable[str] = (),
) -> None:
    grant_sequence_privileges(
        sequence_name,
        grantee="authenticated",
        schema=schema,
        privileges=authenticated_privileges,
    )
    grant_sequence_privileges(
        sequence_name,
        grantee="service_role",
        schema=schema,
        privileges=service_role_privileges,
    )
    anon_privileges_tuple = tuple(anon_privileges)
    if anon_privileges_tuple:
        grant_sequence_privileges(
            sequence_name,
            grantee="anon",
            schema=schema,
            privileges=anon_privileges_tuple,
        )


def grant_table_privileges(
    table_name: str,
    *,
    grantee: str,
    schema: str = "public",
    privileges: Iterable[str] = SUPABASE_DATA_API_RW_PRIVILEGES,
) -> None:
    normalized_privileges = ", ".join(_normalize_privileges(privileges))
    op.execute(
        f"GRANT {normalized_privileges} ON TABLE {_qualified_name(schema, table_name)} TO {_quote_identifier(grantee)}"
    )


def grant_sequence_privileges(
    sequence_name: str,
    *,
    grantee: str,
    schema: str = "public",
    privileges: Iterable[str] = SUPABASE_DATA_API_SEQUENCE_PRIVILEGES,
) -> None:
    normalized_privileges = ", ".join(_normalize_privileges(privileges))
    op.execute(
        f"GRANT {normalized_privileges} ON SEQUENCE {_qualified_name(schema, sequence_name)} TO {_quote_identifier(grantee)}"
    )


def enable_row_level_security(table_name: str, *, schema: str = "public") -> None:
    op.execute(f"ALTER TABLE {_qualified_name(schema, table_name)} ENABLE ROW LEVEL SECURITY")


def create_policy_if_missing(
    table_name: str,
    policy_name: str,
    *,
    command: str = "ALL",
    roles: Iterable[str] = ("authenticated",),
    using: str | None = None,
    with_check: str | None = None,
    schema: str = "public",
) -> None:
    policy_command = command.strip().upper()
    if policy_command not in SUPABASE_POLICY_COMMANDS:
        raise ValueError(f"Unsupported policy command: {command}")

    normalized_roles = tuple(role.strip() for role in roles if role and role.strip())
    if not normalized_roles:
        raise ValueError("At least one policy role is required.")

    clauses = [
        f"CREATE POLICY {_quote_identifier(policy_name)}",
        f"ON {_qualified_name(schema, table_name)}",
        f"FOR {policy_command}",
        f"TO {', '.join(_quote_identifier(role) for role in normalized_roles)}",
    ]
    if using:
        clauses.append(f"USING ({using})")
    if with_check:
        clauses.append(f"WITH CHECK ({with_check})")

    policy_sql = " ".join(clauses)
    op.execute(
        "\n".join(
            (
                "DO $$",
                "BEGIN",
                "    IF NOT EXISTS (",
                "        SELECT 1",
                "        FROM pg_policies",
                f"        WHERE schemaname = {_quote_literal(schema)}",
                f"          AND tablename = {_quote_literal(table_name)}",
                f"          AND policyname = {_quote_literal(policy_name)}",
                "    ) THEN",
                f"        EXECUTE {_quote_literal(policy_sql)};",
                "    END IF;",
                "END",
                "$$;",
            )
        )
    )
