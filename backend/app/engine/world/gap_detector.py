from __future__ import annotations


def detect_gap_categories(elements: list[dict]) -> dict[str, list[dict]]:
    categories: dict[str, list[dict]] = {}
    type_counts: dict[str, int] = {}
    for element in elements:
        element_type = str(element.get("element_type") or "culture")
        type_counts[element_type] = type_counts.get(element_type, 0) + 1

    baseline_categories = {
        "geography",
        "politics",
        "economics",
        "magic_system",
        "culture",
        "technology",
        "religion",
        "ecology",
    }
    for category in baseline_categories:
        if type_counts.get(category, 0) == 0:
            categories.setdefault(category, []).append(
                {
                    "id": f"missing-{category}",
                    "title": f"Missing {category.replace('_', ' ')} coverage",
                    "description": f"No strong {category.replace('_', ' ')} elements have been extracted yet.",
                    "priority": 6,
                }
            )
    return categories


def detect_consistency_flags(elements: list[dict]) -> list[dict]:
    seen: dict[str, str] = {}
    flags: list[dict] = []
    for element in elements:
        name = " ".join(str(element.get("name") or "").split()).strip()
        description = " ".join(str(element.get("description") or "").split()).strip()
        if not name:
            continue
        key = name.lower()
        existing = seen.get(key)
        if existing and existing != description:
            flags.append(
                {
                    "id": f"conflict-{key}",
                    "type": "definition_conflict",
                    "title": f"Conflicting definition for {name}",
                    "description": "Multiple extracted descriptions disagree about this world element.",
                }
            )
        else:
            seen[key] = description
    return flags
