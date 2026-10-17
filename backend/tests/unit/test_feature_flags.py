import pytest
from fastapi import HTTPException

from app.api.deps.feature_flags import (
    require_cursor_page_apis_enabled,
    require_indexed_search_enabled,
    require_reader_events_v2_enabled,
)
from app.core.config import settings


@pytest.mark.parametrize(
    ("setting_name", "dependency"),
    [
        ("CURSOR_PAGE_APIS_ENABLED", require_cursor_page_apis_enabled),
        ("INDEXED_SEARCH_ENABLED", require_indexed_search_enabled),
        ("READER_EVENTS_V2_ENABLED", require_reader_events_v2_enabled),
    ],
)
def test_additive_endpoint_flags_hide_disabled_contracts(monkeypatch, setting_name, dependency):
    monkeypatch.setattr(settings, setting_name, False)

    with pytest.raises(HTTPException) as exc_info:
        dependency()

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize(
    ("setting_name", "dependency"),
    [
        ("CURSOR_PAGE_APIS_ENABLED", require_cursor_page_apis_enabled),
        ("INDEXED_SEARCH_ENABLED", require_indexed_search_enabled),
        ("READER_EVENTS_V2_ENABLED", require_reader_events_v2_enabled),
    ],
)
def test_additive_endpoint_flags_allow_enabled_contracts(monkeypatch, setting_name, dependency):
    monkeypatch.setattr(settings, setting_name, True)

    assert dependency() is None
