import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.utils.character_utils import description_similarity, merge_characters, name_similarity, update_character_classification


async def consolidate_characters(
    db: AsyncSession,
    book_id: uuid.UUID,
    up_to_chapter: int | None = None,
) -> bool:
    query = select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.created_at)
    if up_to_chapter is not None:
        query = query.where(Character.first_chapter <= up_to_chapter)

    characters = list((await db.execute(query)).scalars().all())
    if len(characters) < 2:
        return False

    representatives: list[Character] = []
    merged_any = False

    for char in characters:
        primary = _find_primary_character(representatives, char)
        if primary is None:
            representatives.append(char)
            continue

        await merge_characters(db, primary.id, char.id, book_id)
        merged_any = True

    for char in representatives:
        update_character_classification(char)

    await db.commit()
    return merged_any


def _find_primary_character(representatives: list[Character], candidate: Character) -> Character | None:
    candidate_profile = _character_profile_text(candidate)
    best: tuple[float, Character] | None = None

    for existing in representatives:
        name_score = name_similarity(candidate.name, existing.name)
        if name_score < 0.70:
            continue

        description_score = description_similarity(candidate_profile, _character_profile_text(existing))
        if name_score >= 0.85 or description_score >= 0.75:
            score = (name_score + description_score) / 2
            if best is None or score > best[0]:
                best = (score, existing)

    return best[1] if best else None


def _character_profile_text(char: Character) -> str:
    pieces = [
        char.name,
        char.arc_summary,
        char.archetype,
        " ".join(char.personality_tags or []),
        " ".join(char.motivations or []),
        " ".join(char.fears or []),
    ]
    return " ".join(part.strip() for part in pieces if isinstance(part, str) and part.strip())
