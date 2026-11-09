"""Coverage and evidence checks for character voice reviews."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from app.utils.intelligence_utils import compute_voice_metrics, score_voice_match


class VoiceReviewFormatError(ValueError):
    """A model response cannot be trusted as a completed voice review."""


VOICE_CURRENT_SAMPLE_MINIMUMS = {
    "dialogue": (2, 20),
    "first_person_narration": (1, 40),
}
GROUNDED_VOICE_PROFILE_FIELDS = {
    "personality_tags",
    "motivations",
    "fears",
    "goal",
    "arc_summary",
}

VOICE_SPEECH_QUOTE_PATTERN = re.compile(
    r'["“](?P<double>.+?)["”]|‘(?P<curly>.+?)’(?!\w)|(?<!\w)\'(?P<single>.+?)\'(?!\w)',
    re.DOTALL,
)


def voice_source_matches_submitted(chunk_text: str, submitted_text: str) -> bool:
    """Identify a copied or lightly edited source passage without matching generic fragments."""
    source = " ".join(chunk_text.split()).casefold()
    submitted = " ".join(submitted_text.split()).casefold()
    if source == submitted and len(source) >= 12:
        return True
    if (
        12 <= len(submitted) < 20
        and len(submitted.split()) >= 3
        and submitted in source
        and re.search(r"\b(?:said|asked|replied|whispered|shouted|muttered|answered)\b", submitted)
        and VOICE_SPEECH_QUOTE_PATTERN.search(submitted)
    ):
        return True
    if len(source) < 20 or len(submitted) < 20:
        return False
    if source in submitted or submitted in source:
        return True

    source_words = re.findall(r"\w+", source, flags=re.UNICODE)
    submitted_words = re.findall(r"\w+", submitted, flags=re.UNICODE)
    if min(len(source_words), len(submitted_words)) < 8:
        return False
    width = 3 if len(submitted_words) < 30 else 5
    source_shingles = Counter(
        tuple(source_words[index : index + width]) for index in range(len(source_words) - width + 1)
    )
    submitted_shingles = Counter(
        tuple(submitted_words[index : index + width])
        for index in range(len(submitted_words) - width + 1)
    )
    smaller = min(source_shingles.total(), submitted_shingles.total())
    shared = (source_shingles & submitted_shingles).total()
    minimum_shared = 5 if width == 3 else 8
    minimum_ratio = 0.6 if width == 3 else 0.65
    return shared >= minimum_shared and shared / smaller >= minimum_ratio


def voice_source_covers_submitted_passage(source_text: str, submitted_text: str) -> bool:
    """Detect a copied passage inside an earlier source without matching one shared quote."""
    source = " ".join(source_text.split()).casefold()
    submitted = " ".join(submitted_text.split()).casefold()
    if source == submitted and len(source) >= 12:
        return True
    source_words = re.findall(r"\w+", source_text.casefold(), flags=re.UNICODE)
    submitted_words = re.findall(r"\w+", submitted_text.casefold(), flags=re.UNICODE)
    if len(submitted_words) < 8 or len(source_words) < 8:
        return False
    width = 3 if len(submitted_words) < 30 else 5
    source_shingles = Counter(
        tuple(source_words[index : index + width]) for index in range(len(source_words) - width + 1)
    )
    submitted_shingles = Counter(
        tuple(submitted_words[index : index + width])
        for index in range(len(submitted_words) - width + 1)
    )
    shared = (source_shingles & submitted_shingles).total()
    return shared >= (5 if width == 3 else 8) and shared / submitted_shingles.total() >= 0.8


def voice_finding_key(issue: dict[str, Any], *, source_fingerprint: str = "") -> str:
    """Stable identity for the same source-backed claim across model reruns."""
    parts = (
        source_fingerprint,
        str(issue.get("character_name") or ""),
        str(issue.get("submitted_excerpt") or ""),
        str(issue.get("baseline_excerpt") or ""),
        str(issue.get("baseline_chapter_number") or ""),
    )
    normalized = "|".join(" ".join(part.casefold().split()) for part in parts)
    return hashlib.sha256(normalized.encode()).hexdigest()


def make_voice_review_cache_key(
    book_id: Any,
    text: str,
    chapter_number: int | None,
    character_id: Any,
    baseline_signature: str,
    scene_context: str | None = None,
    voice_mode: str = "dialogue",
) -> str:
    """Include every submitted character and all cited baseline evidence."""
    payload = f"voice-v2:{book_id}:{chapter_number}:{character_id}:{voice_mode}:{scene_context or ''}:{text}:{baseline_signature}"
    return hashlib.sha256(payload.encode()).hexdigest()


def voice_review_context_signature(
    *,
    story_context: str,
    characters: Sequence[dict[str, Any]],
    baseline_by_name: dict[str, Sequence[dict[str, Any]]],
) -> str:
    """Invalidate reviews when cited evidence or grounded profile context changes."""
    profile_fields = (
        "id",
        "generation_id",
        "name",
        "aliases",
        "role",
        "first_chapter",
        "arc_summary",
        "personality_tags",
        "motivations",
        "fears",
        "trait_state",
        "goal",
        "analysis_metadata",
    )
    profiles = [
        {field: character.get(field) for field in profile_fields} for character in characters
    ]
    payload = {
        "story_context": story_context,
        "profiles": profiles,
        "baseline": baseline_by_name,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def grounded_voice_profile_claims(
    character: dict[str, Any],
    baseline_samples: Sequence[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Expose profile claims only when their exact citation survives in the current baseline."""
    if limit < 1:
        return []
    metadata = character.get("analysis_metadata")
    records = metadata.get("profile_claims") if isinstance(metadata, dict) else None
    if not isinstance(records, list):
        return []
    grounded: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        field = record.get("field")
        value = record.get("value")
        quote = record.get("quote")
        chapter = record.get("chapter_number")
        if (
            not isinstance(field, str)
            or field not in GROUNDED_VOICE_PROFILE_FIELDS
            or not isinstance(value, str)
            or not value.strip()
            or not isinstance(quote, str)
            or not 8 <= len(quote) <= 320
            or not isinstance(chapter, int)
            or isinstance(chapter, bool)
            or chapter < 1
        ):
            continue
        current = character.get(field)
        if isinstance(current, list):
            still_current = value in current
        else:
            still_current = isinstance(current, str) and current == value
        if not still_current or not any(
            sample.get("chapter_number") == chapter and quote in str(sample.get("excerpt") or "")
            for sample in baseline_samples
        ):
            continue
        key = (field, value, chapter)
        if key in seen:
            continue
        seen.add(key)
        grounded.append({"field": field, "value": value, "quote": quote, "chapter_number": chapter})
        if len(grounded) >= limit:
            break
    return grounded


def disambiguate_voice_aliases(characters: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exclude aliases that could name another cast member's identity."""
    names = [
        " ".join(str(character.get("name") or "").casefold().split()) for character in characters
    ]
    aliases_by_character = [
        {
            " ".join(str(alias).casefold().split())
            for alias in character.get("aliases") or []
            if isinstance(alias, str) and alias.strip()
        }
        for character in characters
    ]
    resolved: list[dict[str, Any]] = []
    for index, character in enumerate(characters):
        safe_aliases: list[str] = []
        for alias in character.get("aliases") or []:
            if not isinstance(alias, str) or not alias.strip():
                continue
            folded = " ".join(alias.casefold().split())
            if any(
                folded in aliases_by_character[other]
                or re.search(rf"(?<!\w){re.escape(folded)}(?!\w)", names[other])
                for other in range(len(characters))
                if other != index
            ):
                continue
            safe_aliases.append(alias)
        resolved.append({**character, "aliases": safe_aliases})
    return resolved


def split_voice_passage(
    text: str, *, max_chars: int = 3_500, overlap: int = 200
) -> list[dict[str, Any]]:
    """Partition a passage into bounded overlapping ranges with no uncovered characters."""
    if max_chars < 1 or overlap < 0 or overlap >= max_chars:
        raise ValueError("invalid_voice_section_size")
    if not text:
        return []
    sections: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + max_chars // 2, end)
            if boundary > start + overlap:
                end = boundary + 1
        sections.append({"start": start, "end": end, "text": text[start:end]})
        if end == len(text):
            break
        start = end - overlap
    return sections


def voice_ranges_cover_text(ranges: Iterable[dict[str, Any]], length: int) -> bool:
    """Return true only when successful sections cover the entire submitted source."""
    if length <= 0:
        return False
    cursor = 0
    for item in sorted(ranges, key=lambda value: int(value["start"])):
        start, end = int(item["start"]), int(item["end"])
        if start < 0 or end > length or end <= start or start > cursor:
            return False
        cursor = max(cursor, end)
    return cursor == length


def voice_source_anchors_for_section(
    passage: str,
    section: dict[str, Any],
    samples: Sequence[dict[str, Any]],
    *,
    anchor_chars: int = 110,
) -> list[str]:
    """Return exact attributed quote fragments overlapping a reviewed source range."""
    if anchor_chars < 1:
        raise ValueError("invalid_voice_anchor_size")
    anchors: list[str] = []
    for source_range in voice_source_ranges_for_section(passage, section, samples):
        fragment = passage[source_range["start"] : source_range["end"]].strip()
        if not fragment:
            continue
        first = fragment[:anchor_chars]
        anchors.append(first)
        if len(fragment) > anchor_chars:
            last = fragment[-anchor_chars:]
            if last != first:
                anchors.append(last)
    return list(dict.fromkeys(anchors))


def voice_source_ranges_for_section(
    passage: str,
    section: dict[str, Any],
    samples: Sequence[dict[str, Any]],
) -> list[dict[str, int]]:
    """Locate only attributable source spans, never a whole mixed-prose section."""
    section_start, section_end = int(section["start"]), int(section["end"])
    if section_start < 0 or section_end > len(passage) or section_end <= section_start:
        raise ValueError("invalid_voice_section_range")
    ranges: list[dict[str, int]] = []
    for sample in samples:
        excerpt = str(sample.get("excerpt") or "")
        if not excerpt:
            continue
        source_start, source_end = sample.get("source_start"), sample.get("source_end")
        if source_start is not None or source_end is not None:
            if not (
                isinstance(source_start, int)
                and isinstance(source_end, int)
                and 0 <= source_start < source_end <= len(passage)
                and passage[source_start:source_end] == excerpt
            ):
                continue
            occurrences = [source_start]
        else:
            occurrences = []
            search_start = 0
            while True:
                start = passage.find(excerpt, search_start)
                if start < 0:
                    break
                occurrences.append(start)
                search_start = start + max(1, len(excerpt))
            # A legacy sample without offsets cannot disambiguate identical
            # text at multiple locations. Do not claim either as reviewed.
            if len(occurrences) != 1:
                continue
        for start in occurrences:
            overlap_start = max(start, section_start)
            overlap_end = min(start + len(excerpt), section_end)
            if overlap_end > overlap_start:
                ranges.append({"start": overlap_start, "end": overlap_end})
    return ranges


def voice_review_character_context(
    character_name: str,
    voice_mode: str,
    source_anchors: Sequence[str],
    *,
    profile_claims: Sequence[dict[str, Any]] = (),
    baseline_style: str = "",
) -> str:
    """Keep narrator and dialogue attribution instructions distinct in the model prompt."""
    if voice_mode == "first_person_narration":
        guidance = (
            "The narrator identity was selected by the author, not inferred from 'I'. "
            "Review narration only; do not assign quoted dialogue to the narrator."
        )
        evidence_label = "narration"
    elif voice_mode == "dialogue":
        guidance = (
            "Review only dialogue attributable to this character. Do not treat narration "
            "or unattributed dialogue as their speech."
        )
        evidence_label = "dialogue"
    else:
        raise ValueError("invalid_voice_mode")
    anchors = "\n".join(source_anchors) or "None; do not make a voice finding in this section."
    grounded_notes = "\n".join(
        f"- {claim['field']}: {claim['value']} (chapter {claim['chapter_number']}; "
        f"source quote: {claim['quote']})"
        for claim in profile_claims
    )
    return (
        f"Review only {character_name} in {voice_mode.replace('_', ' ')} mode. "
        f"{guidance} Grounded {evidence_label} anchors overlapping this section; "
        f"use the full section text below for exact citations:\n{anchors}"
        + (
            f"\nCited profile notes (context, not substitute baseline evidence):\n{grounded_notes}"
            if grounded_notes
            else ""
        )
        + (
            "\nObserved style of the supplied baseline excerpts (descriptive, not proof "
            f"of a finding):\n{baseline_style}"
            if baseline_style
            else ""
        )
    )


def attributed_voice_samples(
    source: str,
    *,
    character_name: str,
    aliases: Sequence[str] = (),
    chapter_number: int,
    include_offsets: bool = False,
    first_person_speaker: bool = False,
) -> list[dict[str, Any]]:
    """Keep direct attributions and tightly anchored, unambiguous pronoun attributions.

    Include narrator-tagged speech only when the caller verified that the
    first-person narrator is this character and no other known cast member.
    """
    names = [character_name, *aliases]
    names = [name.strip() for name in names if isinstance(name, str) and name.strip()]
    if not names:
        return []
    name_pattern = "|".join(re.escape(name) for name in sorted(set(names), key=len, reverse=True))
    direct_speaker_pattern = f"{name_pattern}|I" if first_person_speaker else name_pattern
    # A tag such as "said Alice Smith" cannot establish that a different
    # character named Alice spoke. The word boundary alone accepts the prefix.
    name_end = r"\b(?!\s+(?-i:[A-Z])[\w'’-]*)"
    speaker_before = re.compile(
        rf"(?:\b(?:{direct_speaker_pattern})\b\s+(?:said|asked|replied|told|whispered|shouted|muttered|answered)\b|"
        rf"\b(?:said|asked|replied|whispered|shouted|muttered|answered)\s+\b(?:{direct_speaker_pattern}){name_end})",
        re.IGNORECASE,
    )
    speaker_after = re.compile(
        rf"^\s*[,;]?\s*(?:said|asked|replied|whispered|shouted|muttered|answered)\s+\b(?:{direct_speaker_pattern}){name_end}",
        re.IGNORECASE,
    )
    speaker_after_name = re.compile(
        rf"^\s*[,;]?\s*\b(?:{direct_speaker_pattern})\b\s+"
        r"(?:said|asked|replied|whispered|shouted|muttered|answered)\b",
        re.IGNORECASE,
    )
    speech_verb = r"(?:said|asked|replied|told|whispered|shouted|muttered|answered)"
    pronoun_before = re.compile(rf"\b(?:he|she|they)\s+{speech_verb}\s*[:,]?\s*$", re.IGNORECASE)
    pronoun_after = re.compile(rf"^\s*[,;]?\s*(?:he|she|they)\s+{speech_verb}\b", re.IGNORECASE)
    antecedent = re.compile(
        rf"(?:^|[.!?][\"”’']?\s+|[\"”’']\s+)(?:{name_pattern})\b(?P<context>[^.!?\n\"“”‘’]{{1,120}})[.!?]\s*$",
        re.IGNORECASE,
    )
    samples: list[dict[str, Any]] = []
    previous_quote_end = 0
    for match in VOICE_SPEECH_QUOTE_PATTERN.finditer(source):
        quote_group = next(
            group for group in ("double", "curly", "single") if match.group(group) is not None
        )
        quote = match.group(quote_group).strip()
        before = source[max(previous_quote_end, match.start() - 60) : match.start()]
        previous_quote_end = match.end()
        if not quote:
            continue
        after = source[match.end() : min(len(source), match.end() + 60)]
        next_quote = VOICE_SPEECH_QUOTE_PATTERN.search(after)
        if next_quote:
            after = after[: next_quote.start()]
        confidence = "explicit"
        preceding_speaker = speaker_before.search(before)
        preceding_is_direct = bool(
            preceding_speaker
            and not re.search(r"[.!?]\s+", before[preceding_speaker.end() :])
            and not re.search(
                rf"\b(?:[A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)?|he|she|they)\s+{speech_verb}\b",
                before[preceding_speaker.end() :],
                re.IGNORECASE,
            )
        )
        if not (
            preceding_is_direct
            or speaker_after.search(after)
            or (quote.endswith((",", "?", "!")) and speaker_after_name.search(after))
        ):
            paragraph_break = source.rfind("\n\n", 0, match.start())
            paragraph_start = paragraph_break + 2 if paragraph_break >= 0 else 0
            window_start = max(paragraph_start, match.start() - 200)
            context_before = source[window_start : match.start()]
            if window_start > paragraph_start:
                context_before = " " + context_before
            pronoun = pronoun_before.search(context_before)
            if pronoun:
                context_before = context_before[: pronoun.start()]
            elif not pronoun_after.match(after):
                continue
            anchor = antecedent.search(context_before)
            if not anchor or re.search(r"\b[A-Z][a-z]{1,}\b", anchor["context"]):
                continue
            confidence = "contextual"
        quote_start = source.find(quote, match.start(quote_group), match.end(quote_group))
        sections = split_voice_passage(quote, max_chars=700, overlap=80)
        shared_source = {
            "source_id": hashlib.sha256(
                f"{chapter_number}:{quote_start}:{quote}".encode()
            ).hexdigest()
        }
        for section in sections:
            excerpt = section["text"]
            source_offsets = (
                {
                    "source_start": quote_start + section["start"],
                    "source_end": quote_start + section["end"],
                }
                if include_offsets
                else {}
            )
            samples.append(
                {
                    "character_name": character_name,
                    "chapter_number": chapter_number,
                    "excerpt": excerpt,
                    **shared_source,
                    **source_offsets,
                    **(
                        {"attribution_confidence": confidence} if confidence == "contextual" else {}
                    ),
                }
            )
    return samples


def first_person_narration_samples(
    source: str, *, chapter_number: int, include_offsets: bool = False
) -> list[dict[str, Any]]:
    """Collect first-person prose, excluding quotes when testing narrator perspective."""
    samples: list[dict[str, Any]] = []
    quoted_ranges = [
        (match.start(), match.end()) for match in VOICE_SPEECH_QUOTE_PATTERN.finditer(source)
    ]
    paragraph_breaks = list(re.finditer(r"\n\s*\n", source))
    block_ranges = []
    block_start = 0
    for paragraph_break in paragraph_breaks:
        block_ranges.append((block_start, paragraph_break.start()))
        block_start = paragraph_break.end()
    block_ranges.append((block_start, len(source)))
    quote_index = 0
    for block_start, block_end in block_ranges:
        block = source[block_start:block_end]
        if re.match(r"\s*[—–]\s+", block):
            # A paragraph-opening dialogue dash identifies speech, not the
            # first-person narrator. The speaker remains unattributed here.
            continue
        source_id = hashlib.sha256(f"{chapter_number}:{block_start}:{block}".encode()).hexdigest()
        narration_ranges = []
        span_start = 0
        while quote_index < len(quoted_ranges) and quoted_ranges[quote_index][1] <= block_start:
            quote_index += 1
        current_quote = quote_index
        while current_quote < len(quoted_ranges) and quoted_ranges[current_quote][0] < block_end:
            quote_start, quote_end = quoted_ranges[current_quote]
            clipped_start = max(quote_start, block_start) - block_start
            clipped_end = min(quote_end, block_end) - block_start
            narration_ranges.append((span_start, clipped_start))
            span_start = clipped_end
            current_quote += 1
        narration_ranges.append((span_start, len(block)))
        for span_start, span_end in narration_ranges:
            raw_span = block[span_start:span_end]
            narration = raw_span.strip()
            # Fiction often uses short first-person paragraphs. Keep them as
            # independent evidence; the later aggregate thresholds still
            # prevent a few short fragments from producing a voice verdict.
            if len(narration.split()) < 2 or not re.search(
                r"\b(?:I|me|my|mine|we|our)\b", narration
            ):
                continue
            narration_start = block_start + span_start + len(raw_span) - len(raw_span.lstrip())
            for section in split_voice_passage(narration, max_chars=700, overlap=80):
                raw_excerpt = section["text"]
                excerpt = raw_excerpt.strip()
                if excerpt:
                    source_offsets: dict[str, int] = {}
                    if include_offsets:
                        excerpt_start = (
                            narration_start
                            + section["start"]
                            + len(raw_excerpt)
                            - len(raw_excerpt.lstrip())
                        )
                        source_offsets = {
                            "source_start": excerpt_start,
                            "source_end": excerpt_start + len(excerpt),
                        }
                    samples.append(
                        {
                            "character_name": None,
                            "chapter_number": chapter_number,
                            "excerpt": excerpt,
                            "source_id": source_id,
                            **source_offsets,
                        }
                    )
    return samples


def voice_independent_source_texts(samples: Sequence[dict[str, Any]]) -> list[str]:
    """Reassemble each source once so overlap cannot inflate voice metrics."""
    by_source: dict[str, list[dict[str, Any]]] = {}
    for index, sample in enumerate(samples):
        source_id = str(sample.get("source_id") or f"sample-{index}")
        by_source.setdefault(source_id, []).append(sample)
    texts: list[str] = []
    for source_samples in by_source.values():
        if all(
            isinstance(sample.get("source_start"), int)
            and isinstance(sample.get("source_end"), int)
            and sample["source_end"] - sample["source_start"]
            == len(str(sample.get("excerpt") or ""))
            for sample in source_samples
        ):
            positions: dict[int, str] = {}
            for sample in source_samples:
                positions.update(
                    (sample["source_start"] + offset, char)
                    for offset, char in enumerate(str(sample.get("excerpt") or ""))
                )
            contiguous: list[str] = []
            previous: int | None = None
            for position, char in sorted(positions.items()):
                if previous is not None and position != previous + 1:
                    contiguous.append(" ")
                contiguous.append(char)
                previous = position
            texts.append("".join(contiguous))
        else:
            # Older samples have no offsets; do not double-count overlapping pieces.
            texts.append(
                max(
                    (str(sample.get("excerpt") or "") for sample in source_samples),
                    key=lambda excerpt: len(excerpt.split()),
                )
            )
    return texts


def voice_baseline_size(samples: Sequence[dict[str, Any]]) -> tuple[int, int]:
    """Count independent sources without multiplying overlap between their segments."""
    texts = voice_independent_source_texts(samples)
    return len(texts), sum(len(source.split()) for source in texts)


def voice_baseline_style_summary(samples: Sequence[dict[str, Any]]) -> str:
    """Describe only measurable patterns in the supplied, source-backed excerpts."""
    texts = voice_independent_source_texts(samples)
    if not any(text.strip() for text in texts):
        return ""
    metrics = compute_voice_metrics(texts)
    count = metrics["sample_dialogue_count"]
    words = metrics["sample_word_count"]
    sentence_lengths = [
        len(re.findall(r"[^\W_]+(?:['’][^\W_]+)*", sentence, flags=re.UNICODE))
        for text in texts
        for sentence in re.split(r"[.!?]+", text)
        if sentence.strip()
    ]
    observed = [
        f"{count} independent {'excerpt' if count == 1 else 'excerpts'}; {words} words",
        f"average sentence length {metrics['avg_sentence_length']} words",
        (
            f"observed sentence-length range {min(sentence_lengths)}–{max(sentence_lengths)} words"
            if sentence_lengths
            else "no complete sentence boundary observed"
        ),
        f"average word length {metrics['avg_word_length_x100'] / 100:.1f} letters",
        f"contractions {metrics['contraction_rate_x1000'] / 10:.1f} per 100 words",
        f"formal vocabulary markers {metrics['formality_score_x1000'] / 10:.1f} per 100 words",
        f"emotion vocabulary markers {metrics['emotional_intensity_x1000'] / 10:.1f} per 100 words",
        "punctuation per 100 words: "
        f"questions {metrics['question_rate_x1000'] / 10:.1f}, "
        f"exclamations {metrics['exclamation_rate_x1000'] / 10:.1f}, "
        f"ellipses {metrics['ellipsis_rate_x1000'] / 10:.1f}, "
        f"dashes {metrics['dash_rate_x1000'] / 10:.1f}",
    ]
    phrases: list[str] = []
    for phrase in metrics["signature_phrases"]:
        chapters = sorted(
            {
                int(sample["chapter_number"])
                for sample in samples
                if isinstance(sample.get("chapter_number"), int)
                and phrase in str(sample.get("excerpt") or "").casefold()
            }
        )
        if chapters:
            phrases.append(f"{phrase!r} (chapter {', '.join(map(str, chapters))})")
    if phrases:
        observed.append("repeated phrases: " + "; ".join(phrases))
    return "; ".join(observed) + ". These are cues, not a voice verdict; cite exact excerpts."


def voice_baseline_sufficient(
    samples: Sequence[dict[str, Any]], *, min_samples: int = 3, min_words: int = 60
) -> bool:
    source_count, word_count = voice_baseline_size(samples)
    return source_count >= min_samples and word_count >= min_words


def voice_current_sample_sufficient(samples: Sequence[dict[str, Any]], *, voice_mode: str) -> bool:
    """Require enough independent current voice before scoring or claiming certainty."""
    minimums = VOICE_CURRENT_SAMPLE_MINIMUMS.get(voice_mode)
    if minimums is None:
        raise ValueError("invalid_voice_mode")
    minimum_sources, minimum_words = minimums
    source_count, word_count = voice_baseline_size(samples)
    return source_count >= minimum_sources and word_count >= minimum_words


def voice_samples_have_reliable_attribution(samples: Sequence[dict[str, Any]]) -> bool:
    """A match score needs current excerpts with no tentative speaker assignments."""
    return bool(samples) and all(
        sample.get("attribution_confidence") not in {"contextual", "unverified_narrator"}
        for sample in samples
    )


def closest_alternate_voice_match(
    *,
    character_name: str,
    submitted_excerpts: Sequence[str],
    own_score: int,
    baseline_by_name: dict[str, Sequence[dict[str, Any]]],
) -> tuple[str | None, int | None]:
    """Return a source-backed stylistic similarity, never an identity verdict."""
    if sum(len(excerpt.split()) for excerpt in submitted_excerpts) < 12:
        return None, None
    submitted_metrics = compute_voice_metrics(list(submitted_excerpts))
    best_name: str | None = None
    best_score: int | None = None
    for name, samples in baseline_by_name.items():
        if (
            name == character_name
            or not voice_baseline_sufficient(samples)
            or not voice_samples_have_reliable_attribution(samples)
        ):
            continue
        baseline_metrics = compute_voice_metrics(voice_independent_source_texts(samples))
        score, _signals = score_voice_match(baseline_metrics, submitted_metrics)
        if score > own_score and score >= 60 and (best_score is None or score > best_score):
            best_name, best_score = name, score
    return best_name, best_score


def select_diverse_voice_baseline_samples(
    samples: Sequence[dict[str, Any]],
    *,
    submitted_text: str,
    character_name: str,
    aliases: Sequence[str] = (),
    max_samples: int = 16,
) -> list[dict[str, Any]]:
    """Rank source-backed samples using the whole passage and spread them across chapters."""
    if max_samples < 1 or not samples:
        return []
    tokens = re.compile(r"[^\W\d_][\w'-]{3,}", re.UNICODE)
    stop = {
        "about",
        "after",
        "again",
        "before",
        "could",
        "from",
        "have",
        "into",
        "said",
        "that",
        "their",
        "there",
        "these",
        "this",
        "those",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
    }

    def terms(value: str) -> set[str]:
        return {word.casefold() for word in tokens.findall(value) if word.casefold() not in stop}

    dialogue_terms: set[str] = set()
    for sample in attributed_voice_samples(
        submitted_text,
        character_name=character_name,
        aliases=aliases,
        chapter_number=0,
    ):
        dialogue_terms.update(terms(sample["excerpt"]))
    passage_terms: set[str] = set()
    for section in split_voice_passage(submitted_text):
        passage_terms.update(terms(section["text"]))

    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, sample in enumerate(samples):
        excerpt_terms = terms(str(sample.get("excerpt") or ""))
        relevance = 3 * len(excerpt_terms & dialogue_terms) + len(excerpt_terms & passage_terms)
        ranked.append((relevance, index, sample))

    by_chapter: dict[int, list[tuple[int, int, dict[str, Any]]]] = {}
    for item in ranked:
        chapter = item[2].get("chapter_number")
        if isinstance(chapter, int):
            by_chapter.setdefault(chapter, []).append(item)
    for chapter_samples in by_chapter.values():
        chapter_samples.sort(key=lambda item: (-item[0], item[1]))

    chapter_numbers = sorted(by_chapter)
    if max_samples == 1:
        chapter_numbers = [
            min(
                chapter_numbers,
                key=lambda chapter: (
                    -by_chapter[chapter][0][0],
                    by_chapter[chapter][0][1],
                ),
            )
        ]
    elif len(chapter_numbers) > max_samples:
        spread_count = max(1, max_samples // 2)
        spread = {
            chapter_numbers[round(index * (len(chapter_numbers) - 1) / max(1, spread_count - 1))]
            for index in range(spread_count)
        }
        additional = sorted(
            (chapter for chapter in chapter_numbers if chapter not in spread),
            key=lambda chapter: (-by_chapter[chapter][0][0], by_chapter[chapter][0][1]),
        )[: max_samples - len(spread)]
        chapter_numbers = sorted([*spread, *additional])

    selected: list[tuple[int, int, dict[str, Any]]] = [
        by_chapter[chapter].pop(0) for chapter in chapter_numbers
    ]
    remaining = sorted(
        (item for chapter in chapter_numbers for item in by_chapter[chapter]),
        key=lambda item: (-item[0], item[1]),
    )
    selected_sources = {str(item[2].get("source_id") or f"sample-{item[1]}") for item in selected}
    repeated: list[tuple[int, int, dict[str, Any]]] = []
    for item in remaining:
        source_id = str(item[2].get("source_id") or f"sample-{item[1]}")
        if source_id in selected_sources:
            repeated.append(item)
        else:
            selected.append(item)
            selected_sources.add(source_id)
            if len(selected) == max_samples:
                break
    selected.extend(repeated[: max_samples - len(selected)])
    return [item[2] for item in sorted(selected, key=lambda item: item[1])]


def _voice_excerpt_evidence_matches(
    samples: Sequence[dict[str, Any]],
    excerpt: str,
    *,
    chapter_number: int | None = None,
    source_start: int | None = None,
    require_offsets: bool = False,
) -> list[list[dict[str, Any]]]:
    """Find exact citations within one source, including overlapping sample boundaries."""
    matches: list[list[dict[str, Any]]] = []
    groups: dict[tuple[Any, tuple[str, str | int]], list[dict[str, Any]]] = {}
    for index, sample in enumerate(samples):
        if chapter_number is not None and sample.get("chapter_number") != chapter_number:
            continue
        sample_text = sample.get("excerpt")
        if not isinstance(sample_text, str) or not sample_text:
            continue
        start, end = sample.get("source_start"), sample.get("source_end")
        if (
            type(start) is int
            and type(end) is int
            and start >= 0
            and end - start == len(sample_text)
        ):
            source_id = sample.get("source_id")
            group_id = ("source", str(source_id)) if source_id else ("sample", index)
            groups.setdefault((sample.get("chapter_number"), group_id), []).append(sample)
        elif not require_offsets and excerpt in sample_text:
            matches.append([sample])

    for group in groups.values():
        source_chars: dict[int, str] = {}
        valid = True
        for sample in group:
            for offset, char in enumerate(sample["excerpt"]):
                position = sample["source_start"] + offset
                previous = source_chars.get(position)
                if previous is not None and previous != char:
                    valid = False
                    break
                source_chars[position] = char
            if not valid:
                break
        if not valid:
            continue
        starts = [source_start] if source_start is not None else source_chars.keys()
        for candidate in starts:
            if not all(
                source_chars.get(candidate + offset) == char for offset, char in enumerate(excerpt)
            ):
                continue
            matches.append(
                [
                    sample
                    for sample in group
                    if sample["source_start"] < candidate + len(excerpt)
                    and sample["source_end"] > candidate
                ]
            )
    return matches


def validate_voice_section_result(
    raw: str,
    *,
    section_text: str,
    section_start: int = 0,
    baseline_samples: Sequence[dict[str, Any]],
    submitted_samples: Sequence[dict[str, Any]],
    character_name: str,
) -> dict[str, Any]:
    """Reject malformed results and any claim without exact, stored evidence."""
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise VoiceReviewFormatError("voice_review_invalid_json") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("issues"), list):
        raise VoiceReviewFormatError("voice_review_invalid_shape")
    verdict = parsed.get("overall_verdict")
    if not isinstance(verdict, str) or not verdict.strip():
        raise VoiceReviewFormatError("voice_review_missing_verdict")
    valid_issues: list[dict[str, Any]] = []
    for issue in parsed["issues"]:
        if not isinstance(issue, dict) or issue.get("character_name") != character_name:
            raise VoiceReviewFormatError("voice_review_wrong_character")
        excerpt = issue.get("submitted_excerpt")
        baseline_excerpt = issue.get("baseline_excerpt")
        chapter = issue.get("baseline_chapter_number")
        occurrences: list[int] = []
        if isinstance(excerpt, str) and excerpt:
            cursor = 0
            while (position := section_text.find(excerpt, cursor)) >= 0:
                occurrences.append(section_start + position)
                cursor = position + 1
        submitted_matches = (
            [
                _voice_excerpt_evidence_matches(
                    submitted_samples,
                    excerpt,
                    source_start=position,
                    require_offsets=any(
                        "source_start" in sample or "source_end" in sample
                        for sample in submitted_samples
                    ),
                )
                for position in occurrences
            ]
            if isinstance(excerpt, str)
            else []
        )
        all_occurrences_supported = bool(submitted_matches) and all(submitted_matches)
        matching_submitted = [
            sample for occurrence in submitted_matches for match in occurrence for sample in match
        ]
        baseline_matches = (
            _voice_excerpt_evidence_matches(
                baseline_samples, baseline_excerpt, chapter_number=chapter
            )
            if isinstance(baseline_excerpt, str) and type(chapter) is int
            else []
        )
        matching_baseline = [sample for match in baseline_matches for sample in match]
        if (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or excerpt not in section_text
            or not matching_submitted
            or not all_occurrences_supported
            or not isinstance(baseline_excerpt, str)
            or not baseline_excerpt.strip()
            or not isinstance(chapter, int)
            or isinstance(chapter, bool)
            or not matching_baseline
        ):
            raise VoiceReviewFormatError("voice_review_unsupported_evidence")
        classification = issue.get("classification")
        severity = issue.get("severity")
        confidence = issue.get("confidence")
        if classification not in {"confirmed", "possible", "justified_variation"}:
            raise VoiceReviewFormatError("voice_review_invalid_classification")
        if severity not in {"minor", "moderate", "critical"}:
            raise VoiceReviewFormatError("voice_review_invalid_severity")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise VoiceReviewFormatError("voice_review_invalid_confidence")
        if not all(
            isinstance(issue.get(field), str) and issue[field].strip()
            for field in (
                "title",
                "description",
                "revision_direction",
                "intentionality_prompt",
            )
        ):
            raise VoiceReviewFormatError("voice_review_missing_explanation")
        if classification == "confirmed" and (
            any(
                sample.get("attribution_confidence") in {"contextual", "unverified_narrator"}
                for sample in matching_submitted
            )
            or any(
                sample.get("attribution_confidence") in {"contextual", "unverified_narrator"}
                for sample in matching_baseline
            )
        ):
            issue = {
                **issue,
                "classification": "possible",
                "confidence": min(confidence, 0.75),
            }
        valid_issues.append(issue)
    return {"issues": valid_issues, "overall_verdict": verdict.strip()}
