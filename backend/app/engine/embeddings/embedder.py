from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def embed_text(text: str) -> list[float]:
    r = await client.embeddings.create(model=settings.OPENAI_EMBED_MODEL, input=text[:8000])
    return r.data[0].embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a single API call — much cheaper than one-by-one."""
    cleaned = [t[:8000] for t in texts]
    r = await client.embeddings.create(model=settings.OPENAI_EMBED_MODEL, input=cleaned)
    return [item.embedding for item in sorted(r.data, key=lambda x: x.index)]


async def embed_character(name: str, traits: dict) -> list[float]:
    parts = [f"Character: {name}"]
    for key in ["hair", "eyes", "build", "age", "face", "distinguishing"]:
        t = traits.get(key, {})
        if isinstance(t, dict) and t.get("value"):
            parts.append(f"{key}: {t['value']}")
        elif isinstance(t, str) and t:
            parts.append(f"{key}: {t}")
    return await embed_text(". ".join(parts))
