"""Aggregate source coverage across independently reviewed character voices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.utils.voice_review_utils import VOICE_SPEECH_QUOTE_PATTERN


def unattributed_quoted_ranges(
    passage: str, not_compared_ranges: Sequence[Mapping[str, int]]
) -> list[dict[str, int]]:
    """Return exact quoted source spans not compared with any voice baseline."""
    gaps: list[dict[str, int]] = []
    for quote in VOICE_SPEECH_QUOTE_PATTERN.finditer(passage):
        group = next(
            name for name in ("double", "curly", "single") if quote.group(name) is not None
        )
        quote_start, quote_end = quote.start(group), quote.end(group)
        for uncovered in not_compared_ranges:
            start = max(quote_start, uncovered["start"])
            end = min(quote_end, uncovered["end"])
            if start >= end:
                continue
            fragment = passage[start:end]
            if not fragment.strip():
                continue
            trimmed_start = start + len(fragment) - len(fragment.lstrip())
            trimmed_end = end - len(fragment) + len(fragment.rstrip())
            gaps.append({"start": trimmed_start, "end": trimmed_end})
    return gaps


def aggregate_voice_review_coverage(
    reviewed: Sequence[Mapping[str, Any]], *, total_characters: int
) -> dict[str, Any]:
    """Report the union of reviewed sections and its uncovered complement."""
    if total_characters < 0:
        raise ValueError("invalid_voice_coverage_length")

    ranges: list[tuple[int, int]] = []
    compared_ranges: list[tuple[int, int]] = []
    all_have_comparison_ranges = bool(reviewed)
    for character_review in reviewed:
        coverage = character_review.get("coverage")
        if (
            not isinstance(coverage, Mapping)
            or coverage.get("total_characters") != total_characters
        ):
            raise ValueError("invalid_voice_character_coverage")
        for field, target in (
            ("processed_ranges", ranges),
            ("compared_ranges", compared_ranges),
        ):
            source = coverage.get(field)
            if field == "compared_ranges" and source is None:
                all_have_comparison_ranges = False
                continue
            if not isinstance(source, list):
                raise ValueError("invalid_voice_character_coverage")
            for item in source:
                if not isinstance(item, Mapping):
                    raise ValueError("invalid_voice_character_coverage")
                start, end = item.get("start"), item.get("end")
                if (
                    type(start) is not int
                    or type(end) is not int
                    or not 0 <= start < end <= total_characters
                ):
                    raise ValueError("invalid_voice_character_coverage")
                target.append((start, end))

    def merged_with_gaps(
        source_ranges: list[tuple[int, int]],
    ) -> tuple[list[dict[str, int]], list[dict[str, int]]]:
        merged: list[dict[str, int]] = []
        for start, end in sorted(source_ranges):
            if merged and start <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], end)
            else:
                merged.append({"start": start, "end": end})
        gaps: list[dict[str, int]] = []
        cursor = 0
        for item in merged:
            if cursor < item["start"]:
                gaps.append({"start": cursor, "end": item["start"]})
            cursor = item["end"]
        if cursor < total_characters:
            gaps.append({"start": cursor, "end": total_characters})
        return merged, gaps

    merged, unattributed = merged_with_gaps(ranges)
    result = {
        "processed_ranges": merged,
        "unattributed_ranges": unattributed,
        "total_characters": total_characters,
    }
    if all_have_comparison_ranges:
        compared, not_compared = merged_with_gaps(compared_ranges)
        if any(
            not any(
                section["start"] <= item["start"] and item["end"] <= section["end"]
                for section in merged
            )
            for item in compared
        ):
            raise ValueError("invalid_voice_character_coverage")
        result["compared_ranges"] = compared
        result["not_compared_ranges"] = not_compared
    return result


def complete_cached_voice_review(
    payload: Mapping[str, Any],
    *,
    submitted_text: str,
    character_names: Sequence[str],
    voice_mode: str,
    baseline_by_name: Mapping[str, Sequence[Mapping[str, Any]]],
) -> bool:
    """Accept cached verdicts only with complete coverage and current source citations."""
    total_characters = len(submitted_text)
    if total_characters <= 0 or not character_names:
        return False
    review = payload.get("review")
    if (
        not isinstance(review, Mapping)
        or review.get("status") != "complete"
        or not isinstance(review.get("overall_verdict"), str)
        or not review["overall_verdict"].strip()
        or not isinstance(review.get("issues"), list)
        or payload.get("voice_mode") != voice_mode
        or payload.get("characters_reviewed") != list(character_names)
    ):
        return False

    per_character = payload.get("coverage_by_character")
    recorded = payload.get("coverage")
    if (
        not isinstance(per_character, list)
        or len(per_character) != len(character_names)
        or not isinstance(recorded, Mapping)
    ):
        return False
    if any(
        not isinstance(item, Mapping)
        or item.get("character_name") != name
        or type(item.get("total_characters")) is not int
        or item["total_characters"] != total_characters
        or not isinstance(item.get("unattributed_ranges"), list)
        for item, name in zip(per_character, character_names, strict=True)
    ):
        return False

    try:
        computed = aggregate_voice_review_coverage(
            [{"coverage": item} for item in per_character],
            total_characters=total_characters,
        )
    except (TypeError, ValueError):
        return False
    if (
        computed.get("unattributed_ranges")
        or not computed.get("compared_ranges")
        or type(recorded.get("total_characters")) is not int
    ):
        return False
    if any(recorded.get(field) != computed[field] for field in computed):
        return False
    quoted = recorded.get("unattributed_quoted_ranges")
    if quoted is not None and quoted != []:
        return False

    coverage_by_name = {
        name: item for name, item in zip(character_names, per_character, strict=True)
    }
    for issue in review["issues"]:
        if not isinstance(issue, Mapping):
            return False
        name = issue.get("character_name")
        excerpt = issue.get("submitted_excerpt")
        baseline_excerpt = issue.get("baseline_excerpt")
        chapter = issue.get("baseline_chapter_number")
        confidence = issue.get("confidence")
        classification = issue.get("classification")
        severity = issue.get("severity")
        if (
            not isinstance(name, str)
            or name not in coverage_by_name
            or not isinstance(excerpt, str)
            or not excerpt.strip()
            or not isinstance(baseline_excerpt, str)
            or not baseline_excerpt.strip()
            or type(chapter) is not int
            or not isinstance(classification, str)
            or classification not in {"confirmed", "possible", "justified_variation"}
            or not isinstance(severity, str)
            or severity not in {"minor", "moderate", "critical"}
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
            or not all(
                isinstance(issue.get(field), str) and issue[field].strip()
                for field in ("title", "description", "revision_direction", "intentionality_prompt")
            )
        ):
            return False
        if not any(
            sample.get("chapter_number") == chapter
            and baseline_excerpt in str(sample.get("excerpt") or "")
            for sample in baseline_by_name.get(name, ())
        ):
            return False
        compared = coverage_by_name[name]["compared_ranges"]
        start = submitted_text.find(excerpt)
        supported = False
        while start >= 0:
            end = start + len(excerpt)
            if any(span["start"] <= start and end <= span["end"] for span in compared):
                supported = True
                break
            start = submitted_text.find(excerpt, start + 1)
        if not supported:
            return False
    return True
