import argparse
import asyncio
import json

from app.core.database import AsyncSessionLocal
from app.services.monetization_service import send_due_trial_emails


async def _run(limit: int) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        result = await send_due_trial_emails(db, limit=limit)
        await db.commit()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Send due LoreVia trial emails.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum due trial emails to process in one run.")
    args = parser.parse_args()

    result = asyncio.run(_run(max(1, args.limit)))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
