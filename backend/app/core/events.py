import logging

from app.core.database import engine
from app.core.redis import get_redis

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    async with engine.connect() as conn:
        await conn.exec_driver_sql("SELECT 1")
    r = await get_redis()
    await r.ping()
    log.info("DB + Redis ready")


async def on_shutdown() -> None:
    await engine.dispose()
    log.info("LoreVia shut down")
