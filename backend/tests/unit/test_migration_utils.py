from pathlib import Path
from types import SimpleNamespace

import sqlalchemy as sa

from app.utils.migration_utils import (
    CORE_APPLICATION_TABLES,
    LEGACY_METADATA_BOOTSTRAP_EXCLUDED_TABLES,
    create_policy_if_missing,
    destructive_downgrade_revisions,
    destructive_upgrade_revisions,
    drop_orphan_table_rowtype_if_present,
    drop_orphan_table_rowtype_if_present_on_connection,
    drop_orphan_table_rowtype_if_present_sql,
    enable_row_level_security,
    grant_sequence_privileges,
    grant_supabase_data_api_sequence_access,
    grant_supabase_data_api_table_access,
    grant_table_privileges,
    is_local_database_url,
    is_safe_test_database_url,
    legacy_bootstrap_metadata_tables,
    normalized_database_target,
    parse_revision_allowlist,
    redact_database_target,
    resolve_alembic_database_url,
    revision_paths_excluding_allowlist,
    should_reset_local_alembic_state,
    unapplied_revision_paths,
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


def test_normalized_database_target_collapses_local_host_aliases() -> None:
    assert normalized_database_target("postgresql://postgres:pass@postgres:5432/lorevia") == (
        "local",
        5432,
        "lorevia",
    )
    assert normalized_database_target("postgresql://postgres:pass@127.0.0.1:5432/lorevia") == (
        "local",
        5432,
        "lorevia",
    )


def test_is_safe_test_database_url_rejects_same_local_database() -> None:
    assert not is_safe_test_database_url(
        "postgresql://postgres:pass@postgres:5432/lorevia",
        "postgresql://postgres:pass@127.0.0.1:5432/lorevia",
    )


def test_is_safe_test_database_url_accepts_distinct_local_test_database() -> None:
    assert is_safe_test_database_url(
        "postgresql://postgres:pass@postgres:5432/lorevia",
        "postgresql://postgres:pass@postgres:5432/lorevia_test",
    )


def test_is_safe_test_database_url_rejects_remote_test_database() -> None:
    assert not is_safe_test_database_url(
        "postgresql://postgres:pass@postgres:5432/lorevia",
        "postgresql://postgres:pass@remote.example.com:5432/lorevia_test",
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


def test_unapplied_revision_paths_excludes_current_revision_ancestry(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    pending = tmp_path / "pending.py"
    script_directory = SimpleNamespace(
        walk_revisions=lambda **_kwargs: [
            SimpleNamespace(path=str(second)),
            SimpleNamespace(path=str(first)),
        ]
    )

    assert unapplied_revision_paths(
        [first, second, pending],
        script_directory=script_directory,
        current_heads=["second"],
    ) == [pending]


def test_unapplied_revision_paths_keeps_every_revision_for_empty_database(
    tmp_path: Path,
) -> None:
    migration = tmp_path / "pending.py"
    script_directory = SimpleNamespace(walk_revisions=lambda **_kwargs: (_ for _ in ()))

    assert unapplied_revision_paths(
        [migration],
        script_directory=script_directory,
        current_heads=[],
    ) == [migration]


def test_parse_revision_allowlist_accepts_commas_and_whitespace() -> None:
    assert parse_revision_allowlist("first, second\nthird") == {"first", "second", "third"}


def test_revision_paths_excluding_allowlist_uses_exact_revision_ids(tmp_path: Path) -> None:
    reviewed = tmp_path / "reviewed.py"
    still_blocked = tmp_path / "still_blocked.py"
    script_directory = SimpleNamespace(
        walk_revisions=lambda: [
            SimpleNamespace(revision="reviewed_revision", path=str(reviewed)),
            SimpleNamespace(revision="blocked_revision", path=str(still_blocked)),
        ]
    )

    assert revision_paths_excluding_allowlist(
        [reviewed, still_blocked],
        script_directory=script_directory,
        allowed_revision_ids={"reviewed_revision"},
    ) == [still_blocked]


def test_should_reset_local_alembic_state_requires_core_tables() -> None:
    assert should_reset_local_alembic_state({"alembic_version"}) is True
    assert should_reset_local_alembic_state({"alembic_version", "users"}) is True


def test_should_reset_local_alembic_state_allows_bootstrapped_schema() -> None:
    assert should_reset_local_alembic_state({"alembic_version", *CORE_APPLICATION_TABLES}) is False
    assert should_reset_local_alembic_state(set(CORE_APPLICATION_TABLES)) is False


def test_legacy_bootstrap_metadata_tables_excludes_tables_with_explicit_history() -> None:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    for table_name in LEGACY_METADATA_BOOTSTRAP_EXCLUDED_TABLES:
        sa.Table(table_name, metadata, sa.Column("id", sa.Integer, primary_key=True))

    table_names = {table.name for table in legacy_bootstrap_metadata_tables(metadata)}

    assert table_names == {"users"}


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


def test_grant_supabase_data_api_table_access_grants_authenticated_and_service_role(
    monkeypatch,
) -> None:
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


def test_grant_supabase_data_api_sequence_access_grants_authenticated_and_service_role(
    monkeypatch,
) -> None:
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


def test_drop_orphan_table_rowtype_if_present_executes_expected_do_block(monkeypatch) -> None:
    executed: list[str] = []
    monkeypatch.setattr(
        "app.utils.migration_utils.op",
        SimpleNamespace(execute=executed.append),
    )

    drop_orphan_table_rowtype_if_present("users")

    assert len(executed) == 1
    assert "FROM pg_class c" in executed[0]
    assert "FROM pg_type t" in executed[0]
    assert "c.relkind IN ('r', 'p', 'v', 'm', 'f')" in executed[0]
    assert "c.relname = 'users'" in executed[0]
    assert "t.typname = 'users'" in executed[0]
    assert "DROP TYPE " in executed[0]
    assert '"public"."users"' in executed[0]


def test_drop_orphan_table_rowtype_if_present_sql_returns_expected_do_block() -> None:
    sql = drop_orphan_table_rowtype_if_present_sql("users")

    assert "FROM pg_class c" in sql
    assert "FROM pg_type t" in sql
    assert "c.relkind IN ('r', 'p', 'v', 'm', 'f')" in sql
    assert "c.relname = 'users'" in sql
    assert "t.typname = 'users'" in sql
    assert "DROP TYPE " in sql
    assert '"public"."users"' in sql


def test_drop_orphan_table_rowtype_if_present_on_connection_executes_expected_sql() -> None:
    executed: list[object] = []

    class FakeConnection:
        def execute(self, statement: object) -> None:
            executed.append(statement)

    drop_orphan_table_rowtype_if_present_on_connection(FakeConnection(), "users")

    assert len(executed) == 1
    statement = executed[0]
    assert getattr(statement, "text", "") == drop_orphan_table_rowtype_if_present_sql("users")
