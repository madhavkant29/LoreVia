from pathlib import Path
from types import SimpleNamespace

from app.utils.migration_utils import (
    CORE_APPLICATION_TABLES,
    create_policy_if_missing,
    destructive_downgrade_revisions,
    destructive_upgrade_revisions,
    enable_row_level_security,
    grant_sequence_privileges,
    grant_supabase_data_api_sequence_access,
    grant_supabase_data_api_table_access,
    grant_table_privileges,
    is_local_database_url,
    redact_database_target,
    resolve_alembic_database_url,
    should_reset_local_alembic_state,
)


def test_is_local_database_url_accepts_local_hosts() -> None:
    assert is_local_database_url("postgresql://postgres:pass@localhost:5432/postgres")
    assert is_local_database_url("postgresql://postgres:pass@127.0.0.1:5432/postgres")
    assert is_local_database_url("postgresql://postgres:pass@[::1]:5432/postgres")
    assert is_local_database_url("postgresql://postgres:pass@postgres:5432/postgres")


def test_is_local_database_url_rejects_remote_hosts() -> None:
    assert not is_local_database_url(
        "postgresql://postgres:pass@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    )


def test_redact_database_target_hides_credentials() -> None:
    target = redact_database_target(
        "postgresql://postgres:secret@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    )
    assert target == "postgresql://aws-1-ap-south-1.pooler.supabase.com:5432/postgres"


def test_resolve_alembic_database_url_prefers_explicit_url() -> None:
    explicit_url, is_explicit = resolve_alembic_database_url(
        "postgresql://postgres:secret@remote.example.com:5432/postgres",
        "postgresql://postgres:secret@localhost:5432/postgres",
    )

    assert explicit_url == "postgresql://postgres:secret@remote.example.com:5432/postgres"
    assert is_explicit is True


def test_resolve_alembic_database_url_rejects_remote_fallback() -> None:
    try:
        resolve_alembic_database_url(
            None,
            "postgresql://postgres:secret@remote.example.com:5432/postgres",
        )
    except ValueError as exc:
        assert "ALEMBIC_DATABASE_URL" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for remote fallback URL")


def test_destructive_upgrade_revisions_ignores_downgrade_only_drops(tmp_path: Path) -> None:
    migration = tmp_path / "20260430_safe.py"
    migration.write_text(
        '''"""Safe migration.

Revision ID: safe
"""

def upgrade() -> None:
    pass

def downgrade() -> None:
    op.drop_table("unsafe")
'''.strip(),
        encoding="utf-8",
    )

    assert destructive_upgrade_revisions(tmp_path) == []


def test_destructive_upgrade_revisions_detects_upgrade_drop_ops(tmp_path: Path) -> None:
    migration = tmp_path / "20260430_bad.py"
    migration.write_text(
        '''"""Unsafe migration.

Revision ID: unsafe
"""

def upgrade() -> None:
    op.drop_table("books")

def downgrade() -> None:
    pass
'''.strip(),
        encoding="utf-8",
    )

    assert destructive_upgrade_revisions(tmp_path) == [migration]


def test_destructive_downgrade_revisions_ignores_upgrade_only_drops(tmp_path: Path) -> None:
    migration = tmp_path / "20260430_safe.py"
    migration.write_text(
        '''"""Safe migration.

Revision ID: safe
"""

def upgrade() -> None:
    op.drop_table("unsafe")

def downgrade() -> None:
    pass
'''.strip(),
        encoding="utf-8",
    )

    assert destructive_downgrade_revisions(tmp_path) == []


def test_destructive_downgrade_revisions_detects_downgrade_drop_ops(tmp_path: Path) -> None:
    migration = tmp_path / "20260430_bad.py"
    migration.write_text(
        '''"""Unsafe migration.

Revision ID: unsafe
"""

def upgrade() -> None:
    pass

def downgrade() -> None:
    op.drop_table("books")
'''.strip(),
        encoding="utf-8",
    )

    assert destructive_downgrade_revisions(tmp_path) == [migration]


def test_should_reset_local_alembic_state_requires_core_tables() -> None:
    assert should_reset_local_alembic_state({"alembic_version"}) is True
    assert should_reset_local_alembic_state({"alembic_version", "users"}) is True


def test_should_reset_local_alembic_state_allows_bootstrapped_schema() -> None:
    assert should_reset_local_alembic_state({"alembic_version", *CORE_APPLICATION_TABLES}) is False
    assert should_reset_local_alembic_state(set(CORE_APPLICATION_TABLES)) is False


def test_grant_table_privileges_executes_expected_sql(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    grant_table_privileges("beta_reader_assignments", grantee="authenticated")

    assert executed == [
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "public"."beta_reader_assignments" TO "authenticated"'
    ]


def test_grant_sequence_privileges_executes_expected_sql(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    grant_sequence_privileges("beta_reader_assignments_id_seq", grantee="authenticated")

    assert executed == [
        'GRANT USAGE, SELECT ON SEQUENCE "public"."beta_reader_assignments_id_seq" TO "authenticated"'
    ]


def test_enable_row_level_security_executes_expected_sql(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    enable_row_level_security("beta_reader_assignments")

    assert executed == ['ALTER TABLE "public"."beta_reader_assignments" ENABLE ROW LEVEL SECURITY']


def test_create_policy_if_missing_executes_expected_do_block(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    create_policy_if_missing(
        "beta_reader_assignments",
        "authors can manage assignments",
        command="ALL",
        using="auth.uid() = author_user_id",
        with_check="auth.uid() = author_user_id",
    )

    assert len(executed) == 1
    assert "FROM pg_policies" in executed[0]
    assert "schemaname = 'public'" in executed[0]
    assert "tablename = 'beta_reader_assignments'" in executed[0]
    assert "policyname = 'authors can manage assignments'" in executed[0]
    assert 'CREATE POLICY "authors can manage assignments"' in executed[0]
    assert 'ON "public"."beta_reader_assignments"' in executed[0]
    assert 'FOR ALL TO "authenticated"' in executed[0]
    assert "USING (auth.uid() = author_user_id)" in executed[0]
    assert "WITH CHECK (auth.uid() = author_user_id)" in executed[0]


def test_grant_supabase_data_api_table_access_grants_authenticated_and_service_role(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    grant_supabase_data_api_table_access("beta_reader_assignments", anon_privileges=("SELECT",))

    assert executed == [
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "public"."beta_reader_assignments" TO "authenticated"',
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "public"."beta_reader_assignments" TO "service_role"',
        'GRANT SELECT ON TABLE "public"."beta_reader_assignments" TO "anon"',
    ]


def test_grant_supabase_data_api_sequence_access_grants_authenticated_and_service_role(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    grant_supabase_data_api_sequence_access("beta_reader_assignments_id_seq")

    assert executed == [
        'GRANT USAGE, SELECT ON SEQUENCE "public"."beta_reader_assignments_id_seq" TO "authenticated"',
        'GRANT USAGE, SELECT ON SEQUENCE "public"."beta_reader_assignments_id_seq" TO "service_role"',
    ]


def test_grant_table_privileges_rejects_empty_privileges(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=lambda _: None),
    )

    try:
        grant_table_privileges("beta_reader_assignments", grantee="authenticated", privileges=())
    except ValueError as exc:
        assert "At least one privilege" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for empty privileges")


def test_create_policy_if_missing_rejects_invalid_command(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=lambda _: None),
    )

    try:
        create_policy_if_missing("beta_reader_assignments", "bad", command="TRUNCATE")
    except ValueError as exc:
        assert "Unsupported policy command" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for invalid policy command")
