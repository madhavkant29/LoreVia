"""Character entity clustering, mention recording, and roster resolution."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.character.entity_filters import entity_words
from app.engine.character.profile_builder import merge_list_values, merge_trait_states
from app.models.character import Character, CharacterMention
from app.utils.characters.constants import ROLE_ONLY_REFERENCE_WORDS
from app.utils.characters.identity import (
    _leading_title,
    family_role_reference,
    filter_character_identity_aliases,
    is_role_only_character_name,
    normalize_character_name,
    partition_identity_key,
)
from app.utils.characters.text import _clean_reason_codes, clean_optional_text, clean_string_list


def build_character_mention_cluster_key(
    name: str | None, aliases: Sequence[str] | None = None
) -> str:
    parts = [
        normalize_character_name(name),
        *(normalize_character_name(alias) for alias in aliases or []),
    ]
    parts = sorted({part for part in parts if part})
    if not parts:
        return ""
    return parts[0]


def _context_links_family_role_to_name(role_name: str, proper_name: str, text: str) -> bool:
    anchor, role = family_role_reference(role_name)
    normalized_proper = normalize_character_name(proper_name)
    if not anchor or not role or not normalized_proper or not text:
        return False
    anchor_phrase = rf"\b{re.escape(anchor)}(?:'s|\u2019s) {re.escape(role)}\b"
    proper_phrase = rf"\b{re.escape(normalized_proper)}\b"
    patterns = (
        rf"{anchor_phrase}[^.?!\n]{{0,80}}{proper_phrase}",
        rf"{proper_phrase}[^.?!\n]{{0,80}}{anchor_phrase}",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _entity_display_name(entity: Mapping[str, Any]) -> str:
    return " ".join(str(entity.get("name") or "").split()).strip()


def _entity_source_text(entity: Mapping[str, Any]) -> str:
    return " ".join(str(entity.get("_source_text") or "").split()).strip()


def _entity_aliases(entity: Mapping[str, Any]) -> list[str]:
    return clean_string_list(
        entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
    )


def _mention_entity_evidence(entity: Mapping[str, Any]) -> dict[str, Any]:
    evidence = entity.get("evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def _entity_mentions_linked_in_text(left_name: str, right_name: str, text: str) -> bool:
    if not left_name or not right_name or not text:
        return False

    left_anchor, left_role = family_role_reference(left_name)
    right_anchor, right_role = family_role_reference(right_name)
    normalized_left = normalize_character_name(left_name)
    normalized_right = normalize_character_name(right_name)

    def _phrase(name: str, role: str | None) -> str:
        return role or normalize_character_name(name)

    left_phrase = _phrase(
        left_name,
        left_role
        if left_role
        else ("chief clerk" if normalized_left.endswith("chief clerk") else None),
    )
    right_phrase = _phrase(
        right_name,
        right_role
        if right_role
        else ("chief clerk" if normalized_right.endswith("chief clerk") else None),
    )
    escaped_left = re.escape(left_phrase)
    escaped_right = re.escape(right_phrase)
    if not escaped_left or not escaped_right:
        return False

    patterns = (
        rf"\b{escaped_left}\b[^.?!\n]{{0,80}}\b{escaped_right}\b",
        rf"\b{escaped_right}\b[^.?!\n]{{0,80}}\b{escaped_left}\b",
    )
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    if left_role and left_anchor:
        anchor_patterns = (
            rf"\b{re.escape(left_anchor)}['\u2019]s {re.escape(left_role)}\b[^.?!\n]{{0,80}}\b{re.escape(normalized_right)}\b",
            rf"\b{re.escape(normalized_right)}\b[^.?!\n]{{0,80}}\b{re.escape(left_anchor)}['\u2019]s {re.escape(left_role)}\b",
        )
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in anchor_patterns):
            return True
    if right_role and right_anchor:
        anchor_patterns = (
            rf"\b{re.escape(right_anchor)}['\u2019]s {re.escape(right_role)}\b[^.?!\n]{{0,80}}\b{re.escape(normalized_left)}\b",
            rf"\b{re.escape(normalized_left)}\b[^.?!\n]{{0,80}}\b{re.escape(right_anchor)}['\u2019]s {re.escape(right_role)}\b",
        )
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in anchor_patterns):
            return True

    return False


def _character_entity_matches_cluster(
    candidate: Mapping[str, Any], cluster: Mapping[str, Any]
) -> bool:
    from app.engine.character.deduplicator import names_equivalent

    candidate_name = _entity_display_name(candidate)
    cluster_name = _entity_display_name(cluster)
    candidate_aliases = _entity_aliases(candidate)
    cluster_aliases = _entity_aliases(cluster)
    if not candidate_name or not cluster_name:
        return False
    candidate_title = _leading_title(candidate_name)
    cluster_title = _leading_title(cluster_name)
    if (candidate_title or cluster_title) and partition_identity_key(
        candidate_name
    ) != partition_identity_key(cluster_name):
        return False
    candidate_family_role = family_role_reference(candidate_name)[1]
    cluster_family_role = family_role_reference(cluster_name)[1]
    if candidate_family_role or cluster_family_role:
        return normalize_character_name(candidate_name) == normalize_character_name(cluster_name)
    if is_role_only_character_name(candidate_name) or is_role_only_character_name(cluster_name):
        return normalize_character_name(candidate_name) == normalize_character_name(cluster_name)
    if names_equivalent(candidate_name, candidate_aliases, cluster_name, cluster_aliases):
        return True

    source_text = " ".join(
        filter(None, [_entity_source_text(candidate), _entity_source_text(cluster)])
    )
    if _context_links_family_role_to_name(candidate_name, cluster_name, source_text):
        return True
    if _context_links_family_role_to_name(cluster_name, candidate_name, source_text):
        return True

    candidate_keys = {
        build_character_mention_cluster_key(candidate_name, candidate_aliases),
        *(normalize_character_name(alias) for alias in candidate_aliases),
    }
    cluster_keys = {
        build_character_mention_cluster_key(cluster_name, cluster_aliases),
        *(normalize_character_name(alias) for alias in cluster_aliases),
    }
    candidate_keys.discard("")
    cluster_keys.discard("")
    return bool(candidate_keys & cluster_keys)


def _cluster_verifier_summary(cluster: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    verdicts: list[str] = []
    reasons: list[str] = []
    local_totals = {
        "mention_count": 0,
        "person_context_mentions": 0,
        "mid_sentence_mentions": 0,
        "sentence_start_mentions": 0,
        "subject_action_mentions": 0,
        "person_ner_mentions": 0,
        "non_person_ner_mentions": 0,
        "interjection_like_mentions": 0,
    }
    local_windows: list[dict[str, Any]] = []
    for item in cluster:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        verifier = evidence.get("verifier") if isinstance(evidence, dict) else {}
        local = verifier.get("local") if isinstance(verifier, dict) else {}
        final = verifier.get("final") if isinstance(verifier, dict) else {}
        if isinstance(local, dict):
            for field in local_totals:
                local_totals[field] += int(local.get(field) or 0)
            for window in local.get("windows") or []:
                if isinstance(window, dict):
                    local_windows.append(dict(window))
        if not isinstance(final, dict):
            continue
        verdict = str(final.get("confidence_band") or "").strip()
        if verdict:
            verdicts.append(verdict)
        for reason in final.get("reasons") or []:
            cleaned = str(reason or "").strip()
            if cleaned and cleaned not in reasons:
                reasons.append(cleaned)
    if not verdicts:
        return None
    unique = set(verdicts)
    if unique == {"accept"}:
        band = "accept"
        is_person_like = True
    elif unique == {"reject"}:
        band = "reject"
        is_person_like = False
    else:
        band = "review"
        is_person_like = False
    return {
        "local": {
            **local_totals,
            "windows": local_windows[:8],
        },
        "local_summary": {
            "member_verdicts": verdicts,
        },
        "llm": {"used": any("llm_" in reason for reason in reasons)},
        "final": {
            "confidence_band": band,
            "is_person_like": is_person_like,
            "reasons": reasons,
        },
    }


def cluster_character_entities(entities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []
    for raw in entities:
        entity = dict(raw)
        if not _entity_display_name(entity):
            continue
        matched_cluster: list[dict[str, Any]] | None = None
        for cluster in clusters:
            if any(_character_entity_matches_cluster(entity, member) for member in cluster):
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append([entity])
            continue
        matched_cluster.append(entity)

    aggregated: list[dict[str, Any]] = []
    for cluster in clusters:

        def _family_role_like_display(display_name: str) -> bool:
            _family_anchor, family_role = family_role_reference(display_name)
            return bool(
                family_role
                or re.search(
                    r"(?:'s|\u2019s|\bs\b)\s+(?:aunt|brother|father|mother|sister|uncle)\b",
                    display_name.casefold(),
                )
            )

        def _cluster_primary_rank(item: Mapping[str, Any]) -> tuple[int, int, int, int, float]:
            display_name = _entity_display_name(item)
            family_role_like = _family_role_like_display(display_name)
            proper_name = not is_role_only_character_name(display_name) and not family_role_like
            return (
                1 if proper_name else 0,
                int(len(entity_words(display_name)) >= 2 and not family_role_like),
                int(_mention_entity_evidence(item).get("strong_mention_count") or 0),
                int(_mention_entity_evidence(item).get("mention_count") or 0),
                float(item.get("confidence") or 0.0),
            )

        ranked = sorted(
            cluster,
            key=_cluster_primary_rank,
            reverse=True,
        )
        primary = dict(ranked[0])
        if _family_role_like_display(_entity_display_name(primary)):
            proper_ranked = [
                item
                for item in ranked
                if not _family_role_like_display(_entity_display_name(item))
                and not is_role_only_character_name(_entity_display_name(item))
            ]
            if proper_ranked:
                primary = dict(proper_ranked[0])
        cluster_names = clean_string_list([_entity_display_name(item) for item in cluster])
        cluster_aliases = merge_list_values(
            *(
                item.get("aliases") if isinstance(item.get("aliases"), list) else []
                for item in cluster
            )
        )
        merged_traits: dict[str, Any] = {}
        evidence = dict(_mention_entity_evidence(primary))
        passages: list[str] = []
        total_mentions = 0
        strong_mentions = 0
        for item in cluster:
            merged_traits = merge_trait_states(
                merged_traits, item.get("traits") if isinstance(item.get("traits"), dict) else {}
            )
            item_evidence = _mention_entity_evidence(item)
            total_mentions += int(item_evidence.get("mention_count") or 0)
            strong_mentions += int(item_evidence.get("strong_mention_count") or 0)
            passages.extend(
                clean_string_list(
                    item_evidence.get("snippets")
                    if isinstance(item_evidence.get("snippets"), list)
                    else []
                )
            )

        primary["aliases"] = filter_character_identity_aliases(
            primary.get("name"),
            merge_list_values(cluster_aliases, cluster_names),
        )
        primary["traits"] = merged_traits
        primary["confidence"] = max(float(item.get("confidence") or 0.0) for item in cluster)
        evidence.update(
            {
                "mention_count": total_mentions or int(evidence.get("mention_count") or 0),
                "strong_mention_count": strong_mentions
                or int(evidence.get("strong_mention_count") or 0),
                "cluster_size": len(cluster),
                "cluster_mention_count": total_mentions or int(evidence.get("mention_count") or 0),
                "cluster_names": cluster_names,
                "resolver_status": "clustered" if len(cluster) > 1 else "single",
                "snippets": clean_string_list(passages)[:6],
            }
        )
        verifier_summary = _cluster_verifier_summary(cluster)
        if verifier_summary is not None:
            evidence["verifier"] = verifier_summary
        primary["evidence"] = evidence
        primary["resolver_status"] = str(evidence.get("resolver_status") or "single")
        primary["canonical_confidence"] = max(
            float(primary.get("confidence") or 0.0),
            min(0.99, 0.35 + (0.1 * len(cluster)) + (0.08 * min(strong_mentions, 4))),
        )
        primary["cluster_members"] = [
            {
                "name": _entity_display_name(item),
                "aliases": _entity_aliases(item),
                "source_batch_key": item.get("_source_batch_key"),
                "source_text": _entity_source_text(item),
                "evidence": _mention_entity_evidence(item),
            }
            for item in cluster
        ]
        aggregated.append(primary)

    return aggregated


async def record_character_mention(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    raw_name: str,
    normalized_name: str,
    source_batch_key: str | None = None,
    cluster_key: str | None = None,
    mention_text: str | None = None,
    matched_character_id: uuid.UUID | None = None,
    resolver_status: str = "unresolved",
    resolver_reasons: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> CharacterMention:
    cleaned_mention_text = clean_optional_text(mention_text)
    stmt = select(CharacterMention).where(
        CharacterMention.book_id == book_id,
        CharacterMention.chapter_number == chapter_number,
        CharacterMention.normalized_name == normalized_name,
        CharacterMention.source_batch_key == source_batch_key,
        CharacterMention.cluster_key == cluster_key,
        CharacterMention.mention_text == cleaned_mention_text,
    )
    mention = (await db.execute(stmt)).scalar_one_or_none()
    if mention is None:
        mention = CharacterMention(
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            normalized_name=normalized_name,
            source_batch_key=source_batch_key,
            cluster_key=cluster_key,
        )
        db.add(mention)
    mention.raw_name = clean_optional_text(raw_name) or raw_name
    mention.normalized_name = normalized_name
    mention.source_batch_key = source_batch_key
    mention.cluster_key = cluster_key
    mention.mention_text = cleaned_mention_text
    mention.matched_character_id = matched_character_id
    mention.resolver_status = clean_optional_text(resolver_status) or "unresolved"
    mention.resolver_reasons = _clean_reason_codes(resolver_reasons)
    merged_evidence = dict(mention.evidence or {})
    if evidence:
        merged_evidence.update(dict(evidence))
    mention.evidence = merged_evidence
    await db.flush()
    return mention


def resolve_character_reference_from_roster(
    characters: Sequence[Character],
    raw_name: str | None,
    *,
    context_text: str | None = None,
) -> Character | None:
    from app.engine.character.deduplicator import names_equivalent

    candidate_name = " ".join(str(raw_name or "").split()).strip()
    if not candidate_name:
        return None

    scored: list[tuple[int, Character]] = []
    normalized_candidate = normalize_character_name(candidate_name)
    candidate_anchor, candidate_role = family_role_reference(candidate_name)
    for character in characters:
        aliases = clean_string_list(character.aliases or [])
        score = 0
        if not candidate_role:
            if names_equivalent(candidate_name, [], character.name, aliases):
                score += 90
            elif normalized_candidate == normalize_character_name(character.name):
                score += 85
            elif normalized_candidate and normalized_candidate in {
                normalize_character_name(alias) for alias in aliases
            }:
                score += 82

        joined_names = [character.name, *aliases]
        if context_text and any(
            _entity_mentions_linked_in_text(candidate_name, value, context_text)
            for value in joined_names
            if value
        ):
            score += 24
        if context_text and any(
            _context_links_family_role_to_name(candidate_name, value, context_text)
            or _context_links_family_role_to_name(value, candidate_name, context_text)
            for value in joined_names
            if value
        ):
            score += 72

        if (
            candidate_anchor
            and candidate_role
            and normalize_character_name(character.name) == candidate_anchor
        ):
            score -= 32

        if is_role_only_character_name(candidate_name) and not is_role_only_character_name(
            character.name
        ):
            score -= 12

        if score > 0:
            scored.append((score, character))

    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], int(item[1].mention_count or 0)), reverse=True)
    best_score, best_character = scored[0]
    if best_score < 60:
        return None
    if len(scored) > 1 and scored[1][0] >= best_score - 8:
        return None
    return best_character
