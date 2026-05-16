from fastapi import APIRouter, Depends

from app.api.deps.rate_limit import rate_limit_api, rate_limit_public, rate_limit_public_asset
from app.api.v1.routes import (
    admin,
    advisor,
    auth,
    beta_reads,
    billing,
    books,
    characters,
    collaboration,
    internal,
    intelligence,
    manuscript,
    notifications,
    public,
    reader,
    webhooks,
    world_building,
)

api_router = APIRouter()
api_router.include_router(auth.router,          prefix="/auth",          tags=["auth"])

# Add public cover endpoint FIRST (before books router) to ensure it takes precedence
api_router.add_api_route(
    "/books/{book_id}/cover",
    books.get_book_cover_public,
    methods=["GET"],
    dependencies=[Depends(rate_limit_public_asset)],
)
api_router.add_api_route(
    "/books/{book_id}/characters/{character_id}/card",
    books.get_book_character_card_public,
    methods=["GET"],
    dependencies=[Depends(rate_limit_public_asset)],
)
api_router.add_api_route(
    "/reader/media/{media_id}",
    reader.get_chapter_media_public,
    methods=["GET"],
    dependencies=[Depends(rate_limit_public_asset)],
)

api_router.include_router(collaboration.router, prefix="/books",         tags=["collaboration"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(books.router,         prefix="/books",         tags=["books"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(manuscript.router,    prefix="/books",         tags=["manuscript"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(public.router,        prefix="/public",        tags=["public"], dependencies=[Depends(rate_limit_public)])
api_router.include_router(billing.router,       prefix="/billing",       tags=["billing"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(beta_reads.router,    tags=["beta-reads"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(internal.router,      prefix="/internal",      tags=["internal"])
api_router.include_router(webhooks.router,      prefix="/webhooks",      tags=["webhooks"])
api_router.include_router(characters.router,    prefix="/characters",    tags=["characters"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(reader.router,        prefix="/reader",        tags=["reader"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(intelligence.router,  prefix="/intelligence",  tags=["intelligence"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(advisor.router,       prefix="/intelligence",  tags=["advisor"],      dependencies=[Depends(rate_limit_api)])
api_router.include_router(world_building.router, prefix="/intelligence", tags=["world-building"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(admin.router,         prefix="/admin",         tags=["admin"], dependencies=[Depends(rate_limit_api)])
