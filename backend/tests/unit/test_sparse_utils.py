import pytest

from app.utils.sparse_utils import (
    apply_sparse_fields,
    apply_sparse_includes,
    exclude_character_fields,
    fields_requested,
    filter_character_fields,
    include_requested,
    parse_csv_param,
)


class TestParseCsvParam:
    def test_none_returns_none(self):
        assert parse_csv_param(None) is None

    def test_empty_string_returns_none(self):
        assert parse_csv_param("") is None
        assert parse_csv_param("   ") is None

    def test_single_value(self):
        assert parse_csv_param("id") == {"id"}

    def test_multiple_values(self):
        assert parse_csv_param("id,name,status") == {"id", "name", "status"}

    def test_trims_whitespace(self):
        assert parse_csv_param(" id , name , status ") == {"id", "name", "status"}

    def test_skips_empty_segments(self):
        assert parse_csv_param("id,,name") == {"id", "name"}


class TestApplySparseFields:
    def test_no_param_returns_full_data(self):
        data = {"id": 1, "name": "test", "status": "active"}
        assert apply_sparse_fields(data, None) == data

    def test_empty_string_returns_full_data(self):
        data = {"id": 1, "name": "test"}
        assert apply_sparse_fields(data, "") == data

    def test_filters_to_requested_fields(self):
        data = {"id": 1, "name": "test", "status": "active", "extra": True}
        result = apply_sparse_fields(data, "id,name")
        assert result == {"id": 1, "name": "test"}

    def test_unknown_fields_not_included(self):
        data = {"id": 1, "name": "test"}
        result = apply_sparse_fields(data, "id,unknown")
        assert result == {"id": 1}


class TestApplySparseIncludes:
    def test_no_param_returns_full_data(self):
        data = {"book": {}, "progress": {}, "chapter_list": []}
        assert apply_sparse_includes(data, None) == data

    def test_filters_to_requested_sections(self):
        data = {"book": {}, "progress": {}, "chapter_list": [], "summary_collection": []}
        result = apply_sparse_includes(data, "book,progress")
        assert result == {"book": {}, "progress": {}}

    def test_empty_result_when_no_matches(self):
        data = {"nodes": [], "edges": []}
        result = apply_sparse_includes(data, "unknown")
        assert result == {}


class TestFieldsRequested:
    def test_none_returns_true(self):
        assert fields_requested(None, "id") is True

    def test_empty_returns_true(self):
        assert fields_requested("", "id") is True

    def test_field_present(self):
        assert fields_requested("id,name", "id") is True

    def test_field_absent(self):
        assert fields_requested("id,name", "status") is False

    def test_any_field_matches(self):
        assert fields_requested("id,name", "status", "name") is True
        assert fields_requested("id,name", "status", "other") is False


class TestIncludeRequested:
    def test_none_returns_true(self):
        assert include_requested(None, "arc_tracker") is True

    def test_section_present(self):
        assert include_requested("arc_tracker,analysis_metadata", "arc_tracker") is True

    def test_section_absent(self):
        assert include_requested("arc_tracker,analysis_metadata", "tags") is False

    def test_any_section_matches(self):
        assert include_requested("chapters,events", "relationship_markers", "events") is True
        assert include_requested("chapters,events", "relationship_markers", "thread_tracks") is False


class TestExcludeCharacterFields:
    _sample_chars = [
        {
            "id": "1",
            "name": "Alice",
            "arc_tracker": {"goal": "survive"},
            "analysis_metadata": {"evidence_count": 5},
            "growth_events": [{"event": "born"}],
            "tags": ["hero"],
        },
    ]

    def test_no_param_keeps_all(self):
        result = exclude_character_fields(self._sample_chars, None)
        assert "arc_tracker" in result[0]
        assert "analysis_metadata" in result[0]
        assert "growth_events" in result[0]
        assert "tags" in result[0]

    def test_empty_string_keeps_all(self):
        result = exclude_character_fields(self._sample_chars, "")
        assert "arc_tracker" in result[0]

    def test_excludes_arc_tracker_when_not_included(self):
        result = exclude_character_fields(self._sample_chars, "analysis_metadata,tags")
        assert "arc_tracker" not in result[0]
        assert "analysis_metadata" in result[0]
        assert "tags" in result[0]
        assert "growth_events" not in result[0]

    def test_excludes_multiple(self):
        result = exclude_character_fields(self._sample_chars, "id,name")
        assert "arc_tracker" not in result[0]
        assert "analysis_metadata" not in result[0]
        assert "growth_events" not in result[0]
        assert "tags" not in result[0]
        assert "id" in result[0]
        assert "name" in result[0]

    def test_all_included_keeps_everything(self):
        result = exclude_character_fields(self._sample_chars, "arc_tracker,analysis_metadata,growth_events,tags")
        assert "arc_tracker" in result[0]
        assert "analysis_metadata" in result[0]
        assert "growth_events" in result[0]
        assert "tags" in result[0]


class TestFilterCharacterFields:
    _sample_chars = [
        {"id": "1", "name": "Alice", "role": "mc", "arc_tracker": None, "internal": "hidden"},
        {"id": "2", "name": "Bob", "role": "sc", "arc_tracker": None, "internal": "hidden"},
    ]

    def test_no_param_returns_all(self):
        result = filter_character_fields(self._sample_chars, None)
        assert len(result) == 2
        assert "internal" in result[0]

    def test_filters_to_requested_fields(self):
        result = filter_character_fields(self._sample_chars, "id,name,role")
        assert result == [
            {"id": "1", "name": "Alice", "role": "mc"},
            {"id": "2", "name": "Bob", "role": "sc"},
        ]

    def test_unknown_fields_omitted(self):
        result = filter_character_fields(self._sample_chars, "id,unknown")
        assert result == [{"id": "1"}, {"id": "2"}]
