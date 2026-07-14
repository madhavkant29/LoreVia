from __future__ import annotations

import json
from typing import Any


def _short_world_value(value: object, limit: int = 220) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        text = "; ".join(_short_world_value(item, limit=limit) for item in value if item)
    elif isinstance(value, dict):
        preferred = (
            value.get("title")
            or value.get("element_name")
            or value.get("name")
            or value.get("description")
            or value.get("suggested_fix")
            or value.get("answer")
            or ""
        )
        text = (
            _short_world_value(preferred, limit=limit)
            if preferred
            else json.dumps(value, default=str)
        )
    else:
        text = str(value)
    text = " ".join(text.split()).strip()
    return (text[: limit - 3] + "...") if len(text) > limit else text


def _format_world_item(item: object) -> str:
    if not isinstance(item, dict):
        return _short_world_value(item)
    label = _short_world_value(
        item.get("title")
        or item.get("element_name")
        or item.get("name")
        or item.get("category")
        or item.get("severity")
    )
    description = _short_world_value(
        item.get("description") or item.get("body") or item.get("problem")
    )
    fix = _short_world_value(
        item.get("suggested_fix") or item.get("suggestion") or item.get("what_to_add")
    )
    parts = [part for part in (label, description, f"Fix: {fix}" if fix else "") if part]
    return " - ".join(parts)


def build_advisor_world_context(world_analysis: dict[str, Any] | None) -> str:
    """Compact world-building analysis so the advisor LLM can cite it cleanly."""
    if not world_analysis:
        return ""
    lines = [
        "--- WORLD ANALYSIS ---",
        f"Mode: {world_analysis.get('mode') or 'gap_detection'}",
    ]
    answer = _short_world_value(world_analysis.get("answer"), limit=700)
    if answer:
        lines.append(f"Summary: {answer}")
    logic_alerts = [item for item in world_analysis.get("logic_alerts") or [] if item][:4]
    if logic_alerts:
        lines.append("Logic alerts:")
        lines.extend(f"- {_format_world_item(item)}" for item in logic_alerts)
    suggestions = [item for item in world_analysis.get("suggestions") or [] if item][:5]
    if suggestions:
        lines.append("Priority suggestions:")
        lines.extend(f"- {_format_world_item(item)}" for item in suggestions)
    citations = [item for item in world_analysis.get("citations") or [] if isinstance(item, dict)][
        :5
    ]
    if citations:
        lines.append("World citations:")
        for item in citations:
            name = _short_world_value(item.get("name"))
            element_type = _short_world_value(item.get("element_type"), limit=80)
            scope = _short_world_value(item.get("source_scope"), limit=80)
            lines.append(f"- {name} [{element_type}] source={scope}".strip())
    steps = [
        _short_world_value(item) for item in world_analysis.get("simulation_steps") or [] if item
    ][:4]
    if steps:
        lines.append("World-logic steps:")
        lines.extend(f"- {step}" for step in steps)
    lines.append("----------------------")
    return "\n".join(lines)
