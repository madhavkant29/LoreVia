"""Route dependencies for additive latency-optimization contracts."""

from fastapi import HTTPException

from app.core.config import settings


def _require_enabled(enabled: bool) -> None:
    if not enabled:
        raise HTTPException(404, "Not found")


def require_cursor_page_apis_enabled() -> None:
    _require_enabled(settings.CURSOR_PAGE_APIS_ENABLED)


def require_indexed_search_enabled() -> None:
    _require_enabled(settings.INDEXED_SEARCH_ENABLED)


def require_reader_events_v2_enabled() -> None:
    _require_enabled(settings.READER_EVENTS_V2_ENABLED)
