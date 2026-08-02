"""Non-blocking repository hygiene report for cleanup planning."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERSIZED_LINE_LIMIT = 500
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
    "venv",
}
ARTIFACT_SUFFIXES = {".log", ".tsbuildinfo", ".pyc"}
LEGACY_PRODUCT_ALIASES = {
    "pro",
    "power",
    "pro_monthly",
    "pro_annual",
    "power_monthly",
    "power_annual",
}
LEGACY_ALIAS_ALLOWED_PATH_PARTS = {
    "backend/app/utils/billing_utils.py",
    "backend/scripts/repo_hygiene_report.py",
    "frontend/src/lib/billing/plans.ts",
}


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _route_layer_smells(path: Path) -> list[str]:
    if "backend/app/api/v1/routes" not in path.as_posix() or path.suffix != ".py":
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    smells: list[str] = []
    for marker in ("open(", "boto3.", "json.dumps(", "asyncio.to_thread("):
        if marker in text:
            smells.append(marker)
    return smells


def _forbidden_aliases(path: Path) -> list[str]:
    if path.suffix != ".py":
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    aliases: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.asname and alias.asname.startswith("_"):
                    aliases.append(f"{alias.name} as {alias.asname}")
    return aliases


def _legacy_product_aliases(path: Path) -> list[str]:
    relative = path.relative_to(REPO_ROOT).as_posix()
    if relative in LEGACY_ALIAS_ALLOWED_PATH_PARTS:
        return []
    if (
        "/tests/" in f"/{relative}"
        or relative.startswith("backend/scripts/")
        or relative.startswith("frontend/src/lib/billing/pricing-catalog")
    ):
        return []
    if path.suffix not in {".py", ".ts", ".tsx"}:
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    found: list[str] = []
    for alias in LEGACY_PRODUCT_ALIASES:
        if f'"{alias}"' in text or f"'{alias}'" in text:
            found.append(alias)
    return found


def main() -> int:
    oversized: list[tuple[Path, int]] = []
    route_smells: list[tuple[Path, list[str]]] = []
    forbidden_aliases: list[tuple[Path, list[str]]] = []
    legacy_aliases: list[tuple[Path, list[str]]] = []
    artifacts: list[Path] = []

    for path in _iter_source_files():
        relative = path.relative_to(REPO_ROOT)
        lines = _line_count(path) if path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"} else 0
        if lines > OVERSIZED_LINE_LIMIT:
            oversized.append((relative, lines))
        smells = _route_layer_smells(path)
        if smells:
            route_smells.append((relative, smells))
        aliases = _forbidden_aliases(path)
        if aliases:
            forbidden_aliases.append((relative, aliases))
        product_aliases = _legacy_product_aliases(path)
        if product_aliases:
            legacy_aliases.append((relative, product_aliases))
        if path.suffix in ARTIFACT_SUFFIXES:
            artifacts.append(relative)

    print("Repository hygiene report (non-blocking)")
    print(f"Oversized files > {OVERSIZED_LINE_LIMIT} lines: {len(oversized)}")
    for relative, lines in sorted(oversized, key=lambda item: (-item[1], str(item[0])))[:30]:
        print(f"  {relative}: {lines}")
    print(f"Route-layer smell candidates: {len(route_smells)}")
    for relative, smells in sorted(route_smells, key=lambda item: str(item[0]))[:30]:
        print(f"  {relative}: {', '.join(sorted(set(smells)))}")
    print(f"Forbidden import alias candidates: {len(forbidden_aliases)}")
    for relative, aliases in sorted(forbidden_aliases, key=lambda item: str(item[0]))[:30]:
        print(f"  {relative}: {', '.join(aliases)}")
    print(f"Legacy product alias candidates: {len(legacy_aliases)}")
    for relative, aliases in sorted(legacy_aliases, key=lambda item: str(item[0]))[:30]:
        print(f"  {relative}: {', '.join(sorted(set(aliases)))}")
    print(f"Repository artifact candidates: {len(artifacts)}")
    for relative in sorted(artifacts)[:30]:
        print(f"  {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
