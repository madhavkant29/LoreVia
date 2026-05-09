from __future__ import annotations


def detect_integration_opportunities(elements: list[dict]) -> list[dict]:
    opportunities: list[dict] = []
    for element in elements:
        usage_count = int(element.get("usage_count") or 0)
        if usage_count > 1:
            continue
        name = str(element.get("name") or "").strip()
        if not name:
            continue
        opportunities.append(
            {
                "id": f"integration-{name.lower().replace(' ', '-')}",
                "element_name": name,
                "element_type": str(element.get("element_type") or "culture"),
                "description": f"{name} appears lightly in the extracted manuscript and may need stronger story integration.",
                "suggestions": [
                    f"Anchor {name} to a character decision or conflict beat.",
                    f"Reference {name} earlier so later appearances feel earned.",
                ],
                "target_chapter": element.get("chapter_number"),
                "priority": 5,
            }
        )
    return opportunities
