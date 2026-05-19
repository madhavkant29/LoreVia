import uuid

from openai import AsyncOpenAI

from app.core.config import settings
from app.parsers.chunker import count_tokens
from app.utils.llm_usage_utils import create_tracked_embedding


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_EMBED_BATCH_TOKENS = 250000


async def embed_text(
    text: str,
    *,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    feature: str = "embedding",
) -> list[float]:
    client = get_client()
    try:
        r = await create_tracked_embedding(
            client=client,
            feature=feature,
            model=settings.OPENAI_EMBED_MODEL,
            user_id=user_id,
            book_id=book_id,
            input=text[:8000],
        )
        return r.data[0].embedding
    finally:
        await client.close()


async def embed_batch(
    texts: list[str],
    *,
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
                user_id=user_id,
                book_id=book_id,
                metadata={"batch_size": len(batch)},
                input=batch,
            )
            results.extend(item.embedding for item in sorted(r.data, key=lambda x: x.index))

        return results
    finally:
        await client.close()


async def embed_character(name: str, traits: dict) -> list[float]:
    parts = [f"Character: {name}"]
    for key in ["hair", "eyes", "build", "age", "face", "distinguishing"]:
        t = traits.get(key, {})
        if isinstance(t, dict) and t.get("value"):
            parts.append(f"{key}: {t['value']}")
        elif isinstance(t, str) and t:
            parts.append(f"{key}: {t}")
    return await embed_text(". ".join(parts), feature="character_embedding")
