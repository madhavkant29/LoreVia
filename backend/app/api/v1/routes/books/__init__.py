from fastapi import APIRouter

from app.api.v1.routes.books.characters import router as characters_router
from app.api.v1.routes.books.core import (
    get_book_character_card_public,
    get_book_cover_public,
    router as core_router,
)
from app.api.v1.routes.books.events import router as events_router
from app.api.v1.routes.books.exports import router as exports_router
from app.api.v1.routes.books.imports import router as imports_router
from app.api.v1.routes.books.notes import router as notes_router
from app.api.v1.routes.books.publish import router as publish_router
from app.api.v1.routes.books.series import router as series_router

router = APIRouter()

router.include_router(core_router)
router.include_router(imports_router)
router.include_router(exports_router)
router.include_router(characters_router)
router.include_router(series_router)
router.include_router(notes_router)
router.include_router(publish_router)
router.include_router(events_router)

# ══════════════════════════════════════════════════════════════════════════════
# Re-exports for unit test monkeypatch compatibility.
# Tests use  monkeypatch.setattr(books, "name", ...)  so each name below
# must be importable as an attribute of this package.
# ══════════════════════════════════════════════════════════════════════════════

# ── Route endpoint functions ─────────────────────────────────────────────────
from app.api.v1.routes.books.characters import (  # noqa: E402, F401
    accept_relationship_candidate,
    apply_book_character_reprocess,
    attach_relationship_candidate_a,
    attach_relationship_candidate_b,
    create_book_character,
    create_book_relationship,
    delete_book_character,
    delete_book_relationship,
    demote_book_character,
    get_book_characters,
    merge_book_characters,
    partition_book_character,
    preview_book_character_reprocess,
    reject_relationship_candidate,
    resolve_relationship_candidate,
    share_book_character,
    update_book_character,
    update_book_relationship,
)
from app.api.v1.routes.books.core import (  # noqa: E402, F401
    _clean_optional_text,
    _clean_text,
    _read_upload_bounded,
    _validate_cover_magic,
    archive_book,
    delete_book,
    get_book,
    get_book_chapter_reports,
    get_book_chapter_versions,
    get_book_overview,
    get_emotional_arc,
    get_prewriting_check,
    get_story_health,
    get_user_stats,
    get_writer_workspace,
    hide_book,
    list_books,
    list_saved_notes,
    permanently_delete_book,
    update_book_mode,
    update_writer_workspace,
)
from app.api.v1.routes.books.events import (  # noqa: E402, F401
    _normalize_book_character_event,
    _normalize_book_major_event,
    get_book_events,
    get_reader_safe_book_events,
)
from app.api.v1.routes.books.exports import (  # noqa: E402, F401
    export_character_bible,
    export_character_card,
    export_manuscript,
    export_novel,
    list_character_bible_vault_notes,
    preview_character_bible_vault,
    save_character_bible_vault_note,
    save_novel_preface,
    save_novel_settings,
)
from app.api.v1.routes.books.imports import (  # noqa: E402, F401
    import_manuscript_content,
    manuscript_readability,
    upload_book_endpoint,
)
from app.api.v1.routes.books.notes import (  # noqa: E402, F401
    delete_book_vault_note,
    export_book_vault_notes,
    get_book_notes,
    get_book_vault_graph,
    get_book_vault_note_relations,
    import_book_vault_notes,
    list_book_vault_notes,
    remove_book_note,
    save_book_vault_note,
    upsert_book_note,
)
from app.api.v1.routes.books.series import (  # noqa: E402, F401
    add_book_to_series,
    create_series,
    get_series_bible,
    list_series,
    set_series_book_status,
    update_book_series,
)

# ── Test-support attributes (objects accessed on the module for patching) ────
from app.core import storage  # noqa: E402, F401
from app.workers.tasks.analysis_tasks import analyse_chapter_task  # noqa: E402, F401
from app.workers.tasks.extraction_tasks import process_book_task  # noqa: E402, F401

# NOTE: _process_chapter is used as a monkeypatch target in tests, but defined
# in app.workers.consumers.extraction_consumer. Import it for the tests.
from app.workers.consumers.extraction_consumer import _process_chapter  # noqa: E402, F401

# ── Utility functions needed by tests ────────────────────────────────────────
from app.api.deps.subscription import check_upload_limit  # noqa: E402, F401
from app.core.redis import (  # noqa: E402, F401
    get_book_cache_version,
    get_book_overview_cache,
    get_writer_workspace_cache,
    mark_book_cache_dirty,
    set_book_overview_cache,
    set_writer_workspace_cache,
)
from app.core.security import create_asset_token, decode_token  # noqa: E402, F401
from app.services.pipeline_state_service import (  # noqa: E402, F401
    build_writer_workspace_update,
    repair_stale_completed_processing_state,
)
from app.services.editor_project_service import repair_stale_editor_processing_state  # noqa: E402, F401
from app.utils.advisor_utils import invalidate_advisor_caches_for_book  # noqa: E402, F401
from app.utils.billing_utils import require_author_access  # noqa: E402, F401
from app.utils.billing_utils import calculate_upload_usage_summary  # noqa: E402, F401
from app.utils.book_utils import (  # noqa: E402, F401
    _append_recent_revision_edit,
    book_out,
    build_book_out_list,
    build_character_card_payload,
    build_emotional_arc_payload,
    build_vault_graph,
    build_prewriting_check,
    build_series_bible_payload,
    build_series_out_list,
    build_single_series_out,
    build_story_health_payload,
    build_writer_workspace_payload,
    build_writer_workspace_payload as build_writer_workspace_response,
    clean_manuscript_html,
    collaboration_can_comment,
    collaboration_has_resource,
    compute_words_read_for_books,
    delete_book_note,
    delete_vault_note,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    export_vault_notes_zip,
    extract_novel_scene_candidates,
    get_book_with_collaboration_access,
    get_owned_book,
    get_owned_series,
    import_vault_notes_zip,
    list_book_notes,
    list_chapter_consistency_reports,
    list_chapter_versions,
    list_novel_scenes,
    list_vault_note_relations,
    list_vault_notes,
    list_vault_bible_notes,
    list_user_notes,
    load_vault_note_overrides,
    next_chapter_number,
    normalize_book_work_type,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    replace_chapter_novel_scenes,
    resolve_owned_series_ids,
    resolve_upload_format_and_work_type,
    save_book_note,
    save_vault_note,
    strip_scene_metadata_from_manuscript_text,
    sync_chapter_content_from_novel_scenes,
)
from app.utils.reader_utils import (  # noqa: E402, F401
    build_chapter_list_payload,
    build_reading_progress_payload,
    build_summary_collection_payload,
)
from app.utils.tag_utils import get_custom_tags_for_entity, list_custom_tags_for_entity_ids  # noqa: E402, F401
from app.utils.character_utils import (  # noqa: E402, F401
    append_unique_summary,
    apply_manual_character_description,
    build_manual_character,
    clean_string_list,
    dedupe_preserve_order,
    demote_character_to_review_candidate,
    is_displayable_character,
    mark_character_candidates_merged,
    merge_characters,
    partition_character,
    refresh_character_duplicate_suggestions,
    relationship_summary_for_character,
    serialize_book_character,
)
from app.utils.user_utils import build_writing_dashboard_stats  # noqa: E402, F401

# Placeholders for monkeypatch.setattr in tests
build_repair_plan = None
apply_repair_plan = None
from app.utils.llm_usage_utils import (  # noqa: E402, F401
    LlmUsageSummary,
    summarize_llm_usage_for_user,
)
from app.utils.notification_utils import build_upload_processing_notification  # noqa: E402, F401
from app.utils.queue_utils import queue_for_user  # noqa: E402, F401
from app.utils.user_utils import add_daily_word_progress  # noqa: E402, F401
from app.utils.export_utils import manuscript_docx  # noqa: E402, F401
from app.utils.export_utils import (  # noqa: E402, F401
    build_character_bible_vault_context,
    character_bible_docx,
    character_bible_markdown,
    character_bible_vault_folder,
    character_bible_vault_preview,
    character_bible_pdf,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    manuscript_epub_compiled,
    manuscript_vault_zip,
    manuscript_pdf_compiled,
    novel_docx,
    novel_epub_compiled,
    novel_pdf_compiled,
)
from app.engine.character.consolidator import consolidate_characters  # noqa: E402, F401
from dataclasses import asdict  # noqa: E402, F401

# ── Schema classes ───────────────────────────────────────────────────────────
from app.schemas.books import BookOut, WriterWorkspaceOut  # noqa: E402, F401

__all__ = [
    "router",
    "get_book_cover_public",
    "get_book_character_card_public",
]


import importlib  # noqa: E402
import sys  # noqa: E402
from types import ModuleType  # noqa: E402

_PATCH_TARGET_MODULES = tuple(
    importlib.import_module(module_name)
    for module_name in (
        "app.api.v1.routes.books.characters",
        "app.api.v1.routes.books.core",
        "app.api.v1.routes.books.events",
        "app.api.v1.routes.books.exports",
        "app.api.v1.routes.books.imports",
        "app.api.v1.routes.books.notes",
        "app.api.v1.routes.books.publish",
        "app.api.v1.routes.books.series",
    )
)


class _PatchPropagatingModule(ModuleType):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for target_module in _PATCH_TARGET_MODULES:
            if hasattr(target_module, name):
                setattr(target_module, name, value)


sys.modules[__name__].__class__ = _PatchPropagatingModule
