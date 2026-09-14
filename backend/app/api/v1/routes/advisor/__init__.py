from fastapi import APIRouter

from app.api.v1.routes.advisor.beta_reader import router as beta_reader_router
from app.api.v1.routes.advisor.chat import router as chat_router
from app.api.v1.routes.advisor.editing import router as editing_router
from app.api.v1.routes.advisor.jobs import router as jobs_router
from app.api.v1.routes.advisor.reports import router as reports_router
from app.api.v1.routes.advisor.suggestions import router as suggestions_router
from app.api.v1.routes.advisor.synopsis import router as synopsis_router
from app.api.v1.routes.advisor.voice import router as voice_router

router = APIRouter()
router.include_router(beta_reader_router)
router.include_router(chat_router)
router.include_router(editing_router)
router.include_router(suggestions_router)
router.include_router(synopsis_router)
router.include_router(voice_router)
router.include_router(reports_router)
router.include_router(jobs_router)

__all__ = ["router"]
