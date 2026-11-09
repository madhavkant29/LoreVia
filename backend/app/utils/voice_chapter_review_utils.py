"""Source-wide voice work planning and result aggregation."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from app.utils.characters.narrator import detect_explicit_first_person_narrator
from app.utils.voice_review_coverage import (
    aggregate_voice_review_coverage,
    unattributed_quoted_ranges,
)
from app.utils.voice_review_utils import (
    attributed_voice_samples,
    disambiguate_voice_aliases,
    first_person_narration_samples,
    split_voice_passage,
)


def voice_chapter_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_voice_chapter_work(
    text: str, chapter_number: int, characters: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Plan every known attributable voice without a cast-count cutoff."""
    cast = disambiguate_voice_aliases(list(characters))
    sections = split_voice_passage(text, max_chars=10_000, overlap=500)
    narrator = detect_explicit_first_person_narrator(text, cast)
    dialogue_narrator = narrator
    work: list[dict[str, Any]] = []
    unreviewed_known_ranges: list[dict[str, int]] = []
    samples_by_character = {
        str(character["id"]): attributed_voice_samples(
            text,
            character_name=str(character["name"]),
            aliases=list(character.get("aliases") or []),
            chapter_number=chapter_number,
            include_offsets=True,
            first_person_speaker=dialogue_narrator is character,
        )
        for character in cast
    }
    for character in cast:
        samples = samples_by_character[str(character["id"])]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for sample in samples:
            grouped.setdefault(str(sample["source_id"]), []).append(sample)
        selected_sections: dict[int, dict[str, Any]] = {}
        local_samples: dict[int, set[tuple[int, int]]] = {}
        for source_samples in grouped.values():
            spans = {
                (int(sample["source_start"]), int(sample["source_end"]))
                for sample in source_samples
            }
            quote_start = min(start for start, _end in spans)
            quote_end = max(end for _start, end in spans)
            matched = False
            for section in sections:
                if section["start"] > quote_start or quote_end > section["end"]:
                    continue
                section_start = int(section["start"])
                if section_start not in local_samples:
                    # A quote that straddles a section edge may lose its speaker
                    # tag. Schedule only a section that can recover every span.
                    local_samples[section_start] = {
                        (
                            section_start + int(sample["source_start"]),
                            section_start + int(sample["source_end"]),
                        )
                        for sample in attributed_voice_samples(
                            section["text"],
                            character_name=str(character["name"]),
                            aliases=list(character.get("aliases") or []),
                            chapter_number=chapter_number,
                            include_offsets=True,
                            first_person_speaker=dialogue_narrator is character,
                        )
                    }
                if spans <= local_samples[section_start]:
                    selected_sections[section_start] = section
                    matched = True
                    break
            if not matched:
                unreviewed_known_ranges.append({"start": quote_start, "end": quote_end})
        for section in selected_sections.values():
            work.append(
                {
                    "key": f"dialogue:{character['id']}:{section['start']}",
                    "character_id": str(character["id"]),
                    "character_name": str(character["name"]),
                    "voice_mode": "dialogue",
                    "start": section["start"],
                    "end": section["end"],
                }
            )
    if narrator is not None and first_person_narration_samples(
        text, chapter_number=chapter_number, include_offsets=True
    ):
        for section in sections:
            if first_person_narration_samples(section["text"], chapter_number=chapter_number):
                work.append(
                    {
                        "key": f"first_person_narration:{narrator['id']}:{section['start']}",
                        "character_id": str(narrator["id"]),
                        "character_name": str(narrator["name"]),
                        "voice_mode": "first_person_narration",
                        "start": section["start"],
                        "end": section["end"],
                    }
                )
    attributed = [
        {"start": int(sample["source_start"]), "end": int(sample["source_end"])}
        for samples in samples_by_character.values()
        for sample in samples
        if sample.get("attribution_confidence") != "contextual"
    ]
    attribution_coverage = aggregate_voice_review_coverage(
        [{"coverage": {"processed_ranges": attributed, "total_characters": len(text)}}],
        total_characters=len(text),
    )
    unknown_quotes = unattributed_quoted_ranges(text, attribution_coverage["unattributed_ranges"])
    return {
        "work": work,
        "sections": [{"start": item["start"], "end": item["end"]} for item in sections],
        "unknown_quotes": unknown_quotes,
        "unreviewed_known_ranges": unreviewed_known_ranges,
        "narrator_identified": narrator is not None,
        "narration_present": bool(
            first_person_narration_samples(text, chapter_number=chapter_number)
        ),
        "known_character_count": len(cast),
    }


def aggregate_voice_chapter_results(
    *,
    source_text: str,
    plan: dict[str, Any],
    completed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Translate bounded result offsets to the whole chapter and deduplicate overlap."""
    total_characters = len(source_text)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    seen: set[str] = set()
    seen_passages: dict[tuple[str, str, str, str, str], set[int]] = {}
    for item in plan["work"]:
        result = completed.get(item["key"])
        if result is None:
            continue
        review = result["review"]
        group_key = (item["character_id"], item["voice_mode"])
        group = grouped.setdefault(
            group_key,
            {
                "character_id": item["character_id"],
                "character_name": item["character_name"],
                "voice_mode": item["voice_mode"],
                "status": "complete",
                "issues": [],
                "warnings": [],
                "coverage": [],
            },
        )
        if review.get("status") == "insufficient_evidence":
            group["status"] = "insufficient_evidence"
        elif review.get("status") != "complete" and group["status"] != "insufficient_evidence":
            group["status"] = "partial_evidence"
        for issue in review.get("issues") or []:
            key = str(issue.get("finding_key") or "")
            excerpt = str(issue.get("submitted_excerpt") or "")
            positions: set[int] = set()
            if excerpt:
                cursor = item["start"]
                while (position := source_text.find(excerpt, cursor, item["end"])) >= 0:
                    positions.add(position)
                    cursor = position + 1
            claim = (
                item["character_id"],
                item["voice_mode"],
                excerpt,
                str(issue.get("baseline_excerpt") or ""),
                str(issue.get("baseline_chapter_number") or ""),
            )
            if positions and positions & seen_passages.get(claim, set()):
                continue
            if positions:
                seen_passages.setdefault(claim, set()).update(positions)
                if key in seen:
                    # Repeated source text can give separate passages the same
                    # section key. Keep both findings distinct in the chapter.
                    occurrence = source_text.count(excerpt, 0, min(positions)) + 1
                    key = hashlib.sha256(f"{key}:occurrence:{occurrence}".encode()).hexdigest()
            if key and key not in seen:
                seen.add(key)
                group["issues"].append({**issue, "finding_key": key})
        group["warnings"].extend(result.get("warnings") or [])
        coverage = result.get("coverage") or {}
        group["coverage"].append(
            {
                "coverage": {
                    "processed_ranges": [
                        {"start": item["start"] + span["start"], "end": item["start"] + span["end"]}
                        for span in coverage.get("processed_ranges") or []
                    ],
                    "compared_ranges": [
                        {"start": item["start"] + span["start"], "end": item["start"] + span["end"]}
                        for span in coverage.get("compared_ranges") or []
                    ],
                    "total_characters": total_characters,
                }
            }
        )
    voices = []
    for group in grouped.values():
        group["coverage"] = aggregate_voice_review_coverage(
            group["coverage"], total_characters=total_characters
        )
        group["warnings"] = list(dict.fromkeys(group["warnings"]))
        voices.append(group)
    union = aggregate_voice_review_coverage(
        [{"coverage": voice["coverage"]} for voice in voices],
        total_characters=total_characters,
    )
    unknown_quotes = unattributed_quoted_ranges(
        source_text, union.get("not_compared_ranges") or union["unattributed_ranges"]
    )
    missing = [item for item in plan["work"] if item["key"] not in completed]
    unreviewed = [
        *list(plan.get("unreviewed_known_ranges") or []),
        *({"start": item["start"], "end": item["end"]} for item in missing),
    ]
    return {
        "status": (
            "insufficient_evidence"
            if not voices
            else "partial_evidence"
            if unreviewed
            or unknown_quotes
            or (plan.get("narration_present") and not plan["narrator_identified"])
            or any(v["status"] != "complete" for v in voices)
            else "complete"
        ),
        "voices": voices,
        "coverage": {**union, "unattributed_quoted_ranges": unknown_quotes},
        "unreviewed_ranges": unreviewed,
        "work_total": len(plan["work"]),
        "work_completed": len(completed),
        "narrator_identified": plan["narrator_identified"],
        "narration_present": bool(plan.get("narration_present")),
    }
