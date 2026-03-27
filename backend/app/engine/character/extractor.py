"""
LLM character + relationship extraction with confidence-weighted traits.
Single LLM pass extracts both — cheaper and gives shared context.
"""
import json
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHARACTER_SYSTEM = """You are a character and relationship extraction engine.

Extract ALL named characters from the text chunk and ALL relationships between them.

TRAIT CONFIDENCE RULES:
- Explicit direct description → 0.85–1.0
- Implied/inferred → 0.5–0.7
- Narrator self-opinion ("plain", "ugly") → cap at 0.35, type="subjective"
- Single mention → max 0.6; repeated → boost toward 1.0

Return ONLY valid JSON, no markdown, no commentary:
{
  "characters": [
    {
      "name": "primary name",
      "aliases": ["other names"],
      "traits": {
        "hair":   {"value": "...", "confidence": 0.0, "type": "objective|subjective|abstract"},
        "eyes":   {"value": "...", "confidence": 0.0, "type": "..."},
        "build":  {"value": "...", "confidence": 0.0, "type": "..."},
        "age":    {"value": "teen|young adult|adult|middle-aged|elderly", "confidence": 0.0, "type": "..."},
        "face":   {"value": "...", "confidence": 0.0, "type": "..."},
        "distinguishing": {"value": "...", "confidence": 0.0, "type": "..."}
      },
      "personality_tags": ["max 3"],
      "motivations": ["what drives them"],
      "fears": ["what they fear"],
      "archetype": "japanese high school boy|mentor|trickster|villain|hero|etc",
      "first_appearance_context": "1 sentence"
    }
  ],
  "relationships": [
    {
      "character_a": "name",
      "character_b": "name",
      "type": "ally|enemy|romantic|family|political|mentor|rival|neutral",
      "sentiment": 0.0,
      "description": "one sentence"
    }
  ]
}

If nothing found, return {"characters": [], "relationships": []}.
Omit null trait fields entirely."""


async def extract_characters_and_relationships(chunk_text: str) -> dict:
    response = await client.chat.completions.create(
        model=settings.OPENAI_EXTRACT_MODEL,
        messages=[
            {"role": "system", "content": CHARACTER_SYSTEM},
            {"role": "user", "content": chunk_text[:4000]},
        ],
        temperature=0.1,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
        return {
            "characters": parsed.get("characters", []),
            "relationships": parsed.get("relationships", []),
        }
    except json.JSONDecodeError:
        return {"characters": [], "relationships": []}
