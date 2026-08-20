from fastapi import APIRouter

from app.api.v1.routes.books.bootstrap import router as bootstrap_router
from app.api.v1.routes.books.characters import router as characters_router
from app.api.v1.routes.books.continuity import router as continuity_router
from app.api.v1.routes.books.core import BookOut, list_books
from app.api.v1.routes.books.core import router as core_router
from app.api.v1.routes.books.events import router as events_router
from app.api.v1.routes.books.exports import router as exports_router
from app.api.v1.routes.books.imports import router as imports_router
from app.api.v1.routes.books.intelligence import router as intelligence_router
from app.api.v1.routes.books.lifecycle import (
    get_book_character_card_public,
    get_book_cover_public,
)
from app.api.v1.routes.books.lifecycle import router as lifecycle_router
from app.api.v1.routes.books.notes import router as notes_router
from app.api.v1.routes.books.publish import router as publish_router
from app.api.v1.routes.books.revision_workflow import router as revision_workflow_router
from app.api.v1.routes.books.series import router as series_router
from app.api.v1.routes.books.visibility import router as visibility_router

router = APIRouter()

router.include_router(core_router)
router.include_router(intelligence_router)
router.include_router(continuity_router)
router.include_router(bootstrap_router)
router.include_router(lifecycle_router)
router.include_router(imports_router)
router.include_router(exports_router)
router.include_router(characters_router)
router.include_router(series_router)
router.include_router(notes_router)
router.include_router(publish_router)
router.include_router(events_router)
router.include_router(visibility_router)
router.include_router(revision_workflow_router)

__all__ = [
    "router",
    "BookOut",
    "list_books",
    "get_book_cover_public",
    "get_book_character_card_public",
]
