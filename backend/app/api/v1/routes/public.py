from fastapi import APIRouter

from app.api.v1.routes.public_catalog import router as catalog_router
from app.api.v1.routes.public_forum import router as forum_router
from app.api.v1.routes.public_shared import router as shared_router

router = APIRouter()
router.include_router(forum_router)
router.include_router(catalog_router)
router.include_router(shared_router)

__all__ = ["router"]
