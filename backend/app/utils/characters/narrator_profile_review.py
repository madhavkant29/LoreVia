"""Source-checked, review-only profile proposals for a first-person narrator."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.models.character import Character
from app.utils.characters.narrator import (
    FIRST_PERSON_NARRATION_RE,
    first_person_narration_span,
)
from app.utils.characters.profile_evidence import (
    ground_character_profile_claims,
    merge_profile_claim_records,
    profile_claim_records,
)


def narrator_profile_proposals(
    response: str,
    *,
    character_name: str,
    chapter_number: int,
    window_start: int,
    source_passage: str,
) -> list[dict[str, Any]]:
    """Keep claims only when their quote is in the supplied narration passage."""
    try:
        parsed = json.loads(response)
    except (TypeError, ValueError):
        return []
    profile = parsed.get("profile") if isinstance(parsed, dict) else None
    if not isinstance(profile, dict):
        return []
    grounded, citations = ground_character_profile_claims(
        profile, source_passage, character_name=character_name, is_narrator=True
    )
    records = profile_claim_records(
        {**grounded, "evidence": {"profile_claims": citations}},
        chapter_number=chapter_number,
    )
    result: list[dict[str, Any]] = []
    for record in records:
        start = record.get("start")
        end = record.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if not FIRST_PERSON_NARRATION_RE.search(record["quote"]) or not first_person_narration_span(
            source_passage, (start, end)
        ):
            continue
        result.append(
            {
                "field": record["field"],
                "value": record["value"],
                "quote": record["quote"],
                "chapter_number": chapter_number,
                "source_start": window_start + start,
                "source_end": window_start + end,
            }
        )
    return result


def dedupe_narrator_profile_proposals(
    proposals: Sequence[dict[str, Any]], *, limit: int = 20
) -> list[dict[str, Any]]:
    """Avoid repeated claims from overlapping passages or chapters."""
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for proposal in proposals:
        key = (str(proposal.get("field") or ""), str(proposal.get("value") or "").casefold())
        if not all(key) or key in seen:
            continue
        seen.add(key)
        result.append(proposal)
        if len(result) >= limit:
            break
    return result


def accept_narrator_profile_proposal(character: Character, index: int) -> None:
    """Apply one author-reviewed, source-checked proposal to the current profile."""
    metadata = dict(character.analysis_metadata or {})
    review = dict(metadata.get("narrator_profile_review") or {})
    proposals = list(review.get("proposals") or [])
    if (
        not review.get("author_confirmed_identity")
        or str(character.generation_id) != review.get("generation_id")
        or index < 0
        or index >= len(proposals)
    ):
        raise ValueError("narrator_profile_review_unavailable")
    proposal = proposals[index]
    if not isinstance(proposal, dict) or proposal.get("status", "pending") != "pending":
        raise ValueError("narrator_profile_proposal_already_reviewed")
    field = str(proposal.get("field") or "")
    value = str(proposal.get("value") or "").strip()
    quote = str(proposal.get("quote") or "").strip()
    start = proposal.get("source_start")
    end = proposal.get("source_end")
    chapter = proposal.get("chapter_number")
    if (
        not value
        or not quote
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or not isinstance(chapter, int)
        or chapter < 1
    ):
        raise ValueError("narrator_profile_proposal_invalid")
    if field in {"personality_tags", "motivations", "fears"}:
        existing = list(getattr(character, field) or [])
        if value.casefold() not in {item.casefold() for item in existing}:
            existing.append(value)
        setattr(character, field, existing)
    elif field == "goal":
        if character.goal and character.goal != value:
            raise ValueError("narrator_profile_claim_conflicts_with_current_value")
        character.goal = value
    elif field.startswith("trait:") and field[6:].replace("_", "").isalnum():
        key = field[6:]
        traits = dict(character.trait_state or {})
        prior = traits.get(key)
        if isinstance(prior, dict) and prior.get("value") not in {None, value}:
            raise ValueError("narrator_profile_claim_conflicts_with_current_value")
        traits[key] = {"value": value, "confidence": 0.7, "type": "subjective"}
        character.trait_state = traits
    else:
        raise ValueError("narrator_profile_proposal_field_unsupported")
    proposals[index] = {**proposal, "status": "accepted"}
    review["proposals"] = proposals
    metadata["narrator_profile_review"] = review
    metadata["profile_claims"] = merge_profile_claim_records(
        metadata.get("profile_claims"),
        [
            {
                "field": field,
                "value": value,
                "quote": quote,
                "chapter_number": chapter,
                "start": start,
                "end": end,
                "source_batch_key": None,
            }
        ],
    )
    character.analysis_metadata = metadata
