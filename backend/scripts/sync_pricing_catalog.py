"""Sync the backend-owned pricing catalog to the tracked frontend copy.

Run from the repository root:
    python backend/scripts/sync_pricing_catalog.py
    python backend/scripts/sync_pricing_catalog.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "backend" / "app" / "data" / "pricing-catalog.json"
TARGET = REPO_ROOT / "frontend" / "src" / "lib" / "billing" / "pricing-catalog.json"


def _canonical_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the frontend copy is stale.")
    args = parser.parse_args()

    expected = _canonical_json(SOURCE)
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    if args.check:
        if current != expected:
            print(
                f"Pricing catalog drift: {TARGET.relative_to(REPO_ROOT)} is not synced "
                f"from {SOURCE.relative_to(REPO_ROOT)}.",
                file=sys.stderr,
            )
            return 1
        print("Pricing catalog is synced.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8")
    print(f"Synced {TARGET.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
