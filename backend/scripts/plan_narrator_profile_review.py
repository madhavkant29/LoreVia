"""Plan a capped, review-only profile pass for an author-confirmed narrator.

The default command is read only and prints no manuscript passages. Applying the
plan requires an exact generation and plan hash plus explicit narrator confirmation.
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
from app.models.character import Character
from app.models.generation import BookDataGeneration
from app.parsers.chunker import count_tokens
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.characters.narrator import first_person_profile_windows
from app.utils.characters.narrator_profile_review import (
    dedupe_narrator_profile_proposals,
    narrator_profile_proposals,
)
from app.utils.llm_pricing import calculate_llm_reservation_cost

MAX_CALLS = 6
MAX_PROMPT_TOKENS_PER_CALL = 1_600
MAX_OUTPUT_TOKENS_PER_CALL = 650
MAX_TOTAL_TOKENS = 12_000
MAX_COST_USD = Decimal("0.01")
APPLY_TOKEN = "CONFIRMED_NARRATOR_PROFILE_REVIEW_6_CALLS_0_01_USD"
REVIEW_SYSTEM = (
    "The author confirmed that the named character narrates the supplied passage "
    "in first person. Propose a sparse profile for this narrator. Use first-person "
    "narration, not another speaker's dialogue. Every nonempty trait, goal, "
    "motivation, fear, or personality tag needs its own exact source quote. "
    "Do not infer durable traits from a single temporary reaction. If uncertain, "
    "leave the field empty. Return only JSON: "
    '{"profile":{"goal":null,"motivations":[],"fears":[],"personality_tags":[],"traits":{},'
    '"claim_evidence":{"goal":null,"motivations":{},"fears":{},"personality_tags":{},"traits":{}}}}'
)


def review_prompt(name: str, chapter: int, passage: str) -> str:
    return json.dumps(
        {"character": name, "chapter": chapter, "source_passage": passage},
        ensure_ascii=False,
    )


def review_budget(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) > MAX_CALLS:
        raise ValueError("narrator_profile_call_limit_exceeded")
    prompt_tokens = 0
    for row in rows:
        estimated = count_tokens(REVIEW_SYSTEM + "\n" + row["prompt"]) + 128
        if estimated > MAX_PROMPT_TOKENS_PER_CALL:
            raise ValueError("narrator_profile_prompt_limit_exceeded")
        prompt_tokens += estimated
    output_tokens = len(rows) * MAX_OUTPUT_TOKENS_PER_CALL
    if prompt_tokens + output_tokens > MAX_TOTAL_TOKENS:
        raise ValueError("narrator_profile_token_limit_exceeded")
    _input, _output, cost, _version = calculate_llm_reservation_cost(
        settings.OPENAI_EXTRACT_MODEL,
        estimated_prompt_tokens=prompt_tokens,
        estimated_completion_tokens=output_tokens,
    )
    if cost > MAX_COST_USD:
        raise ValueError("narrator_profile_cost_limit_exceeded")
    return {
        "calls": len(rows),
        "estimated_prompt_tokens": prompt_tokens,
        "maximum_output_tokens": output_tokens,
        "estimated_total_tokens": prompt_tokens + output_tokens,
        "estimated_cost_usd": str(cost),
        "model": settings.OPENAI_EXTRACT_MODEL,
    }


async def build_plan(
    book_id: uuid.UUID, character_id: uuid.UUID, chapters: list[int]
) -> dict[str, Any]:
    if not chapters or len(chapters) > 3 or len(set(chapters)) != len(chapters):
        raise ValueError("narrator_profile_invalid_chapter_scope")
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        generation = (
            await db.execute(
                select(BookDataGeneration).where(
                    BookDataGeneration.book_id == book_id,
                    BookDataGeneration.status == "active",
                )
            )
        ).scalar_one()
        character = await db.get(Character, character_id)
        if (
            character is None
            or character.book_id != book_id
            or character.generation_id != generation.id
        ):
            raise ValueError("narrator_profile_character_not_in_active_generation")
        chapter_rows = (
            (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book_id, Chapter.number.in_(chapters))
                )
            )
            .scalars()
            .all()
        )
        if len(chapter_rows) != len(chapters):
            raise ValueError("narrator_profile_chapter_missing")
        name = character.name
        generation_id = generation.id
        keys = {chapter.number: chapter.s3_key for chapter in chapter_rows}
    rows: list[dict[str, Any]] = []
    source_hashes: dict[int, str] = {}
    for number in sorted(chapters):
        raw = await asyncio.to_thread(download_book, keys[number])
        source = str(deserialize_manuscript_content(raw).get("text") or "")
        source_hashes[number] = hashlib.sha256(source.encode("utf-8")).hexdigest()
        for start, end, passage in first_person_profile_windows(
            source, max_chars=1_600, max_windows=2
        ):
            rows.append(
                {
                    "chapter": number,
                    "start": start,
                    "end": end,
                    "passage": passage,
                    "prompt": review_prompt(name, number, passage),
                }
            )
    budget = review_budget(rows)
    fingerprint = {
        "book_id": str(book_id),
        "generation_id": str(generation_id),
        "character_id": str(character_id),
        "name": name,
        "source_hashes": source_hashes,
        "windows": [(row["chapter"], row["start"], row["end"]) for row in rows],
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "book_id": str(book_id),
        "character_id": str(character_id),
        "character_name": name,
        "active_generation_id": str(generation_id),
        "chapters": sorted(chapters),
        "source_windows": len(rows),
        "plan_sha256": plan_sha256,
        "budget": budget,
        "_rows": rows,
        "_source_keys": keys,
    }


async def apply_plan(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    chapters: list[int],
    *,
    expected_generation_id: uuid.UUID,
    expected_plan_sha256: str,
) -> dict[str, Any]:
    plan = await build_plan(book_id, character_id, chapters)
    if (
        plan["active_generation_id"] != str(expected_generation_id)
        or plan["plan_sha256"] != expected_plan_sha256
    ):
        raise ValueError("narrator_profile_plan_changed")
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        book = await db.get(Book, book_id)
        if book is None or book.mode != "author":
            raise ValueError("narrator_profile_author_book_required")
        user_id = book.user_id
    proposals: list[dict[str, Any]] = []
    for row in plan["_rows"]:
        raw = await complete_with_fallback(
            system=REVIEW_SYSTEM,
            user=row["prompt"],
            openai_model=settings.OPENAI_EXTRACT_MODEL,
            temperature=0.0,
            max_tokens=MAX_OUTPUT_TOKENS_PER_CALL,
            response_format={"type": "json_object"},
            require_complete_output=True,
            usage_feature="narrator_profile_review",
            usage_user_id=user_id,
            usage_book_id=book_id,
            usage_db=None,
        )
        proposals.extend(
            narrator_profile_proposals(
                raw,
                character_name=plan["character_name"],
                chapter_number=row["chapter"],
                window_start=row["start"],
                source_passage=row["passage"],
            )
        )
    # Recheck current source and generation after provider calls before writing.
    fresh = await build_plan(book_id, character_id, chapters)
    if fresh["plan_sha256"] != expected_plan_sha256:
        raise ValueError("narrator_profile_plan_changed_after_review")
    proposals = dedupe_narrator_profile_proposals(proposals)
    async with AsyncSessionLocal() as db:
        async with db.begin():
            generation = (
                await db.execute(
                    select(BookDataGeneration).where(
                        BookDataGeneration.book_id == book_id,
                        BookDataGeneration.status == "active",
                    )
                )
            ).scalar_one()
            character = await db.get(Character, character_id, with_for_update=True)
            if (
                generation.id != expected_generation_id
                or character is None
                or character.generation_id != generation.id
            ):
                raise ValueError("narrator_profile_generation_changed")
            metadata = dict(character.analysis_metadata or {})
            metadata["narrator_profile_review"] = {
                "plan_sha256": expected_plan_sha256,
                "generation_id": str(expected_generation_id),
                "chapters": sorted(chapters),
                "author_confirmed_identity": True,
                "chapter_s3_keys": {
                    str(number): key for number, key in plan["_source_keys"].items()
                },
                "proposals": proposals,
            }
            character.analysis_metadata = metadata
    await mark_book_cache_dirty(str(book_id))
    return {
        "active_generation_id": str(expected_generation_id),
        "character_name": plan["character_name"],
        "ai_calls": plan["budget"]["calls"],
        "source_checked_claims_for_review": len(proposals),
        "budget": plan["budget"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=uuid.UUID, required=True)
    parser.add_argument("--character-id", type=uuid.UUID, required=True)
    parser.add_argument("--chapters", type=int, nargs="+", required=True)
    parser.add_argument("--apply-with-ai", action="store_true")
    parser.add_argument("--expected-generation-id", type=uuid.UUID)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--confirm-narrator", default="")
    args = parser.parse_args()
    if args.apply_with_ai:
        if (
            args.expected_generation_id is None
            or not args.expected_plan_sha256
            or args.confirm_narrator != APPLY_TOKEN
        ):
            parser.error(
                "AI review requires the expected generation, plan hash, and "
                f"--confirm-narrator {APPLY_TOKEN}"
            )
        result = await apply_plan(
            args.book_id,
            args.character_id,
            args.chapters,
            expected_generation_id=args.expected_generation_id,
            expected_plan_sha256=args.expected_plan_sha256,
        )
    else:
        plan = await build_plan(args.book_id, args.character_id, args.chapters)
        result = {key: value for key, value in plan.items() if not key.startswith("_")}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
