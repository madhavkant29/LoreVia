"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""

from fastapi import APIRouter

# ── Routers ─────────────────────────────────────────────────────────────────
from app.api.v1.routes.reader.core import (
    get_chapter_media_public,
)
from app.api.v1.routes.reader.core import (
    router as core_router,
)
from app.api.v1.routes.reader.graph import router as graph_router
from app.api.v1.routes.reader.progress import router as progress_router
from app.api.v1.routes.reader.timeline import router as timeline_router

router = APIRouter()
router.include_router(core_router)
router.include_router(progress_router)
router.include_router(timeline_router)
router.include_router(graph_router)

# ══════════════════════════════════════════════════════════════════════════════
# Re-exports for unit test monkeypatch compatibility.
# Tests use  monkeypatch.setattr(reader, "name", ...)  so each name below
# must be importable as an attribute of this package.
# ══════════════════════════════════════════════════════════════════════════════

# ── reader.core (endpoint handlers) ─────────────────────────────────────────
from app.api.v1.routes.reader.core import (  # noqa: E402, F401
    _clean_text,
    get_chapter,
    get_chapter_list,
    get_summary,
    get_summary_collection,
    save_quote,
    search,
    smart_tap,
    thematic_search,
)

# ── reader.graph ────────────────────────────────────────────────────────────
from app.api.v1.routes.reader.graph import (  # noqa: E402, F401
    get_relationship_evolution,
    get_relationships,
)

# ── reader.progress ─────────────────────────────────────────────────────────
from app.api.v1.routes.reader.progress import (  # noqa: E402, F401
    get_progress,
    mark_book_read,
    update_chapter_read_status,
    update_progress,
)

# ── reader.timeline ─────────────────────────────────────────────────────────
from app.api.v1.routes.reader.timeline import (  # noqa: E402, F401
    _normalize_reader_character_event,
    _normalize_reader_major_event,
    get_foreshadowing_highlights,
    get_plot_threads,
    get_reader_events,
    get_timeline,
    memory_recall,
    save_plot_thread_note,
)

# ── app.core ────────────────────────────────────────────────────────────────
from app.core.config import is_local_mode  # noqa: E402, F401
from app.core.redis import (  # noqa: E402, F401
    cache_get,
    cache_set,
    get_book_cache_version,
    get_reader_events_cache,
    get_reader_progress_cache_version,
    get_reader_timeline_cache,
    get_relationship_evolution_cache,
    key_memory_recall,
    mark_reader_progress_cache_dirty,
    set_reader_events_cache,
    set_reader_timeline_cache,
    set_relationship_evolution_cache,
)
from app.core.security import decode_token  # noqa: E402, F401
from app.core.storage import download_book  # noqa: E402, F401

# ── engine ──────────────────────────────────────────────────────────────────
from app.engine.analysis.recall import generate_recall  # noqa: E402, F401
from app.engine.character.consolidator import consolidate_characters  # noqa: E402, F401
from app.engine.search.semantic import (  # noqa: E402, F401
    build_search_result,
    find_context_for_tap,
    semantic_search,
)

# ── services ────────────────────────────────────────────────────────────────
from app.services.chapter_recovery_service import resolve_reader_chapter_payload  # noqa: E402, F401
from app.services.summary_service import get_or_generate_summary  # noqa: E402, F401

# ── utils ───────────────────────────────────────────────────────────────────
from app.utils.beta_read_utils import sync_beta_assignments_for_reader_book  # noqa: E402, F401
from app.utils.billing_utils import summary_mode_allowed  # noqa: E402, F401
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.characters.manual import backfill_character_first_chapters_for_chapter_text
from app.utils.characters.serialization import serialize_reader_character
from app.utils.queue_utils import queue_for_user  # noqa: E402, F401

# ── reader_utils ────────────────────────────────────────────────────────────
from app.utils.reader_utils import (  # noqa: E402, F401
    build_timeline_track_payload,
    chapter_intelligence_available,
    chapter_intelligence_map,
    collapse_graph_characters,
    dedupe_timeline_events,
    graph_character_visibility_analysis,
    is_graph_character_visible,
    is_valid_timeline_character,
    list_plot_threads,
    normalize_summary_response,
    queue_analysis_if_missing,
    read_chapter_set,
    relationship_node_description,
    require_summary_access,
    summary_visible_chapter_set,
    timeline_character_detail,
    timeline_plot_thread_span,
    timeline_relationship_detail,
    timeline_visible_chapter_set,
    update_plot_thread_note,
)
from app.utils.tag_utils import (  # noqa: E402, F401
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)

__all__ = ["router", "get_chapter_media_public"]


import importlib  # noqa: E402
import sys  # noqa: E402
from types import ModuleType  # noqa: E402

_PATCH_TARGET_MODULES = tuple(
    importlib.import_module(module_name)
    for module_name in (
        "app.api.v1.routes.reader.core",
        "app.api.v1.routes.reader.graph",
        "app.api.v1.routes.reader.progress",
        "app.api.v1.routes.reader.timeline",
    )
)


class _PatchPropagatingModule(ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for target_module in _PATCH_TARGET_MODULES:
            if hasattr(target_module, name):
                setattr(target_module, name, value)


sys.modules[__name__].__class__ = _PatchPropagatingModule
