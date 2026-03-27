"""
Prediction engine - RAG over book chunks + GPT-4o reasoning.
Phase 3 feature.
"""
import json
import uuid

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.search.semantic import semantic_search

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PREDICT_SYSTEM = """You are analysing a novel. The user asks a prediction question.
Based ONLY on the evidence provided (story context up to the current chapter),
generate 2-3 theories.

Return JSON only:
{
  "theories": [
    {
      "theory": "concise statement",
      "confidence": 0.0-1.0,
      "evidence": ["quote or event from the text"],
      "reasoning": "1-2 sentences"
    }
  ]
}

Be specific. Cite evidence from the provided context. Do not invent facts.
Do not spoil anything past the current chapter."""


async def predict(
    db: AsyncSession,
    book_id: uuid.UUID,
    question: str,
    current_chapter: int,
) -> list[dict]:
    context_chunks = await semantic_search(db, book_id, question, current_chapter, limit=10)
    context = "\n\n".join(c["text"] for c in context_chunks)

    r = await client.chat.completions.create(
        model=settings.OPENAI_INTEL_MODEL,
        messages=[
            {"role": "system", "content": PREDICT_SYSTEM},
            {
                "role": "user",
                "content": f"Question: {question}\n\nStory context:\n{context}",
            },
        ],
        temperature=0.3,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(r.choices[0].message.content)
        return data.get("theories", [])
    except Exception:
        return []
