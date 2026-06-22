"""Audit and optionally clean obviously bogus character records.

Run in dry-run mode by default:
    python scripts/audit_character_bible_noise.py

To delete only the obvious noise records after review:
    python scripts/audit_character_bible_noise.py --apply-delete --confirm-delete DELETE_NOISE
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.engine.character.entity_filters import character_persistence_decision
from app.models.character import Character
from app.utils.characters.graph import get_graph_visibility_override
from app.utils.characters.identity import normalize_character_name
from app.utils.logging import get_logger

log = get_logger("lorevia.audit.character_bible_noise")
CONFIRM_DELETE_VALUE = "DELETE_NOISE"


@dataclass(frozen=True)
class CharacterNoiseFinding:
    character_id: str
    book_id: str
    name: str
    reasons: tuple[str, ...]
    mention_count: int
    relationship_count: int
    first_chapter: int
    last_seen_chapter: int | None
    is_manual: bool
    graph_override: str | None


def _relationship_count(character: Character) -> int:
    return len(character.relationships_as_a or []) + len(character.relationships_as_b or [])


def _has_meaningful_profile(character: Character) -> bool:
    return bool(
        (character.role and character.role.strip())
        or (character.aliases or [])
        or (character.personality_tags or [])
        or (character.motivations or [])
        or (character.fears or [])
        or (character.archetype and character.archetype.strip())
        or (character.arc_summary and character.arc_summary.strip())
        or (character.trait_state or {})
        or (character.goal and character.goal.strip())
        or (character.lie_they_believe and character.lie_they_believe.strip())
        or (character.backstory_wound and character.backstory_wound.strip())
        or (character.arc_type and character.arc_type.strip())
        or _relationship_count(character) > 0
    )


def _is_obvious_noise_character(character: Character) -> tuple[bool, tuple[str, ...]]:
    name = " ".join((character.name or "").split())
    if not name:
        return False, ("missing_name",)

    evidence = {
        "mention_count": int(character.mention_count or 0),
        "strong_mention_count": 0,
        "has_dialogue_or_action": False,
        "has_physical_description": bool(character.trait_state),
        "appears_multiple_times": int(character.mention_count or 0) >= 2,
    }
    decision = character_persistence_decision(
        name,
        role=character.role,
        aliases=character.aliases or [],
        personality_tags=character.personality_tags or [],
        motivations=character.motivations or [],
        fears=character.fears or [],
        archetype=character.archetype,
        trait_state=character.trait_state or {},
        relationship_count=_relationship_count(character),
        arc_summary=character.arc_summary,
        evidence=evidence,
        entity_type="person",
    )

    low_footprint = (
        int(character.mention_count or 0) <= 2
        and _relationship_count(character) == 0
        and not (character.states or [])
        and not getattr(character, "voice_profile", None)
        and not _has_meaningful_profile(character)
    )
    obvious_noise = (
        not getattr(character, "is_manual", False)
        and decision.allowed is False
        and low_footprint
        and len(normalize_character_name(name).split()) <= 2
    )
    reasons = decision.reasons or ("save_gate_rejected",)
    return obvious_noise, reasons


async def build_noise_report(book_id: uuid.UUID | None = None, db=None) -> dict:
    close_db = db is None
    if db is None:
        db = AsyncSessionLocal()
    try:
        stmt = (
            select(Character)
            .options(
                selectinload(Character.states),
                selectinload(Character.relationships_as_a),
                selectinload(Character.relationships_as_b),
                selectinload(Character.voice_profile),
            )
            .order_by(
                Character.book_id.asc(), Character.first_chapter.asc(), Character.created_at.asc()
            )
        )
        if book_id is not None:
            stmt = stmt.where(Character.book_id == book_id)

        characters = (await db.execute(stmt)).scalars().all()
        findings: list[CharacterNoiseFinding] = []
        for character in characters:
            is_noise, reasons = _is_obvious_noise_character(character)
            if not is_noise:
                continue
            findings.append(
                CharacterNoiseFinding(
                    character_id=str(character.id),
                    book_id=str(character.book_id),
                    name=character.name,
                    reasons=reasons,
                    mention_count=int(character.mention_count or 0),
                    relationship_count=_relationship_count(character),
                    first_chapter=int(character.first_chapter or 0),
                    last_seen_chapter=character.last_seen_chapter,
                    is_manual=bool(getattr(character, "is_manual", False)),
                    graph_override=get_graph_visibility_override(character),
                )
            )

        grouped: dict[str, list[dict]] = {}
        for finding in findings:
            grouped.setdefault(finding.book_id, []).append(asdict(finding))
        return {
            "total_characters": len(characters),
            "noise_count": len(findings),
            "books": grouped,
        }
    finally:
        if close_db:
            await db.close()


async def apply_noise_cleanup(book_id: uuid.UUID | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Character)
            .options(
                selectinload(Character.states),
                selectinload(Character.relationships_as_a),
                selectinload(Character.relationships_as_b),
                selectinload(Character.voice_profile),
            )
            .order_by(
                Character.book_id.asc(), Character.first_chapter.asc(), Character.created_at.asc()
            )
        )
        if book_id is not None:
            stmt = stmt.where(Character.book_id == book_id)

        characters = (await db.execute(stmt)).scalars().all()
        deleted: list[str] = []
        for character in characters:
            is_noise, _ = _is_obvious_noise_character(character)
            if not is_noise:
                continue
            await db.delete(character)
            deleted.append(str(character.id))

        await db.commit()
        return {"deleted_count": len(deleted), "deleted_character_ids": deleted}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and optionally clean noisy character records."
    )
    parser.add_argument(
        "--book-id", type=uuid.UUID, default=None, help="Limit the audit to a single book ID."
    )
    parser.add_argument(
        "--apply-delete", action="store_true", help="Delete obvious noise records after review."
    )
    parser.add_argument(
        "--confirm-delete",
        type=str,
        default="",
        help="Required confirmation token when --apply-delete is set.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    report = await build_noise_report(args.book_id)
    log.info("character_bible_noise_report %s", json.dumps(report, default=str))
    if not args.apply_delete:
        return
    if args.confirm_delete != CONFIRM_DELETE_VALUE:
        raise SystemExit(
            f"Refusing to delete without --confirm-delete {CONFIRM_DELETE_VALUE}. "
            "Run dry-run first and review the report."
        )
    cleanup = await apply_noise_cleanup(args.book_id)
    log.info("character_bible_noise_cleanup %s", json.dumps(cleanup, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
