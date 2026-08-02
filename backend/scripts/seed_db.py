"""Seed test user. Usage: python scripts/seed_db.py"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.utils.logging import get_logger

log = get_logger("lorevia.seed")


async def seed():
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(User).where(User.email == "test@lorevia.app"))).scalar():
            log.info("seed_user_exists", extra={"email": "test@lorevia.app"})
            return
        user = User(
            email="test@lorevia.app", password_hash=hash_password("testpass123"), tier="power"
        )
        db.add(user)
        await db.commit()
        log.info(
            "seed_user_created",
            extra={"email": user.email, "tier": user.tier, "user_id": str(user.id)},
        )


if __name__ == "__main__":
    asyncio.run(seed())
