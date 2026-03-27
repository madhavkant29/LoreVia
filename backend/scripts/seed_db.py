"""Seed test user. Usage: python scripts/seed_db.py"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from sqlalchemy import select


async def seed():
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(User).where(User.email == "test@lorevia.app"))).scalar():
            print("Seed user exists")
            return
        user = User(email="test@lorevia.app", password_hash=hash_password("testpass123"), tier="power")
        db.add(user)
        await db.commit()
        print(f"Created: {user.email} (power tier) id={user.id}")

if __name__ == "__main__":
    asyncio.run(seed())
