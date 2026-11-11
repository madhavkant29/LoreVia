"""Read-only, source-neutral budget plan for one active generation's relationship review.

This command makes no provider calls or database changes. It never prints passages.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.llm import complete_with_fallback
from app.core.redis import mark_book_cache_dirty
from app.core.storage import download_book
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship
from app.parsers.chunker import count_tokens
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.characters.relationship_repair import (
    relationship_evidence_windows,
    verified_relationship_evidence_proposal,
)
from app.utils.llm_pricing import calculate_llm_reservation_cost
from scripts.review_unanchored_relationships import apply_plan, build_plan

MAX_CALLS = 12
MAX_PROMPT_TOKENS_PER_CALL = 2_200
MAX_OUTPUT_TOKENS_PER_CALL = 300
MAX_TOTAL_TOKENS = 30_000
MAX_COST_USD = Decimal("0.02")
APPLY_TOKEN = "REVIEW_RELATIONSHIP_EVIDENCE_12_CALLS_0_02_USD"

REVIEW_SYSTEM = (
    "Review only the named pair in the supplied manuscript passages. "
    "Treat the existing label as an unverified hypothesis. Do not infer a tie "
    "from co-occurrence alone. Return JSON with supported (boolean), "
    "relationship_type (short snake_case label), and quote (exact contiguous "
    "source words, at most 320 characters). If the passage does not establish "
    "the label, return supported false and no quote."
)


def review_prompt(
    left: str, right: str, current_label: str, windows: list[tuple[int, int, str]]
) -> str:
    return json.dumps(
        {
            "character_a": left,
            "character_b": right,
            "unverified_existing_label": current_label,
            "source_passages": [text for _start, _end, text in windows],
        },
        ensure_ascii=False,
    )


def review_budget(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject an oversized plan before any potential provider call."""
    if len(rows) > MAX_CALLS:
        raise ValueError("relationship_review_call_limit_exceeded")
    prompt_tokens = 0
    for row in rows:
        estimated = count_tokens(REVIEW_SYSTEM + "\n" + row["prompt"]) + 128
        if estimated > MAX_PROMPT_TOKENS_PER_CALL:
            raise ValueError("relationship_review_prompt_limit_exceeded")
        prompt_tokens += estimated
    output_tokens = len(rows) * MAX_OUTPUT_TOKENS_PER_CALL
    if prompt_tokens + output_tokens > MAX_TOTAL_TOKENS:
        raise ValueError("relationship_review_token_limit_exceeded")
    _input_cost, _output_cost, cost, _version = calculate_llm_reservation_cost(
        settings.OPENAI_EXTRACT_MODEL,
        estimated_prompt_tokens=prompt_tokens,
        estimated_completion_tokens=output_tokens,
    )
    if cost > MAX_COST_USD:
        raise ValueError("relationship_review_cost_limit_exceeded")
    return {
        "calls": len(rows),
        "max_prompt_tokens": prompt_tokens,
        "max_output_tokens": output_tokens,
        "max_total_tokens": prompt_tokens + output_tokens,
        "max_cost_usd": str(cost),
        "model": settings.OPENAI_EXTRACT_MODEL,
    }


def evidence_plan_hash(
    repair_plan_sha256: str,
    sources: dict[int, str],
    eligible: list[dict[str, Any]],
) -> str:
    """Bind an AI plan to exact chapter content and selected prompts."""
    return hashlib.sha256(
        json.dumps(
            {
                "repair_plan_sha256": repair_plan_sha256,
                "source_hashes": {
                    number: hashlib.sha256(source.encode("utf-8")).hexdigest()
                    for number, source in sources.items()
                },
                "eligible": [(row["relationship_id"], row["prompt"]) for row in eligible],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


async def build_evidence_review_plan(db: Any, book_id: uuid.UUID) -> dict[str, Any]:
    repair = await build_plan(db, book_id)
    characters = (
        (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    )
    names = {item.id: item for item in characters}
    chapters = (await db.execute(select(Chapter).where(Chapter.book_id == book_id))).scalars().all()
    keys = {item.number: item.s3_key for item in chapters}
    review_ids = {item["relationship_id"] for item in repair["review"]}
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == book_id,
                    CharacterRelationship.generation_id
                    == uuid.UUID(repair["active_generation_id"]),
                    CharacterRelationship.edited_by_author.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    # Release the read transaction before downloading source passages.
    await db.commit()
    sources: dict[int, str] = {}
    eligible: list[dict[str, Any]] = []
    for relationship in sorted(relationships, key=lambda item: str(item.id)):
        if str(relationship.id) not in review_ids:
            continue
        left = names[relationship.character_a_id]
        right = names[relationship.character_b_id]
        chapter = relationship.from_chapter
        if chapter not in sources:
            raw = await asyncio.to_thread(download_book, keys[chapter])
            sources[chapter] = str(deserialize_manuscript_content(raw).get("text") or "")
        evidence = relationship.label_evidence or {}
        quote = evidence.get("quote") if isinstance(evidence, dict) else None
        windows = relationship_evidence_windows(
            sources[chapter],
            [left.name, *(left.aliases or [])],
            [right.name, *(right.aliases or [])],
            preferred_quote=quote,
        )
        if not windows:
            continue
        eligible.append(
            {
                "relationship_id": str(relationship.id),
                "character_a": left.name,
                "character_b": right.name,
                "chapter": chapter,
                "prompt": review_prompt(left.name, right.name, relationship.rel_type, windows),
                "windows": windows,
            }
        )
    budget = review_budget(eligible)
    evidence_plan_sha256 = evidence_plan_hash(repair["plan_sha256"], sources, eligible)
    return {
        "book_id": str(book_id),
        "active_generation_id": repair["active_generation_id"],
        "repair_plan_sha256": repair["plan_sha256"],
        "evidence_plan_sha256": evidence_plan_sha256,
        "relationships_for_review": repair["review_count"],
        "eligible_for_ai_review": len(eligible),
        "skipped_without_ai": repair["review_count"] - len(eligible),
        "budget": budget,
        "eligible_pairs": [
            {
                "character_a": row["character_a"],
                "character_b": row["character_b"],
                "chapter": row["chapter"],
            }
            for row in eligible
        ],
        "_eligible": eligible,
    }


async def apply_evidence_review_plan(
    *,
    book_id: uuid.UUID,
    expected_generation_id: uuid.UUID,
    expected_plan_sha256: str,
) -> dict[str, Any]:
    """Make capped tracked calls, then atomically move all unsupported ties to review."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        plan = await build_evidence_review_plan(db, book_id)
        book = await db.get(Book, book_id)
        if book is None or book.mode != "author":
            raise ValueError("relationship_review_author_book_required")
        user_id = book.user_id
    if (
        plan["active_generation_id"] != str(expected_generation_id)
        or plan["evidence_plan_sha256"] != expected_plan_sha256
    ):
        raise ValueError("relationship_review_plan_changed")

    proposals: dict[str, dict[str, Any]] = {}
    for row in plan["_eligible"]:
        raw = await complete_with_fallback(
            system=REVIEW_SYSTEM,
            user=row["prompt"],
            openai_model=settings.OPENAI_EXTRACT_MODEL,
            temperature=0.0,
            max_tokens=MAX_OUTPUT_TOKENS_PER_CALL,
            response_format={"type": "json_object"},
            require_complete_output=True,
            retry_transient_openai=False,
            usage_feature="character_relationship_evidence_repair",
            usage_user_id=user_id,
            usage_book_id=book_id,
            usage_db=None,
        )
        proposal = verified_relationship_evidence_proposal(
            raw,
            windows=row["windows"],
            left_name=row["character_a"],
            right_name=row["character_b"],
        )
        if proposal is not None:
            proposals[row["relationship_id"]] = proposal

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        fresh_plan = await build_evidence_review_plan(db, book_id)
    if fresh_plan["evidence_plan_sha256"] != expected_plan_sha256:
        raise ValueError("relationship_review_plan_changed_after_ai")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            applied = await apply_plan(
                db,
                book_id=book_id,
                expected_generation_id=expected_generation_id,
                expected_plan_sha256=plan["repair_plan_sha256"],
            )
            candidates = (
                (
                    await db.execute(
                        select(CharacterRelationshipCandidate).where(
                            CharacterRelationshipCandidate.book_id == book_id,
                            CharacterRelationshipCandidate.generation_id == expected_generation_id,
                            CharacterRelationshipCandidate.source_batch_key.like(
                                "relationship-repair:%"
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for candidate in candidates:
                evidence = dict(candidate.evidence or {})
                relationship = dict(evidence.get("relationship") or {})
                prior_id = str(evidence.get("repaired_relationship_id") or "")
                proposal = proposals.get(prior_id)
                if proposal is None:
                    continue
                relationship["review_proposal"] = proposal
                evidence["relationship"] = relationship
                candidate.evidence = evidence
                candidate.reason_codes = [
                    *(candidate.reason_codes or []),
                    "ai_evidence_proposal_needs_review",
                ]
        if applied["review_count"]:
            await mark_book_cache_dirty(str(book_id))
    return {
        "active_generation_id": str(expected_generation_id),
        "relationships_queued_for_review": applied["review_count"],
        "ai_calls": plan["budget"]["calls"],
        "source_verified_proposals": len(proposals),
        "participant_anchored_proposals": sum(
            bool(item["participants_anchored"]) for item in proposals.values()
        ),
        "budget": plan["budget"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=uuid.UUID, required=True)
    parser.add_argument("--apply-with-ai", action="store_true")
    parser.add_argument("--expected-generation-id", type=uuid.UUID)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--confirm-apply", default="")
    args = parser.parse_args()
    if args.apply_with_ai:
        if (
            args.expected_generation_id is None
            or not args.expected_plan_sha256
            or args.confirm_apply != APPLY_TOKEN
        ):
            parser.error(
                "AI review requires --expected-generation-id, --expected-plan-sha256, "
                f"and --confirm-apply {APPLY_TOKEN}"
            )
        result = await apply_evidence_review_plan(
            book_id=args.book_id,
            expected_generation_id=args.expected_generation_id,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    else:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            result = await build_evidence_review_plan(db, args.book_id)
        result.pop("_eligible")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
