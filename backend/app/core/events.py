import logging

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    from app.main import _lazy_api_app

    await _lazy_api_app.ensure_app()
    log.info("Startup completed")


async def on_shutdown() -> None:
    from app.core.database import engine
    from app.core.redis import close_all_redis_clients

    await close_all_redis_clients()
    await engine.dispose()
    log.info("LoreVia shut down")
