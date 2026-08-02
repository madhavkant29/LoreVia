from __future__ import annotations

INTENT_KEYWORDS: dict[str, list[str]] = {
    "plothole": [
        "plot hole",
        "plot-hole",
        "plothole",
        "contradiction",
        "contradicts",
        "contradicting",
        "inconsistency",
        "inconsistent",
        "doesn't make sense",
        "does not make sense",
        "doesn't add up",
        "does not add up",
        "broken logic",
        "logic issue",
    ],
    "direction": [
        "what should",
        "what next",
        "what now",
        "where should",
        "where do i",
        "where to go",
        "how should",
        "how do i continue",
        "should i",
        "which direction",
        "next step",
        "next chapter",
        "next scene",
        "what happens next",
        "what do i do",
        "stuck",
        "writer's block",
        "writers block",
        "don't know where",
        "dont know where",
    ],
    "opportunity": [
        "opportunity",
        "opportunities",
        "potential",
        "untapped",
        "unexplored",
        "could i",
        "what if i",
        "expand",
        "develop further",
        "seed",
        "plant",
        "foreshadow",
        "unused",
        "underused",
        "under-utilised",
    ],
    "consistency": [
        "consistency",
        "consistent",
        "canon",
        "lore",
        "rule",
        "rules",
        "worldbuild",
        "world-build",
        "world build",
        "timeline",
        "continuity",
        "does this fit",
        "does it make sense in",
        "contradiction",
        "contradicts",
    ],
}


def classify_intent_fast(user_message: str | None) -> str:
    if not user_message or not user_message.strip():
        return "general"
    lower = user_message.strip().lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return intent
    return "general"
