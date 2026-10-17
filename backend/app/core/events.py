import logging

log = logging.getLogger("lorevia.startup")


async def on_startup() -> None:
    log.info("LoreVia starting up")
    from app.main import _lazy_api_app

    await _lazy_api_app.ensure_app()
    log.info("Startup completed")


async def on_shutdown() -> None:
    from app.core.database import engine
    from app.core.llm import close_openai_clients
    from app.core.redis import close_all_redis_clients
    from app.engine.embeddings.embedder import close_embedding_client

    try:
        await close_openai_clients()
    finally:
        try:
            await close_embedding_client()
        finally:
            try:
                await close_all_redis_clients()
            finally:
                await engine.dispose()
    log.info("LoreVia shut down")
