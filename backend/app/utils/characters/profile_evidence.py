"""Ground model-proposed character profile claims in the submitted source."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.utils.characters.narrator import first_person_narration_span

PROFILE_SCALAR_FIELDS = (
    "goal",
    "lie_they_believe",
    "backstory_wound",
    "arc_type",
    "arc_summary",
    "archetype",
    "first_appearance_context",
)
PROFILE_LIST_FIELDS = ("personality_tags", "motivations", "fears")
FIRST_PERSON_RE = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.I)
FIRST_PERSON_SUBJECT_RE = re.compile(r"\b(?:I|we)\b", re.I)
SPEECH_VERB_RE = r"(?:said|asked|answered|replied|told|cried|called|shouted|whispered)"
POST_QUOTE_SPEECH_VERB_RE = r"(?:said|asked|answered|replied|cried|called|shouted|whispered)"


def profile_quote_attributed_to_character(
    source_text: str,
    span: tuple[int, int],
    *,
    character_name: str,
    aliases: Sequence[str] = (),
    is_narrator: bool = False,
) -> bool:
    """Hold first-person claims unless the target speaks or acts in the cited text."""
    quote = source_text[span[0] : span[1]]
    pronouns = list(FIRST_PERSON_RE.finditer(quote))
    if not pronouns:
        return True
    if is_narrator:
        return first_person_narration_span(source_text, span)
    names = [name.strip() for name in [character_name, *aliases] if name.strip()]
    for name in names:
        pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
        for match in re.finditer(pattern, quote, re.I):
            before_name = quote[: match.start()]
            if not FIRST_PERSON_RE.search(before_name) and not FIRST_PERSON_SUBJECT_RE.search(
                quote
            ):
                return True
        before = source_text[max(0, span[0] - 100) : span[0]]
        after = source_text[span[1] : span[1] + 100]
        if re.search(rf"{pattern}\s+{SPEECH_VERB_RE}\b[^.!?]{{0,45}}$", before, re.I):
            return True
        if re.search(rf"^[^.!?]{{0,45}}{POST_QUOTE_SPEECH_VERB_RE}\s+{pattern}", after, re.I):
            return True
    return False


def character_mention_weight(entity: Mapping[str, Any]) -> int:
    """Prefer verified source occurrences over extraction-cluster row counts."""
    evidence = entity.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    if evidence.get("source_mention_count_verified") is True:
        count = evidence.get("mention_count")
        if isinstance(count, int) and not isinstance(count, bool):
            return max(0, count)
    evidence_cluster_size = evidence.get("cluster_size")
    cluster_size = entity.get("cluster_size")
    return max(
        1,
        evidence_cluster_size
        if isinstance(evidence_cluster_size, int) and not isinstance(evidence_cluster_size, bool)
        else 0,
        cluster_size if isinstance(cluster_size, int) and not isinstance(cluster_size, bool) else 0,
    )


def profile_evidence_packets(entity: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collect every distinct, bounded mention window in an identity cluster."""
    members = entity.get("cluster_members")
    packets: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for member in members if isinstance(members, list) else []:
        if not isinstance(member, dict):
            continue
        source_batch_key = str(member.get("source_batch_key") or "")
        source_windows = member.get("source_windows")
        if not isinstance(source_windows, list):
            source_windows = [
                {"start": member.get("source_start"), "text": member.get("source_text")}
            ]
        for window in source_windows:
            if not isinstance(window, dict):
                continue
            source_text = str(window.get("text") or "")
            if not source_text:
                continue
            source_start = window.get("start")
            source_start = (
                source_start if isinstance(source_start, int) and source_start >= 0 else 0
            )
            key = (source_batch_key, source_start, source_text)
            if key in seen:
                continue
            seen.add(key)
            packets.append(
                {
                    "source_batch_key": source_batch_key,
                    "source_start": source_start,
                    "text": source_text,
                }
            )
    return packets


def bundle_profile_evidence_packets(
    windows: Sequence[Mapping[str, Any]], *, max_chars: int = 8_000
) -> list[dict[str, Any]]:
    """Pack same-batch evidence windows into bounded profile requests with offset maps."""
    if max_chars < 1:
        raise ValueError("invalid_profile_packet_size")
    bundles: list[dict[str, Any]] = []
    current_text = ""
    current_segments: list[dict[str, Any]] = []
    current_batch_key = ""

    def flush() -> None:
        nonlocal current_text, current_segments, current_batch_key
        if current_segments:
            bundles.append(
                {
                    "text": current_text,
                    "source_batch_key": current_batch_key,
                    "segments": current_segments,
                }
            )
        current_text = ""
        current_segments = []
        current_batch_key = ""

    for window in windows:
        text = str(window.get("text") or "")
        if not text:
            continue
        batch_key = str(window.get("source_batch_key") or "")
        header = f"\n[Evidence passage {len(current_segments) + 1}]\n"
        if len(header) + len(text) > max_chars:
            raise ValueError("profile_evidence_window_exceeds_packet_size")
        if current_segments and (
            batch_key != current_batch_key
            or len(current_text) + len(header) + len(text) > max_chars
        ):
            flush()
            header = "\n[Evidence passage 1]\n"
        source_start = window.get("source_start")
        source_start = source_start if isinstance(source_start, int) and source_start >= 0 else 0
        joined_start = len(current_text) + len(header)
        current_text += header + text
        current_segments.append(
            {
                "joined_start": joined_start,
                "joined_end": joined_start + len(text),
                "source_start": source_start,
                "source_batch_key": batch_key,
            }
        )
        current_batch_key = batch_key
    flush()
    return bundles


def map_profile_citations_to_source(
    citations: Mapping[str, Any], segments: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Reject citations outside original evidence and restore batch-relative offsets."""
    mapped: dict[str, Any] = {}
    for field, value in citations.items():
        if not isinstance(value, dict):
            continue
        start = value.get("start")
        end = value.get("end")
        if isinstance(start, int) and isinstance(end, int):
            segment = next(
                (
                    item
                    for item in segments
                    if int(item["joined_start"]) <= start < end <= int(item["joined_end"])
                ),
                None,
            )
            if segment is None:
                raise ValueError("profile_citation_outside_source_passage")
            offset = int(segment["source_start"]) - int(segment["joined_start"])
            mapped[field] = {
                **value,
                "start": start + offset,
                "end": end + offset,
                "source_batch_key": segment["source_batch_key"],
            }
        else:
            mapped[field] = map_profile_citations_to_source(value, segments)
    return mapped


def shift_profile_citations(citations: Mapping[str, Any], source_start: int) -> dict[str, Any]:
    """Translate packet-relative quote offsets back into extraction-batch offsets."""
    shifted: dict[str, Any] = {}
    for field, value in citations.items():
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("start"), int) and isinstance(value.get("end"), int):
            shifted[field] = {
                **value,
                "start": value["start"] + source_start,
                "end": value["end"] + source_start,
            }
        else:
            shifted[field] = shift_profile_citations(value, source_start)
    return shifted


def source_quote_span(source_text: str, proposed_quote: object) -> tuple[int, int] | None:
    """Find a verbatim quote, allowing PDF line-break whitespace normalization only."""
    quote = str(proposed_quote or "").strip()
    if not source_text or len(quote) < 8 or len(quote) > 320:
        return None
    words = quote.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(word) for word in words)
    match = re.search(pattern, source_text)
    return (match.start(), match.end()) if match else None


def ground_character_profile_claims(
    raw: dict[str, Any],
    source_text: str,
    *,
    character_name: str | None = None,
    aliases: Sequence[str] = (),
    is_narrator: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only profile fields with a verifiable per-claim source quote."""
    citations = raw.get("claim_evidence")
    citations = citations if isinstance(citations, dict) else {}
    grounded: dict[str, Any] = {}
    verified: dict[str, Any] = {}

    def supported(span: tuple[int, int] | None) -> bool:
        return span is not None and (
            character_name is None
            or profile_quote_attributed_to_character(
                source_text,
                span,
                character_name=character_name,
                aliases=aliases,
                is_narrator=is_narrator,
            )
        )

    for field in PROFILE_SCALAR_FIELDS:
        value = raw.get(field)
        span = source_quote_span(source_text, citations.get(field))
        grounded[field] = (
            value if isinstance(value, str) and value.strip() and supported(span) else None
        )
        if grounded[field] is not None and span is not None:
            verified[field] = {
                "quote": source_text[span[0] : span[1]],
                "start": span[0],
                "end": span[1],
            }

    for field in PROFILE_LIST_FIELDS:
        values = raw.get(field)
        field_citations = citations.get(field)
        field_citations = field_citations if isinstance(field_citations, dict) else {}
        kept: list[str] = []
        field_verified: dict[str, Any] = {}
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, str) or not value.strip():
                continue
            span = source_quote_span(source_text, field_citations.get(value))
            if span is None or not supported(span):
                continue
            kept.append(value)
            field_verified[value] = {
                "quote": source_text[span[0] : span[1]],
                "start": span[0],
                "end": span[1],
            }
        grounded[field] = kept
        if field_verified:
            verified[field] = field_verified

    traits = raw.get("traits")
    traits = traits if isinstance(traits, dict) else {}
    trait_citations = citations.get("traits")
    trait_citations = trait_citations if isinstance(trait_citations, dict) else {}
    grounded_traits: dict[str, Any] = {}
    verified_traits: dict[str, Any] = {}
    for trait, data in traits.items():
        if not isinstance(data, dict) or not str(data.get("value") or "").strip():
            continue
        span = source_quote_span(source_text, trait_citations.get(trait))
        if span is None or not supported(span):
            continue
        grounded_traits[trait] = data
        verified_traits[trait] = {
            "quote": source_text[span[0] : span[1]],
            "start": span[0],
            "end": span[1],
        }
    grounded["traits"] = grounded_traits
    if verified_traits:
        verified["traits"] = verified_traits

    growth_event = raw.get("growth_event")
    growth_span = source_quote_span(source_text, citations.get("growth_event"))
    grounded["growth_event"] = (
        growth_event
        if isinstance(growth_event, dict) and growth_event.get("event") and supported(growth_span)
        else None
    )
    if grounded["growth_event"] is not None and growth_span is not None:
        verified["growth_event"] = {
            "quote": source_text[growth_span[0] : growth_span[1]],
            "start": growth_span[0],
            "end": growth_span[1],
        }
    return grounded, verified


def profile_claims_complete(raw: Mapping[str, Any], grounded: Mapping[str, Any]) -> bool:
    """Reject any proposed nonempty profile claim that lacked an exact source quote."""
    if not isinstance(raw.get("claim_evidence"), dict):
        return False
    for field in PROFILE_SCALAR_FIELDS:
        value = raw.get(field)
        if value is not None and not isinstance(value, str):
            return False
        if isinstance(value, str) and value.strip() and not grounded.get(field):
            return False
    for field in PROFILE_LIST_FIELDS:
        values = raw.get(field)
        if values is not None and not isinstance(values, list):
            return False
        if any(not isinstance(value, str) or not value.strip() for value in values or []):
            return False
        proposed = values or []
        if len(proposed) != len(grounded.get(field) or []):
            return False
    traits = raw.get("traits")
    if traits is not None and not isinstance(traits, dict):
        return False
    if any(
        not isinstance(data, dict)
        or (data.get("value") is not None and not isinstance(data.get("value"), str))
        for data in (traits or {}).values()
    ):
        return False
    proposed_traits = {
        key for key, data in (traits or {}).items() if str(data.get("value") or "").strip()
    }
    if proposed_traits != set(grounded.get("traits") or {}):
        return False
    growth = raw.get("growth_event")
    if growth is not None and not isinstance(growth, dict):
        return False
    if isinstance(growth, dict):
        if any(
            key in growth and growth[key] is not None and not isinstance(growth[key], str)
            for key in ("event", "impact", "tone")
        ):
            return False
        if (
            any(str(growth.get(key) or "").strip() for key in ("impact", "tone"))
            and not str(growth.get("event") or "").strip()
        ):
            return False
        if str(growth.get("event") or "").strip() and not grounded.get("growth_event"):
            return False
    return True


def merge_grounded_profile_claims(
    ranked: Sequence[Mapping[str, Any]], merged_traits: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Combine only cited claims across a name cluster, preserving each source batch."""
    updates: dict[str, Any] = {}
    citations: dict[str, Any] = {}

    def citation_for(item: Mapping[str, Any], field: str, value: str | None = None) -> Any:
        evidence = item.get("evidence")
        claims = evidence.get("profile_claims") if isinstance(evidence, dict) else None
        claim = claims.get(field) if isinstance(claims, dict) else None
        if value is not None:
            claim = claim.get(value) if isinstance(claim, dict) else None
        if not isinstance(claim, dict) or not claim.get("quote"):
            return None
        return {**claim, "source_batch_key": item.get("_source_batch_key")}

    for field in PROFILE_SCALAR_FIELDS:
        updates[field] = None
        for item in ranked:
            value = item.get(field)
            citation = citation_for(item, field)
            if isinstance(value, str) and value.strip() and citation:
                updates[field] = value
                citations[field] = citation
                break

    for field in PROFILE_LIST_FIELDS:
        values: list[str] = []
        field_citations: dict[str, Any] = {}
        seen: set[str] = set()
        for item in ranked:
            for value in item.get(field) if isinstance(item.get(field), list) else []:
                if not isinstance(value, str) or not value.strip():
                    continue
                citation = citation_for(item, field, value)
                key = value.casefold()
                if citation and key not in seen:
                    seen.add(key)
                    values.append(value)
                    field_citations[value] = citation
        updates[field] = values
        if field_citations:
            citations[field] = field_citations

    traits: dict[str, Any] = {}
    trait_citations: dict[str, Any] = {}
    for trait, data in merged_traits.items():
        if not isinstance(data, dict):
            continue
        for item in ranked:
            item_traits = item.get("traits")
            item_trait = item_traits.get(trait) if isinstance(item_traits, dict) else None
            citation = citation_for(item, "traits", trait)
            if (
                isinstance(item_trait, dict)
                and item_trait.get("value") == data.get("value")
                and citation
            ):
                traits[trait] = data
                trait_citations[trait] = citation
                break
    updates["traits"] = traits
    if trait_citations:
        citations["traits"] = trait_citations

    updates["growth_event"] = None
    for item in ranked:
        value = item.get("growth_event")
        citation = citation_for(item, "growth_event")
        if isinstance(value, dict) and value.get("event") and citation:
            updates["growth_event"] = value
            citations["growth_event"] = citation
            break
    return updates, citations


def profile_claim_records(
    extracted: Mapping[str, Any], *, chapter_number: int | None = None
) -> list[dict[str, Any]]:
    """Flatten cited claims into provenance records for the character profile."""
    evidence = extracted.get("evidence")
    claims = evidence.get("profile_claims") if isinstance(evidence, dict) else None
    if not isinstance(claims, dict):
        return []
    records: list[dict[str, Any]] = []

    def add(field: str, value: Any, citation: Any) -> None:
        if not isinstance(citation, dict) or not citation.get("quote") or not value:
            return
        cited_chapter = citation.get("chapter_number")
        if (
            not isinstance(cited_chapter, int)
            or isinstance(cited_chapter, bool)
            or cited_chapter < 1
        ):
            cited_chapter = chapter_number
        records.append(
            {
                "field": field,
                "value": str(value),
                "quote": str(citation["quote"]),
                "chapter_number": cited_chapter,
                "source_batch_key": citation.get("source_batch_key"),
                "start": citation.get("start"),
                "end": citation.get("end"),
            }
        )

    for field in PROFILE_SCALAR_FIELDS:
        add(field, extracted.get(field), claims.get(field))
    for field in PROFILE_LIST_FIELDS:
        field_citations = claims.get(field)
        if not isinstance(field_citations, dict):
            continue
        for value in extracted.get(field) if isinstance(extracted.get(field), list) else []:
            if isinstance(value, str):
                add(field, value, field_citations.get(value))
    trait_citations = claims.get("traits")
    traits = extracted.get("traits")
    if isinstance(trait_citations, dict) and isinstance(traits, dict):
        for trait, data in traits.items():
            if isinstance(data, dict):
                add(f"trait:{trait}", data.get("value"), trait_citations.get(trait))
    growth = extracted.get("growth_event")
    if isinstance(growth, dict):
        add("growth_event", growth.get("event"), claims.get("growth_event"))
    return records


def merge_profile_claim_records(
    existing: object, incoming: object, *, limit: int = 120
) -> list[dict[str, Any]]:
    """Retain prior citations and append distinct new ones without unbounded metadata."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in [
        *(existing if isinstance(existing, list) else []),
        *(incoming if isinstance(incoming, list) else []),
    ]:
        if not isinstance(record, dict):
            continue
        key = (
            record.get("field"),
            record.get("value"),
            record.get("quote"),
            record.get("source_batch_key"),
            record.get("chapter_number"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(record)
    return merged[-max(0, limit) :] if limit else []
