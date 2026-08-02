import ast
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "app" / "db" / "migrations" / "versions"
IRREVERSIBLE_HISTORY_ALLOWLIST = {
    "20260425_baseline_schema.py",
    "20260429_rebuild_public_schema.py",
}


def test_every_migration_defines_upgrade_and_downgrade() -> None:
    missing: list[str] = []
    for path in MIGRATIONS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if not {"upgrade", "downgrade"}.issubset(functions):
            missing.append(path.name)
    assert missing == []


def test_only_grandfathered_history_has_unconditional_irreversible_downgrade() -> None:
    irreversible: set[str] = set()
    for path in MIGRATIONS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        downgrade = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
            ),
            None,
        )
        if downgrade and downgrade.body and isinstance(downgrade.body[0], ast.Raise):
            irreversible.add(path.name)
    assert irreversible == IRREVERSIBLE_HISTORY_ALLOWLIST
