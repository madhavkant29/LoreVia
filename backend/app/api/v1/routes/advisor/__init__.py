"""
Story Advisor — author-mode intelligence endpoint.
RAG-grounded conversation: embeds each user message, retrieves top-5 relevant
chunks, sends only those chunks + last 10 conversation turns to GPT-4o-mini.

Also provides:
- /advisor/suggestions  — proactive scan for plotholes, dropped threads, dead
                          characters, unused setups, future directions (DB-only)
- /advisor/message      — conversational turn
"""

from fastapi import APIRouter
from openai import AsyncOpenAI

from app.api.v1.routes.advisor.chat import (
    _advisor_sse,
    _advisor_stream_response,
    _best_issue_snippet,
    _enqueue_book_advisor_task,
    _parse_advisor_job_id,
    _safe_prompt_str,
    advisor_greeting,
    advisor_message,
    advisor_message_async,
    advisor_message_async_status,
    advisor_message_stream,
    whats_the_word,
    whats_the_word_stream,
)
from app.api.v1.routes.advisor.chat import router as chat_router
from app.api.v1.routes.advisor.jobs import (
    SeriesContinuityRequest,
    _enqueue_series_advisor_task,
    series_advisor_message,
    series_advisor_message_status,
    series_advisor_message_stream,
    series_continuity_check,
    series_continuity_check_stream,
)
from app.api.v1.routes.advisor.jobs import router as jobs_router
from app.api.v1.routes.advisor.suggestions import (
    advisor_suggestions,
    advisor_suggestions_job_status,
    advisor_suggestions_scan,
)
from app.api.v1.routes.advisor.suggestions import router as suggestions_router
from app.api.v1.routes.advisor.synopsis import (
    continuity_report,
    editorial_review,
    editorial_review_stream,
    inline_continuity_check,
    inline_continuity_check_stream,
    manuscript_synopsis,
    manuscript_synopsis_stream,
    prose_tighten,
    prose_tighten_stream,
    voice_consistency_review,
    voice_consistency_review_stream,
)
from app.api.v1.routes.advisor.synopsis import router as synopsis_router
from app.core.config import settings
from app.core.redis import (
    get_advisor_response_cache,
    get_editorial_review_cache,
    get_proactive_scan_cache,
    get_prose_tighten_cache,
    get_series_advisor_response_cache,
    get_series_continuity_cache,
    get_suggestion_scan_cache,
    get_synopsis_cache,
    get_voice_consistency_cache,
    set_advisor_response_cache,
    set_editorial_review_cache,
    set_proactive_scan_cache,
    set_prose_tighten_cache,
    set_series_advisor_response_cache,
    set_series_continuity_cache,
    set_suggestion_scan_cache,
    set_synopsis_cache,
    set_voice_consistency_cache,
)
from app.core.storage import download_book
from app.engine.search.semantic import semantic_search
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_BOOK,
    ADVISOR_SCOPE_SERIES,
    create_advisor_job,
    mark_advisor_job_failed,
    serialize_advisor_job,
)
from app.utils.advisor_utils import (
    build_advisor_suggestions_payload,
    build_character_voice_context,
    build_continuity_report_markdown,
    build_continuity_report_pdf,
    build_fallback_advisor_suggestions,
    build_series_story_context,
    build_story_context,
    generate_whats_the_word_result,
    identify_character_mentions,
    make_advisor_cache_key,
    make_editorial_cache_key,
    normalize_editorial_review_result,
    normalize_prose_tighten_result,
    normalize_series_continuity_result,
    normalize_synopsis_result,
    normalize_voice_consistency_result,
    retrieve_series_continuity_passages,
    stream_advisor_reply_payload,
    stream_series_advisor_reply_payload,
)
from app.utils.books.continuity import detect_chapter_continuity_flags
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    score_voice_match,
)
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
)
from app.workers.tasks.intelligence_tasks import (
    generate_advisor_reply_task,
    generate_advisor_suggestions_task,
    generate_series_advisor_reply_task,
)

router = APIRouter()
router.include_router(chat_router)
router.include_router(suggestions_router)
router.include_router(synopsis_router)
router.include_router(jobs_router)


import importlib  # noqa: E402
import sys  # noqa: E402
from types import ModuleType  # noqa: E402

_PATCH_TARGET_MODULES = tuple(
    importlib.import_module(module_name)
    for module_name in (
        "app.api.v1.routes.advisor.chat",
        "app.api.v1.routes.advisor.suggestions",
        "app.api.v1.routes.advisor.synopsis",
        "app.api.v1.routes.advisor.jobs",
    )
)


class _PatchPropagatingModule(ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for target_module in _PATCH_TARGET_MODULES:
            if hasattr(target_module, name):
                setattr(target_module, name, value)
            if name == "advisor_suggestions" and hasattr(
                target_module, "_suggestions_advisor_suggestions"
            ):
                setattr(target_module, "_suggestions_advisor_suggestions", value)


sys.modules[__name__].__class__ = _PatchPropagatingModule
