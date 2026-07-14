from fastapi import APIRouter

from app.api.v1.routes.reader.chapters import router as chapters_router
from app.api.v1.routes.reader.core import get_chapter_media_public
from app.api.v1.routes.reader.core import router as core_router
from app.api.v1.routes.reader.events import router as events_router
from app.api.v1.routes.reader.graph import router as graph_router
from app.api.v1.routes.reader.memory import router as memory_router
from app.api.v1.routes.reader.progress import router as progress_router
from app.api.v1.routes.reader.search import router as search_router
from app.api.v1.routes.reader.timeline import router as timeline_router

router = APIRouter()
router.include_router(core_router)
router.include_router(chapters_router)
router.include_router(progress_router)
router.include_router(events_router)
router.include_router(timeline_router)
router.include_router(memory_router)
router.include_router(search_router)
router.include_router(graph_router)

__all__ = ["router", "get_chapter_media_public"]
