"""Build cited character profiles after mention discovery and identity clustering."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import httpx
from fastapi import HTTPException
from openai import OpenAIError

from app.core.config import settings
from app.core.llm import complete_with_fallback
from app.engine.character.profile_builder import merge_trait_states
from app.utils.characters.profile_evidence import (
    bundle_profile_evidence_packets,
    ground_character_profile_claims,
    map_profile_citations_to_source,
    merge_grounded_profile_claims,
    profile_claims_complete,
    profile_evidence_packets,
    shift_profile_citations,
)
from app.utils.llm_usage_utils import (
    LLMIncompleteResponseError,
    is_transient_llm_provider_error,
    short_llm_coordination_retry_delay,
)

log = logging.getLogger(__name__)

PROFILE_SYSTEM = """Build a sparse, evidence-backed profile for ONE identified character.
The identity has already been resolved. Do not discover or merge characters here.
Use only the supplied source passage. Leave a field empty when it is not supported.
Every nonempty value, list item, trait, or growth event must have its own exact verbatim
source quote in claim_evidence. Do not use a name mention alone as evidence for a trait,
motivation, fear, or arc. Preserve observations separately from interpretations.
The source may contain other people: attribute facts only to the named character.
Return JSON only: {"profile":{"traits":{},"personality_tags":[],"goal":null,
"motivations":[],"fears":[],"lie_they_believe":null,"backstory_wound":null,
"arc_type":null,"arc_summary":null,"archetype":null,
"first_appearance_context":null,"growth_event":null,
"claim_evidence":{"traits":{},"personality_tags":{},"goal":null,
"motivations":{},"fears":{},"lie_they_believe":null,
"backstory_wound":null,"arc_type":null,"arc_summary":null,
"archetype":null,"first_appearance_context":null,"growth_event":null}}}.
Trait values use {"value":"...","confidence":0.0,"type":"objective|subjective|abstract"}.
If nothing about this person is supported beyond their name, return empty profile fields."""


class CharacterProfileFormatError(ValueError):
    """Profile output was incomplete or lacked verifiable source quotes."""


async def extract_profile_from_packet(
    *,
    character_name: str,
    aliases: list[str],
    packet: dict[str, Any],
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    language: str | None,
) -> dict[str, Any]:
    """Extract one sparse profile and reject unsupported or malformed claims."""
    source_text = str(packet["text"])
    prompt = (
        f"Character: {character_name}\n"
        f"Known aliases: {', '.join(aliases[:8]) or 'none'}\n"
        f"Source passage:\n{source_text}"
    )
    retry_instruction = ""
    for _attempt in range(2):
        try:
            raw = await complete_with_fallback(
                system=PROFILE_SYSTEM,
                user=prompt + retry_instruction,
                openai_model=settings.OPENAI_EXTRACT_MODEL,
                gemini_model=settings.GEMINI_EXTRACT_MODEL,
                temperature=0.1,
                max_tokens=1800,
                response_format={"type": "json_object"},
                require_complete_output=True,
                usage_feature="character_profile_enrichment",
                usage_user_id=user_id,
                usage_book_id=book_id,
                usage_db=None,
                language=language,
            )
        except LLMIncompleteResponseError:
            retry_instruction = (
                "\nValidation feedback: The previous answer was cut off. Return a shorter, "
                "complete profile JSON object with only source-backed claims."
            )
            continue
        except HTTPException as exc:
            delay = short_llm_coordination_retry_delay(exc)
            if _attempt or delay is None:
                raise
            await asyncio.sleep(delay)
            continue
        except (OpenAIError, httpx.HTTPError, TimeoutError) as exc:
            if _attempt or not is_transient_llm_provider_error(exc):
                raise
            await asyncio.sleep(0.25)
            continue
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            retry_instruction = (
                "\nValidation feedback: Return one complete JSON object with a profile object. "
                "Do not include markdown or commentary."
            )
            continue
        profile = parsed.get("profile") if isinstance(parsed, dict) else None
        if not isinstance(profile, dict):
            retry_instruction = (
                "\nValidation feedback: The response must contain a profile JSON object. "
                "Use empty fields when this passage provides no supported facts."
            )
            continue
        grounded, citations = ground_character_profile_claims(profile, source_text)
        if not profile_claims_complete(profile, grounded):
            retry_instruction = (
                "\nValidation feedback: At least one nonempty claim lacked a verbatim "
                "quote from the supplied source passage. Remove unsupported claims or "
                "provide an exact source quote for each claim."
            )
            continue
        try:
            mapped_citations = (
                map_profile_citations_to_source(citations, packet["segments"])
                if "segments" in packet
                else shift_profile_citations(citations, int(packet["source_start"]))
            )
        except ValueError:
            retry_instruction = (
                "\nValidation feedback: Every citation must come from a single original "
                "evidence passage, not from a generated header or across passages."
            )
            continue
        return {
            **grounded,
            "_source_batch_key": packet["source_batch_key"],
            "evidence": {"profile_claims": mapped_citations},
        }
    raise CharacterProfileFormatError("character_profile_invalid_or_unsupported_response")


async def enrich_chapter_character_profiles(
    entities: list[dict[str, Any]],
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    language: str | None,
) -> list[dict[str, Any]]:
    """Profile every discovered identity using all of its bounded chapter evidence windows."""
    if not entities:
        return []
    semaphore = asyncio.Semaphore(max(1, settings.LLM_MAX_CONCURRENT_CALLS_PER_USER))
    work: list[tuple[int, dict[str, Any]]] = []
    unanchored_indices: set[int] = set()
    for entity_index, entity in enumerate(entities):
        windows = profile_evidence_packets(entity)
        if not windows:
            unanchored_indices.add(entity_index)
            continue
        work.extend((entity_index, packet) for packet in bundle_profile_evidence_packets(windows))

    async def run(entity_index: int, packet: dict[str, Any]) -> dict[str, Any]:
        entity = entities[entity_index]
        async with semaphore:
            return await extract_profile_from_packet(
                character_name=str(entity["name"]),
                aliases=list(entity.get("aliases") or []),
                packet=packet,
                user_id=user_id,
                book_id=book_id,
                language=language,
            )

    results = await asyncio.gather(
        *(run(entity_index, packet) for entity_index, packet in work),
        return_exceptions=True,
    )
    profiles_by_entity: dict[int, list[dict[str, Any]]] = {}
    invalid_responses_by_entity: dict[int, int] = {}
    for (entity_index, _packet), result in zip(work, results, strict=True):
        if isinstance(result, CharacterProfileFormatError):
            invalid_responses_by_entity[entity_index] = (
                invalid_responses_by_entity.get(entity_index, 0) + 1
            )
            continue
        if isinstance(result, Exception):
            raise result
        profiles_by_entity.setdefault(entity_index, []).append(result)

    if invalid_responses_by_entity:
        log.warning(
            "character_profile_enrichment_partial book_id=%s invalid_response_batches=%s affected_characters=%s",
            book_id,
            sum(invalid_responses_by_entity.values()),
            len(invalid_responses_by_entity),
        )

    enriched: list[dict[str, Any]] = []
    for entity_index, entity in enumerate(entities):
        profiles = profiles_by_entity.get(entity_index, [])
        merged_traits: dict[str, Any] = {}
        for profile in profiles:
            merged_traits = merge_trait_states(merged_traits, profile["traits"])
        updates, citations = merge_grounded_profile_claims(profiles, merged_traits)
        evidence = dict(entity.get("evidence") or {})
        evidence["profile_claims"] = citations
        if entity_index in unanchored_indices:
            evidence["profile_enrichment_status"] = "unanchored_reference"
        elif invalid_responses_by_entity.get(entity_index):
            evidence["profile_enrichment_status"] = "partial_invalid_response"
            evidence["profile_enrichment_invalid_batches"] = invalid_responses_by_entity[
                entity_index
            ]
        else:
            evidence["profile_enrichment_status"] = "complete"
        enriched.append({**entity, **updates, "evidence": evidence})
    return enriched
