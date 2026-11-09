from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from app.utils.intelligence_utils import (
    compute_voice_metrics,
    score_voice_match,
)
from app.utils.voice_profile_samples import explicit_dialogue_by_character

MAX_BETA_READER_BATCH_CHARS = 24_000
MAX_BETA_READER_BATCH_CHAPTERS = 4
MAX_OVERUSED_TERMS = 30
MAX_TERM_EVIDENCE = 3

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?", re.MULTILINE)
_DIALOGUE_RE = re.compile(r'["“][^"”]*["”]', re.DOTALL)
_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "almost",
    "also",
    "although",
    "always",
    "among",
    "another",
    "around",
    "because",
    "before",
    "being",
    "below",
    "between",
    "both",
    "could",
    "didn",
    "does",
    "doesn",
    "doing",
    "don",
    "down",
    "during",
    "each",
    "even",
    "every",
    "from",
    "further",
    "hadn",
    "hasn",
    "have",
    "having",
    "here",
    "hers",
    "herself",
    "himself",
    "into",
    "itself",
    "just",
    "might",
    "more",
    "most",
    "mustn",
    "myself",
    "never",
    "other",
    "ought",
    "ours",
    "ourselves",
    "over",
    "same",
    "shan",
    "should",
    "shouldn",
    "some",
    "such",
    "than",
    "that",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "under",
    "until",
    "very",
    "wasn",
    "weren",
    "what",
    "when",
    "where",
    "which",
    "while",
    "whom",
    "would",
    "wouldn",
    "your",
    "yours",
    "yourself",
    "yourselves",
}

_VOICE_METRICS = (
    ("avg_sentence_length", "sentence length"),
    ("formality_score_x1000", "formality"),
    ("contraction_rate_x1000", "contraction use"),
    ("question_rate_x1000", "question frequency"),
    ("exclamation_rate_x1000", "exclamation use"),
    ("ellipsis_rate_x1000", "ellipsis use"),
    ("dash_rate_x1000", "dash use"),
    ("lexical_complexity_x1000", "vocabulary complexity"),
    ("emotional_intensity_x1000", "emotional register"),
)


def _clean_text(value: object, *, max_chars: int = 1000) -> str:
    return " ".join(str(value or "").split()).strip()[:max_chars]


def stable_beta_reader_id(prefix: str, *parts: object) -> str:
    raw = "|".join(_clean_text(part, max_chars=1000).casefold() for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def build_beta_reader_request_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_chapter_source_fingerprint(chapters: Iterable[Any]) -> str:
    parts = [
        f"{chapter.id}:{chapter.number}:{int(chapter.content_version or 1)}"
        for chapter in sorted(chapters, key=lambda item: item.number)
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_passage_source_fingerprint(text: str) -> str:
    normalized = " ".join((text or "").replace("’", "'").split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalized_tokens(text: str) -> list[tuple[str, int, int]]:
    normalized = (text or "").replace("’", "'")
    return [
        (match.group(0).casefold(), match.start(), match.end())
        for match in _WORD_RE.finditer(normalized)
    ]


def _dialogue_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in _DIALOGUE_RE.finditer(text or "")]


def _inside_spans(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _entity_terms(names: Iterable[str]) -> set[str]:
    excluded: set[str] = set()
    for name in names:
        normalized = " ".join(token for token, _, _ in _normalized_tokens(name))
        if not normalized:
            continue
        excluded.add(normalized)
        excluded.update(token for token in normalized.split() if len(token) >= 4)
    return excluded


def _has_burst(positions_by_chapter: dict[int, list[int]]) -> bool:
    for positions in positions_by_chapter.values():
        for index in range(len(positions) - 2):
            if positions[index + 2] - positions[index] <= 120:
                return True
    return False


def _term_excerpt(text: str, start: int, end: int, max_chars: int = 240) -> str:
    left = max(0, start - max_chars // 2)
    right = min(len(text), max(end + max_chars // 2, left + max_chars))
    excerpt = " ".join(text[left:right].split()).strip()
    if left > 0:
        excerpt = f"…{excerpt}"
    if right < len(text):
        excerpt = f"{excerpt}…"
    return excerpt[:max_chars]


def analyze_overused_language(
    chapter_texts: dict[int, str],
    *,
    excluded_names: Iterable[str] = (),
) -> list[dict[str, Any]]:
    excluded = _entity_terms(excluded_names)
    total_words = sum(len(_normalized_tokens(text)) for text in chapter_texts.values())
    if total_words <= 0:
        return []

    records: dict[tuple[str, str], dict[str, Any]] = {}
    for chapter_number, text in sorted(chapter_texts.items()):
        dialogue_spans = _dialogue_spans(text)
        chapter_token_index = 0
        for sentence_match in _SENTENCE_RE.finditer(text):
            sentence_start = sentence_match.start()
            sentence_tokens = _normalized_tokens(sentence_match.group(0))
            token_rows: list[tuple[str, int, int, int, bool]] = []
            for token, relative_start, relative_end in sentence_tokens:
                absolute_start = sentence_start + relative_start
                absolute_end = sentence_start + relative_end
                token_rows.append(
                    (
                        token,
                        absolute_start,
                        absolute_end,
                        chapter_token_index,
                        _inside_spans(absolute_start, dialogue_spans),
                    )
                )
                chapter_token_index += 1

            for token, start, end, token_index, is_dialogue in token_rows:
                if len(token.replace("'", "")) < 4 or token in _STOPWORDS or token in excluded:
                    continue
                key = ("word", token)
                row = records.setdefault(
                    key,
                    {
                        "kind": "word",
                        "term": token,
                        "count": 0,
                        "narration_count": 0,
                        "dialogue_count": 0,
                        "chapter_counts": Counter(),
                        "positions": defaultdict(list),
                        "occurrences": [],
                    },
                )
                row["count"] += 1
                row["dialogue_count" if is_dialogue else "narration_count"] += 1
                row["chapter_counts"][chapter_number] += 1
                row["positions"][chapter_number].append(token_index)
                if len(row["occurrences"]) < MAX_TERM_EVIDENCE:
                    row["occurrences"].append((chapter_number, start, end))

            for size in range(2, 5):
                for index in range(0, len(token_rows) - size + 1):
                    window = token_rows[index : index + size]
                    phrase_tokens = [item[0] for item in window]
                    phrase = " ".join(phrase_tokens)
                    if phrase in excluded or all(token in _STOPWORDS for token in phrase_tokens):
                        continue
                    if any(token in excluded for token in phrase_tokens):
                        continue
                    start, end = window[0][1], window[-1][2]
                    is_dialogue = all(item[4] for item in window)
                    key = ("phrase", phrase)
                    row = records.setdefault(
                        key,
                        {
                            "kind": "phrase",
                            "term": phrase,
                            "count": 0,
                            "narration_count": 0,
                            "dialogue_count": 0,
                            "chapter_counts": Counter(),
                            "positions": defaultdict(list),
                            "occurrences": [],
                        },
                    )
                    row["count"] += 1
                    row["dialogue_count" if is_dialogue else "narration_count"] += 1
                    row["chapter_counts"][chapter_number] += 1
                    row["positions"][chapter_number].append(window[0][3])
                    if len(row["occurrences"]) < MAX_TERM_EVIDENCE:
                        row["occurrences"].append((chapter_number, start, end))

    findings: list[dict[str, Any]] = []
    for row in records.values():
        rate = (int(row["count"]) / total_words) * 1000
        burst = _has_burst(row["positions"])
        threshold_met = (
            int(row["count"]) >= 5 and rate >= 2.5
            if row["kind"] == "word"
            else int(row["count"]) >= 3 and rate >= 0.5
        )
        if not threshold_met and not burst:
            continue
        evidence = [
            {
                "chapter_number": chapter_number,
                "excerpt": _term_excerpt(chapter_texts[chapter_number], start, end),
            }
            for chapter_number, start, end in row["occurrences"]
        ]
        findings.append(
            {
                "id": stable_beta_reader_id("term", row["kind"], row["term"]),
                "term": row["term"],
                "kind": row["kind"],
                "count": int(row["count"]),
                "rate_per_1000": round(rate, 2),
                "narration_count": int(row["narration_count"]),
                "dialogue_count": int(row["dialogue_count"]),
                "burst_detected": burst,
                "chapter_counts": {
                    str(key): int(value) for key, value in sorted(row["chapter_counts"].items())
                },
                "evidence": evidence,
            }
        )

    return sorted(
        findings,
        key=lambda item: (
            not item["burst_detected"],
            -float(item["rate_per_1000"]),
            -int(item["count"]),
            item["term"],
        ),
    )[:MAX_OVERUSED_TERMS]


def _profile_value(profile: Any, key: str, default: Any = None) -> Any:
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


def _profile_payload(profile: Any) -> dict[str, Any]:
    return {
        "sample_dialogue_count": int(_profile_value(profile, "sample_dialogue_count", 0) or 0),
        "sample_word_count": int(_profile_value(profile, "sample_word_count", 0) or 0),
        **{key: int(_profile_value(profile, key, 0) or 0) for key, _ in _VOICE_METRICS},
        "signature_phrases": [
            _clean_text(phrase, max_chars=120).casefold()
            for phrase in (_profile_value(profile, "signature_phrases", []) or [])
            if _clean_text(phrase, max_chars=120)
        ],
    }


def build_scoped_voice_profiles(
    chapter_texts: dict[int, str],
    characters: list[Any],
    stored_profiles: list[Any],
    *,
    include_stored_signatures: bool,
) -> list[dict[str, Any]]:
    """Build voice metrics only from dialogue attributed inside the requested scope."""
    character_rows = [
        {
            "id": character.id,
            "name": character.name,
            "aliases": list(getattr(character, "aliases", None) or []),
        }
        for character in characters
    ]
    dialogue_by_name: dict[str, list[str]] = {str(character.name): [] for character in characters}
    for chapter_number, text in sorted(chapter_texts.items()):
        attributed = explicit_dialogue_by_character(
            text, character_rows, chapter_number=chapter_number
        )
        for name, samples in attributed.items():
            dialogue_by_name.setdefault(name, []).extend(samples)

    stored_by_character_id = {
        str(_profile_value(profile, "character_id")): profile for profile in stored_profiles
    }
    scoped_profiles: list[dict[str, Any]] = []
    for character in characters:
        metrics = compute_voice_metrics(dialogue_by_name.get(str(character.name), []))
        metrics["character_id"] = character.id
        if include_stored_signatures:
            stored = stored_by_character_id.get(str(character.id))
            stored_phrases = (
                _profile_value(stored, "signature_phrases", []) if stored is not None else []
            ) or []
            metrics["signature_phrases"] = list(
                dict.fromkeys(
                    [
                        *(
                            _clean_text(phrase, max_chars=120).casefold()
                            for phrase in metrics.get("signature_phrases") or []
                        ),
                        *(
                            _clean_text(phrase, max_chars=120).casefold()
                            for phrase in stored_phrases
                        ),
                    ]
                )
            )[:6]
        scoped_profiles.append(metrics)
    return scoped_profiles


def _voice_confidence(left: dict[str, Any], right: dict[str, Any] | None = None) -> str:
    values = [left, right or left]
    if all(
        row["sample_dialogue_count"] >= 15 and row["sample_word_count"] >= 300 for row in values
    ):
        return "high"
    if all(row["sample_dialogue_count"] >= 5 and row["sample_word_count"] >= 100 for row in values):
        return "medium"
    if all(row["sample_dialogue_count"] >= 3 and row["sample_word_count"] >= 50 for row in values):
        return "low"
    return "insufficient"


def _voice_pair_similarity(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[int, list[str], list[str]]:
    left_score, _ = score_voice_match(left, right)
    right_score, _ = score_voice_match(right, left)
    left_phrases = set(left.get("signature_phrases") or [])
    right_phrases = set(right.get("signature_phrases") or [])
    shared_phrases = sorted(left_phrases & right_phrases)
    union = left_phrases | right_phrases
    phrase_similarity = (len(shared_phrases) / len(union)) * 100 if union else 0.0
    similarity = int(round((0.8 * ((left_score + right_score) / 2)) + (0.2 * phrase_similarity)))
    similarities: list[tuple[float, str]] = []
    for key, label in _VOICE_METRICS:
        left_value = float(left.get(key) or 0)
        right_value = float(right.get(key) or 0)
        scale = max(4.0, abs(left_value), abs(right_value))
        similarities.append((abs(left_value - right_value) / scale, label))
    shared_signals = [label for _, label in sorted(similarities)[:4]]
    return max(0, min(100, similarity)), shared_signals, shared_phrases[:6]


def analyze_character_voice_distinctness(
    characters: list[Any],
    profiles: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    character_by_id = {str(character.id): character for character in characters}
    profile_rows = [
        (profile, _profile_payload(profile))
        for profile in profiles
        if str(_profile_value(profile, "character_id")) in character_by_id
    ]
    warnings: list[str] = []
    output: list[dict[str, Any]] = []

    for profile, metrics in profile_rows:
        profile_character_id = _profile_value(profile, "character_id")
        character = character_by_id[str(profile_character_id)]
        confidence = _voice_confidence(metrics)
        row = {
            "id": stable_beta_reader_id("voice", profile_character_id),
            "character_id": str(profile_character_id),
            "character_name": character.name,
            "distinctness_score": None,
            "confidence": confidence,
            "sample_dialogue_count": metrics["sample_dialogue_count"],
            "sample_word_count": metrics["sample_word_count"],
            "closest_character_id": None,
            "closest_character_name": None,
            "similarity_score": None,
            "signals": {key: metrics[key] for key, _ in _VOICE_METRICS},
            "shared_signals": [],
            "shared_phrases": [],
        }
        if confidence == "insufficient":
            warnings.append(
                f"{character.name} needs at least 3 attributed dialogue samples and 50 words for voice comparison."
            )
            output.append(row)
            continue

        closest: tuple[int, Any, dict[str, Any], list[str], list[str]] | None = None
        for other_profile, other_metrics in profile_rows:
            other_character_id = _profile_value(other_profile, "character_id")
            if (
                other_character_id == profile_character_id
                or _voice_confidence(other_metrics) == "insufficient"
            ):
                continue
            similarity, signals, phrases = _voice_pair_similarity(metrics, other_metrics)
            if closest is None or similarity > closest[0]:
                closest = (similarity, other_profile, other_metrics, signals, phrases)
        if closest is None:
            warnings.append(
                f"{character.name} has no second sufficiently sampled character to compare against."
            )
            output.append(row)
            continue
        similarity, other_profile, other_metrics, signals, phrases = closest
        other_character_id = _profile_value(other_profile, "character_id")
        other_character = character_by_id[str(other_character_id)]
        row.update(
            {
                "distinctness_score": 100 - similarity,
                "confidence": _voice_confidence(metrics, other_metrics),
                "closest_character_id": str(other_character_id),
                "closest_character_name": other_character.name,
                "similarity_score": similarity,
                "shared_signals": signals,
                "shared_phrases": phrases,
            }
        )
        output.append(row)
    profiled_character_ids = {
        str(_profile_value(profile, "character_id")) for profile, _ in profile_rows
    }
    for character in characters:
        if str(character.id) in profiled_character_ids:
            continue
        warnings.append(f"{character.name} does not have an extracted dialogue voice profile yet.")
        output.append(
            {
                "id": stable_beta_reader_id("voice", character.id),
                "character_id": str(character.id),
                "character_name": character.name,
                "distinctness_score": None,
                "confidence": "insufficient",
                "sample_dialogue_count": 0,
                "sample_word_count": 0,
                "closest_character_id": None,
                "closest_character_name": None,
                "similarity_score": None,
                "signals": {},
                "shared_signals": [],
                "shared_phrases": [],
            }
        )
    if not profile_rows:
        warnings.append("No extracted character voice profiles are available yet.")
    return output[:20], warnings


def split_beta_reader_batches(chapter_texts: dict[int, str]) -> list[list[tuple[int, str]]]:
    units: list[tuple[int, str]] = []
    for chapter_number, text in sorted(chapter_texts.items()):
        remaining = text.strip()
        while len(remaining) > MAX_BETA_READER_BATCH_CHARS:
            split_at = remaining.rfind("\n\n", 0, MAX_BETA_READER_BATCH_CHARS)
            if split_at < MAX_BETA_READER_BATCH_CHARS // 2:
                split_at = remaining.rfind(" ", 0, MAX_BETA_READER_BATCH_CHARS)
            split_at = split_at if split_at > 0 else MAX_BETA_READER_BATCH_CHARS
            units.append((chapter_number, remaining[:split_at].strip()))
            remaining = remaining[split_at:].strip()
        if remaining:
            units.append((chapter_number, remaining))

    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    current_chars = 0
    current_chapters: set[int] = set()
    for unit in units:
        next_chapters = current_chapters | {unit[0]}
        if current and (
            current_chars + len(unit[1]) > MAX_BETA_READER_BATCH_CHARS
            or len(next_chapters) > MAX_BETA_READER_BATCH_CHAPTERS
        ):
            batches.append(current)
            current = []
            current_chars = 0
            current_chapters = set()
        current.append(unit)
        current_chars += len(unit[1])
        current_chapters.add(unit[0])
    if current:
        batches.append(current)
    return batches


def normalize_beta_reader_synthesis(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "overall_impression": _clean_text(raw, max_chars=1200),
            "reader_vibe": "",
            "story_understanding": "",
            "strengths": [],
            "reader_questions": [],
            "prioritized_revisions": [],
            "findings": [],
        }
    if not isinstance(parsed, dict):
        parsed = {}

    def clean_list(key: str, limit: int) -> list[str]:
        return [
            cleaned
            for item in (parsed.get(key) or [])[:limit]
            if (cleaned := _clean_text(item, max_chars=600))
        ]

    findings: list[dict[str, Any]] = []
    for item in (parsed.get("findings") or [])[:20]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), max_chars=160)
        description = _clean_text(item.get("description"), max_chars=1000)
        recommendation = _clean_text(item.get("recommendation"), max_chars=800)
        if not title or not description or not recommendation:
            continue
        chapter_value = item.get("chapter_number")
        chapter_number = (
            int(chapter_value)
            if isinstance(chapter_value, (int, float)) and int(chapter_value) > 0
            else None
        )
        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        category = (
            _clean_text(item.get("category") or "reader_feedback", max_chars=64)
            .lower()
            .replace(" ", "_")
        )
        evidence_text = _clean_text(item.get("evidence"), max_chars=240)
        findings.append(
            {
                "id": stable_beta_reader_id(
                    "finding", category, chapter_number, title, evidence_text
                ),
                "category": category,
                "severity": severity,
                "title": title,
                "description": description,
                "chapter_number": chapter_number,
                "evidence": [{"chapter_number": chapter_number, "excerpt": evidence_text}]
                if evidence_text
                else [],
                "recommendation": recommendation,
                "reader_question": _clean_text(item.get("reader_question"), max_chars=500) or None,
            }
        )
    return {
        "overall_impression": _clean_text(parsed.get("overall_impression"), max_chars=1200),
        "reader_vibe": _clean_text(parsed.get("reader_vibe"), max_chars=320),
        "story_understanding": _clean_text(parsed.get("story_understanding"), max_chars=1200),
        "strengths": clean_list("strengths", 8),
        "reader_questions": clean_list("reader_questions", 8),
        "prioritized_revisions": clean_list("prioritized_revisions", 8),
        "findings": findings,
    }
