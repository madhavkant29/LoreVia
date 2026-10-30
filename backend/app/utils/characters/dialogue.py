"""Source-level checks for explicit character speech attribution."""

from __future__ import annotations

import re

SPEECH_VERBS = (
    "answered",
    "asked",
    "called",
    "muttered",
    "replied",
    "said",
    "shouted",
    "whispered",
)
SPEECH_VERB_PATTERN = "(?:" + "|".join(SPEECH_VERBS) + ")"
NAME_FOLLOWS_SPEECH = re.compile(
    rf"[\"\u201d\u2019']\s*,?\s*{SPEECH_VERB_PATTERN}\s+$",
    flags=re.IGNORECASE,
)
SPEECH_FOLLOWS_NAME = re.compile(
    rf"^\s*,?\s*{SPEECH_VERB_PATTERN}\b\s*[,\u003a\u2013\u2014-]?\s*[\"\u201c\u2018']",
    flags=re.IGNORECASE,
)
QUOTED_SPAN = re.compile(r'"[^"]*"|“[^”]*”|‘[^’]*’', flags=re.DOTALL)
COMMUNICATION_FOLLOWS_NAME = re.compile(
    r"^\s+(?:answered|asked|called|replied|spoke|texted|told|warned|wrote)\b",
    flags=re.IGNORECASE,
)
HUMAN_SELF_ACTION = re.compile(
    r"^\s+(?:raised|lowered|rubbed|clutched|gripped|washed|covered|"
    r"lifted|hurt|bandaged|closed|opened|wiped)\s+"
    r"(?:his|her|their)\s+"
    r"(?:hand|hands|arm|arms|face|eyes|head|mouth|coat|jacket|bag)\b",
    flags=re.IGNORECASE,
)


def _unquoted_name_mentions(source_text: str, name: str) -> list[re.Match[str]]:
    pattern = re.compile(r"(?<!\w)" + re.escape(name.strip()) + r"(?!\w)", re.IGNORECASE)
    quoted_ranges = [(span.start(), span.end()) for span in QUOTED_SPAN.finditer(source_text)]
    return [
        match
        for match in pattern.finditer(source_text)
        if not any(start < match.start() < end for start, end in quoted_ranges)
    ]


def has_explicit_speech_attribution(source_text: str, name: str) -> bool:
    """Require a source mention beside a speech verb, not just a nearby action."""
    if not source_text or not name or not name.strip():
        return False
    for match in _unquoted_name_mentions(source_text, name):
        before = source_text[max(0, match.start() - 100) : match.start()]
        after = source_text[match.end() : match.end() + 60]
        if SPEECH_FOLLOWS_NAME.match(after) or NAME_FOLLOWS_SPEECH.search(before):
            return True
    return False


def has_direct_communication_attribution(source_text: str, name: str) -> bool:
    """Find a named person's direct communication action outside quoted material."""
    if not source_text or not name or not name.strip():
        return False
    return any(
        COMMUNICATION_FOLLOWS_NAME.match(source_text[match.end() : match.end() + 80])
        for match in _unquoted_name_mentions(source_text, name)
    )


def has_named_human_self_action(source_text: str, name: str) -> bool:
    """Find a source-exact named action with an explicit human self-reference."""
    if not source_text or not name or not name.strip():
        return False
    return any(
        follows_human_self_action(source_text[match.end() : match.end() + 80])
        for match in _unquoted_name_mentions(source_text, name)
    )


def follows_human_self_action(text_after_name: str) -> bool:
    """Recognize a bounded human possessive action directly after a name."""
    return bool(HUMAN_SELF_ACTION.match(text_after_name))
