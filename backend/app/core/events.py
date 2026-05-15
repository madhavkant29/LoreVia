import logging

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    log.info("Startup completed without blocking infrastructure checks")


async def on_shutdown() -> None:
    from app.core.database import engine

    await engine.dispose()
    log.info("LoreVia shut down")
