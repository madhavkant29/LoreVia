import logging
import uuid

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_embedding_cache, set_embedding_cache
from app.parsers.chunker import count_tokens
from app.utils.llm_usage_utils import create_tracked_embedding

log = logging.getLogger("lorevia.embedder")


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_EMBED_BATCH_TOKENS = 250000


async def embed_text(
    text: str,
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    feature: str = "embedding",
) -> list[float]:
    normalized = (text or "")[:8000]

    cached = await get_embedding_cache(
        feature=feature,
        model=settings.OPENAI_EMBED_MODEL,
        text=normalized,
    )
    if cached is not None:
        return cached

    client = get_client()
    try:
        r = await create_tracked_embedding(
            client=client,
            feature=feature,
            model=settings.OPENAI_EMBED_MODEL,
            db=db,
            user_id=user_id,
            book_id=book_id,
            input=normalized,
        )
        result = r.data[0].embedding

        await set_embedding_cache(
            feature=feature,
            model=settings.OPENAI_EMBED_MODEL,
            text=normalized,
            vector=result,
        )
        return result
    finally:
        await client.close()


async def embed_batch(
    texts: list[str],
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    feature: str = "embedding_batch",
) -> list[list[float]]:
    """Embed multiple texts while staying under the provider token cap per request."""
    client = get_client()
    try:
        cleaned = [t[:8000] for t in texts]
        if not cleaned:
            return []

        results: list[list[float]] = []
        batch: list[str] = []
        batch_tokens = 0

        for text in cleaned:
            token_count = count_tokens(text)
            if batch and batch_tokens + token_count > MAX_EMBED_BATCH_TOKENS:
                r = await create_tracked_embedding(
                    client=client,
                    feature=feature,
                    model=settings.OPENAI_EMBED_MODEL,
                    db=db,
                    user_id=user_id,
                    book_id=book_id,
                    metadata={"batch_size": len(batch)},
                    input=batch,
                )
                results.extend(item.embedding for item in sorted(r.data, key=lambda x: x.index))
                batch = []
                batch_tokens = 0

            batch.append(text)
            batch_tokens += token_count

        if batch:
            r = await create_tracked_embedding(
                client=client,
                feature=feature,
                model=settings.OPENAI_EMBED_MODEL,
                db=db,
                user_id=user_id,
                book_id=book_id,
                metadata={"batch_size": len(batch)},
                input=batch,
            )
            results.extend(item.embedding for item in sorted(r.data, key=lambda x: x.index))

        return results
    finally:
        await client.close()


async def embed_character(
    name: str,
    traits: dict,
    *,
    db: AsyncSession | None = None,
) -> list[float]:
    return await embed_text(
        build_character_embedding_text(name=name, traits=traits),
        db=db,
        feature="character_embedding",
    )


def build_chunk_embedding_text(
    *,
    chapter_number: int | None,
    chapter_title: str | None,
    text: str,
) -> str:
    title = (chapter_title or "Untitled").strip() or "Untitled"
    chapter_label = f"Chapter {chapter_number}: {title}" if chapter_number is not None else f"Chapter: {title}"
    body = (text or "").strip()
    return f"{chapter_label}\n\n{body}" if body else chapter_label


def build_character_embedding_text(
    *,
    name: str,
    traits: dict | None,
    aliases: list[str] | None = None,
    role: str | None = None,
    arc_summary: str | None = None,
    evidence_snippets: list[str] | None = None,
) -> str:
    parts = [f"Character: {name}"]
    cleaned_aliases = [str(alias).strip() for alias in aliases or [] if str(alias).strip()]
    if cleaned_aliases:
        parts.append(f"Aliases: {', '.join(cleaned_aliases[:6])}")
    if role:
        parts.append(f"Role: {role}")
    for key in ["hair", "eyes", "build", "age", "face", "distinguishing"]:
        t = (traits or {}).get(key, {})
        if isinstance(t, dict) and t.get("value"):
            parts.append(f"{key}: {t['value']}")
        elif isinstance(t, str) and t:
            parts.append(f"{key}: {t}")
    if arc_summary:
        parts.append(f"Arc: {arc_summary}")
    for snippet in [str(item).strip() for item in (evidence_snippets or []) if str(item).strip()][:3]:
        parts.append(f"Evidence: {snippet[:220]}")
    return ". ".join(parts)
