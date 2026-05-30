"""
Sparse fieldset and include controls for heavy API endpoints.

Supports two complementary patterns:

    ?fields=id,title,status          pick specific top-level keys from a dict response
    ?include=book,progress,chapters  pick which sub-objects to include (skip heavy ones)

Only *reduces* the default response — never adds.  When the query param is
absent the response is unchanged (backward compatible).
"""

from __future__ import annotations

from typing import Any


def parse_csv_param(value: str | None) -> set[str] | None:
    if value is None:
        return None
    value = str(value) if not isinstance(value, str) else value
    if not value.strip():
        return None
    return {item.strip() for item in value.split(",") if item.strip()}


def apply_sparse_fields(data: dict[str, Any], fields_param: str | None) -> dict[str, Any]:
    fields = parse_csv_param(fields_param)
    if fields is None:
        return data
    return {k: v for k, v in data.items() if k in fields}


def apply_sparse_includes(data: dict[str, Any], include_param: str | None) -> dict[str, Any]:
    includes = parse_csv_param(include_param)
    if includes is None:
        return data
    return {k: v for k, v in data.items() if k in includes}


def fields_requested(fields_param: str | None, *names: str) -> bool:
    """Check if any of the named fields were explicitly requested via ?fields=."""
    requested = parse_csv_param(fields_param)
    if requested is None:
        return True
    return bool(requested.intersection(names))


def include_requested(include_param: str | None, *names: str) -> bool:
    """Check if any of the named sections were explicitly requested via ?include=."""
    requested = parse_csv_param(include_param)
    if requested is None:
        return True
    return bool(requested.intersection(names))


def exclude_character_fields(
    characters: list[dict[str, Any]],
    include_param: str | None,
) -> list[dict[str, Any]]:
    """Drop heavy sub-keys from character dicts when not requested by ?include=.

    Recognised include values:
      - arc_tracker
      - analysis_metadata
      - growth_events
      - tags (note: kept by default when include_param is None)
    """
    if include_param is None or not include_param.strip():
        return characters

    includes = parse_csv_param(include_param)
    if includes is None:
        return characters

    exclude_keys: set[str] = set()
    if "arc_tracker" not in includes:
        exclude_keys.add("arc_tracker")
    if "analysis_metadata" not in includes:
        exclude_keys.add("analysis_metadata")
    if "growth_events" not in includes:
        exclude_keys.add("growth_events")
    if "tags" not in includes:
        exclude_keys.add("tags")

    if not exclude_keys:
        return characters

    return [
        {k: v for k, v in char.items() if k not in exclude_keys}
        for char in characters
    ]


def filter_character_fields(
    characters: list[dict[str, Any]],
    fields_param: str | None,
) -> list[dict[str, Any]]:
    """Keep only the requested top-level fields on each character dict."""
    fields = parse_csv_param(fields_param)
    if fields is None:
        return characters
    return [
        {k: v for k, v in char.items() if k in fields}
        for char in characters
    ]
