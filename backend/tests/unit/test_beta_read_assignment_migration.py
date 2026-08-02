from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "20260514_add_beta_read_assignments.py"
    )
    spec = spec_from_file_location("beta_read_assignment_migration", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeInspector:
    def __init__(self, state):
        self._state = state

    def get_table_names(self):
        return list(self._state["tables"])

    def get_columns(self, table_name):
        return [
            {"name": column_name} for column_name in self._state["columns"].get(table_name, set())
        ]

    def get_indexes(self, table_name):
        return [
            {"name": index_name} for index_name in self._state["indexes"].get(table_name, set())
        ]


class _FakeOp:
    def __init__(self, state):
        self._state = state
        self.created_indexes: list[tuple[str, str, list[str]]] = []

    def get_bind(self):
        return object()

    def add_column(self, table_name, column):
        self._state["columns"].setdefault(table_name, set()).add(column.name)

    def create_index(self, name, table_name, columns):
        assert set(columns).issubset(self._state["columns"].get(table_name, set()))
        self._state["indexes"].setdefault(table_name, set()).add(name)
        self.created_indexes.append((name, table_name, list(columns)))


def test_upgrade_skips_awarded_at_index_until_column_exists(monkeypatch) -> None:
    migration = _load_migration_module()
    beta_read_columns = {
        "id",
        "book_id",
        "author_user_id",
        "reader_user_id",
        "collaborator_id",
        "reader_email",
        "state",
        "scope_kind",
        "task_label",
        "section_label",
        "chapter_start",
        "chapter_end",
        "window_days",
        "reward_points",
        "required_progress_pct",
        "required_comment_count",
        "require_final_feedback",
        "starts_at",
        "expires_at",
        "access_granted_at",
        "first_opened_at",
        "submitted_at",
        "completed_at",
        "awarded_points",
        "final_feedback",
        "submission_metadata",
        "reminder_24h_sent_at",
        "reminder_6h_sent_at",
        "missed_reason",
        "counted_toward_missed_streak",
        "revoked_at",
        "revoked_reason",
        "disqualified_at",
        "disqualified_reason",
        "state_changed_at",
        "metadata_json",
        "created_at",
        "updated_at",
    }
    state = {
        "tables": {"beta_read_assignments", "users"},
        "columns": {
            "beta_read_assignments": beta_read_columns,
            "users": set(),
        },
        "indexes": {
            "beta_read_assignments": set(),
            "users": set(),
        },
    }
    fake_op = _FakeOp(state)

    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector(state))

    migration.upgrade()

    created_index_names = {name for name, _table_name, _columns in fake_op.created_indexes}
    assert "ix_beta_read_assignments_awarded_at" not in created_index_names
    assert "ix_beta_read_assignments_completed_at" in created_index_names
    assert "author_questions_json" in state["columns"]["beta_read_assignments"]
    assert "feedback_payload" in state["columns"]["beta_read_assignments"]
