"""Review generated relationship labels in one active book generation.

The default command is read-only and never prints manuscript text or quotes.
Apply requires the generation ID from a fresh dry run and an explicit token.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.storage import download_book
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.generation import BookDataGeneration
from app.models.intelligence import CharacterRelationship
from app.utils.characters.profile_evidence import source_quote_span
from app.utils.characters.relationship_evidence import relationship_quote_anchors_participants

CONFIRM_TOKEN = "REVIEW_UNANCHORED_RELATIONSHIPS"


async def build_plan(db: AsyncSession, book_id: uuid.UUID) -> dict[str, Any]:
    book = await db.get(Book, book_id)
    if book is None or book.status != "ready":
        raise ValueError("Book must be ready before relationship repair")
    generations = (
        (
            await db.execute(
                select(BookDataGeneration).where(
                    BookDataGeneration.book_id == book_id,
                    BookDataGeneration.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    if len(generations) != 1:
        raise ValueError("Expected exactly one active generation")
    generation = generations[0]
    characters = (
        (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    )
    names = {character.id: character.name for character in characters}
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == book_id,
                    CharacterRelationship.generation_id == generation.id,
                    CharacterRelationship.edited_by_author.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    chapters = (await db.execute(select(Chapter).where(Chapter.book_id == book_id))).scalars().all()
    source_keys = {chapter.number: chapter.s3_key for chapter in chapters}
    source_cache: dict[int, str] = {}
    review: list[dict[str, Any]] = []
    for relationship in relationships:
        left = names.get(relationship.character_a_id)
        right = names.get(relationship.character_b_id)
        if not left or not right:
            raise ValueError("Relationship endpoint is missing from the visible cast")
        evidence = relationship.label_evidence or {}
        quote = evidence.get("quote") if isinstance(evidence, dict) else None
        if not quote:
            reason = "relationship_source_quote_missing"
        else:
            chapter_number = relationship.from_chapter
            if chapter_number not in source_cache:
                source_key = source_keys.get(chapter_number)
                if not source_key:
                    raise ValueError(f"Saved source missing for chapter {chapter_number}")
                source_cache[chapter_number] = (
                    await asyncio.to_thread(download_book, source_key)
                ).decode("utf-8", "replace")
            if source_quote_span(source_cache[chapter_number], quote) is None:
                reason = "relationship_source_quote_unverified"
            elif not relationship_quote_anchors_participants(quote, left, right):
                reason = "relationship_participants_unanchored"
            else:
                continue
        review.append(
            {
                "relationship_id": str(relationship.id),
                "character_a": left,
                "character_b": right,
                "chapter": relationship.from_chapter,
                "type": relationship.rel_type,
                "reason": reason,
            }
        )
    return {
        "book_id": str(book_id),
        "active_generation_id": str(generation.id),
        "generated_relationships_checked": len(relationships),
        "review_count": len(review),
        "review": review,
    }


async def apply_plan(
    db: AsyncSession, *, book_id: uuid.UUID, expected_generation_id: uuid.UUID
) -> dict[str, Any]:
    generation = await db.get(BookDataGeneration, expected_generation_id, with_for_update=True)
    if generation is None or generation.status != "active":
        raise ValueError("Active generation changed during repair")
    plan = await build_plan(db, book_id)
    if plan["active_generation_id"] != str(expected_generation_id):
        raise ValueError("Active generation changed since dry run")
    for item in plan["review"]:
        relationship = await db.get(
            CharacterRelationship, uuid.UUID(item["relationship_id"]), with_for_update=True
        )
        if (
            relationship is None
            or relationship.generation_id != expected_generation_id
            or relationship.edited_by_author
        ):
            raise ValueError("Relationship changed during repair")
        evidence = dict(relationship.label_evidence or {})
        db.add(
            CharacterRelationshipCandidate(
                book_id=book_id,
                generation_id=expected_generation_id,
                chapter_number=relationship.from_chapter,
                raw_character_a=item["character_a"],
                raw_character_b=item["character_b"],
                matched_character_a_id=relationship.character_a_id,
                matched_character_b_id=relationship.character_b_id,
                rel_type=relationship.rel_type,
                sentiment=relationship.sentiment,
                description=relationship.description,
                status="pending",
                reason_codes=[item["reason"], "generated_relationship_requires_review"],
                evidence={
                    "relationship": {"label_evidence": evidence},
                    "source_quote_verified": item["reason"]
                    == "relationship_participants_unanchored",
                    "relationship_participants_anchored": False,
                    "repaired_relationship_id": item["relationship_id"],
                },
                source_batch_key=f"relationship-repair:{item['relationship_id']}",
            )
        )
        await db.delete(relationship)
    await db.flush()
    return {**plan, "applied": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=uuid.UUID, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-generation-id", type=uuid.UUID)
    parser.add_argument("--confirm-apply", default="")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.apply and (args.confirm_apply != CONFIRM_TOKEN or args.expected_generation_id is None):
        raise SystemExit(
            "Apply requires --expected-generation-id and --confirm-apply " + CONFIRM_TOKEN
        )
    async with AsyncSessionLocal() as db:
        if args.apply:
            async with db.begin():
                result = await apply_plan(
                    db, book_id=args.book_id, expected_generation_id=args.expected_generation_id
                )
        else:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            result = await build_plan(db, args.book_id)
            result["applied"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
