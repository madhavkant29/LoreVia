from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / "20260519_remove_beta_read_awarded_at_residue.py"
    )
    spec = spec_from_file_location("remove_beta_read_awarded_at_residue", module_path)
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
        return [{"name": column_name} for column_name in self._state["columns"].get(table_name, set())]

    def get_indexes(self, table_name):
        return [{"name": index_name} for index_name in self._state["indexes"].get(table_name, set())]


class _FakeOp:
    def __init__(self, state):
        self._state = state
        self.dropped_indexes: list[tuple[str, str]] = []
        self.dropped_columns: list[tuple[str, str]] = []
        self.added_indexes: list[tuple[str, str, list[str]]] = []
        self.added_columns: list[tuple[str, str]] = []

    def get_bind(self):
        return object()

    def drop_index(self, name, table_name):
        self._state["indexes"].setdefault(table_name, set()).discard(name)
        self.dropped_indexes.append((table_name, name))

    def drop_column(self, table_name, column_name):
        self._state["columns"].setdefault(table_name, set()).discard(column_name)
        self.dropped_columns.append((table_name, column_name))

    def add_column(self, table_name, column):
        self._state["columns"].setdefault(table_name, set()).add(column.name)
        self.added_columns.append((table_name, column.name))

    def create_index(self, name, table_name, columns):
        self._state["indexes"].setdefault(table_name, set()).add(name)
        self.added_indexes.append((table_name, name, list(columns)))


def test_upgrade_drops_awarded_at_index_and_column(monkeypatch) -> None:
    migration = _load_migration_module()
    state = {
        "tables": {"beta_read_assignments"},
        "columns": {"beta_read_assignments": {"id", "awarded_at", "created_at"}},
        "indexes": {"beta_read_assignments": {"ix_beta_read_assignments_awarded_at"}},
    }
    fake_op = _FakeOp(state)

    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector(state))

    migration.upgrade()

    assert ("beta_read_assignments", "ix_beta_read_assignments_awarded_at") in fake_op.dropped_indexes
    assert ("beta_read_assignments", "awarded_at") in fake_op.dropped_columns
    assert "awarded_at" not in state["columns"]["beta_read_assignments"]
    assert "ix_beta_read_assignments_awarded_at" not in state["indexes"]["beta_read_assignments"]


def test_downgrade_restores_awarded_at_index_and_column(monkeypatch) -> None:
    migration = _load_migration_module()
    state = {
        "tables": {"beta_read_assignments"},
        "columns": {"beta_read_assignments": {"id", "created_at"}},
        "indexes": {"beta_read_assignments": set()},
    }
    fake_op = _FakeOp(state)

    monkeypatch.setattr(migration, "op", fake_op)
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: _FakeInspector(state))

    migration.downgrade()

    assert ("beta_read_assignments", "awarded_at") in fake_op.added_columns
    assert ("beta_read_assignments", "ix_beta_read_assignments_awarded_at", ["awarded_at"]) in fake_op.added_indexes
    assert "awarded_at" in state["columns"]["beta_read_assignments"]
    assert "ix_beta_read_assignments_awarded_at" in state["indexes"]["beta_read_assignments"]
