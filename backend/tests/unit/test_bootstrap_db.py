from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_bootstrap_db_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_db.py"
    spec = spec_from_file_location("bootstrap_db_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_db_upgrades_all_heads(monkeypatch) -> None:
    bootstrap_db = _load_bootstrap_db_module()
    alembic_calls: list[tuple[str, ...]] = []
    table_snapshots = [set(), set(bootstrap_db.CORE_APPLICATION_TABLES)]

    monkeypatch.setattr(bootstrap_db, "_existing_tables", lambda: table_snapshots.pop(0))
    monkeypatch.setattr(bootstrap_db, "_run_alembic", lambda *args: alembic_calls.append(args) or 0)

    exit_code = bootstrap_db.main()

    assert exit_code == 0
    assert alembic_calls == [("upgrade", "heads")]
