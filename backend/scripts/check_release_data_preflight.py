"""Run the aggregate-only, read-only release data preflight.

The report contains counts and constraint names only. It never prints row IDs,
user IDs, book IDs, chapter IDs, manuscript text, or database credentials.

Run inside the configured backend container:
    python scripts/check_release_data_preflight.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import engine
from app.services.release_data_preflight_service import audit_release_data_from_engine
from app.utils.migration_utils import redact_database_target


async def main() -> int:
    try:
        preflight = await audit_release_data_from_engine(engine)
        report = {
            "database_target": redact_database_target(settings.DATABASE_URL),
            **preflight.as_dict(),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if preflight.safe_for_constraint_rollout else 2
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
