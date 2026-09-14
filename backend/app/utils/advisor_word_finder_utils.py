from __future__ import annotations

import json
import re
import uuid

from openai import AsyncOpenAI

from app.utils.llm_usage_utils import create_tracked_chat_completion

WHATS_THE_WORD_SYSTEM = """\
You help fiction writers find one precise English word from a short description.

Return JSON only with this exact shape:
{
  "word": "single-word answer",
  "gloss": "brief explanation in under 16 words"
}

Rules:
- Return exactly one English word.
- Prefer precise, natural, contemporary vocabulary over obscure showboating.
- If a previous suggestion is provided, do not repeat it.
- Keep the gloss short, plain, and useful.
- Do not ask follow-up questions.
"""

WHATS_THE_WORD_USER = """\
Book: {title}
Description: {description}
Previous suggestion to avoid: {previous_word}
"""

_WHATS_THE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _normalize_single_word(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    if _WHATS_THE_WORD_RE.fullmatch(text):
        return text.lower()
    match = _WHATS_THE_WORD_RE.search(text)
    return match.group(0).lower() if match else ""


def normalize_whats_the_word_result(raw: str) -> dict[str, str]:
    fallback_word = _normalize_single_word(raw)
    fallback = {
        "word": fallback_word or "word",
        "gloss": "A close fit for the description.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return fallback

    word = _normalize_single_word(parsed.get("word")) if isinstance(parsed, dict) else ""
    if not word:
        return fallback

    gloss = " ".join(str((parsed or {}).get("gloss") or "").split()).strip()
    if not gloss:
        gloss = fallback["gloss"]
    return {"word": word, "gloss": gloss[:120]}


async def generate_whats_the_word_result(
    *,
    client: AsyncOpenAI,
    model: str,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    book_title: str,
    description: str,
    previous_word: str | None = None,
) -> dict[str, str]:
    response = await create_tracked_chat_completion(
        client=client,
        feature="advisor_whats_the_word",
        model=model,
        user_id=user_id,
        book_id=book_id,
        temperature=0.9,
        max_tokens=120,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": WHATS_THE_WORD_SYSTEM},
            {
                "role": "user",
                "content": WHATS_THE_WORD_USER.format(
                    title=book_title.strip() or "Untitled book",
                    description=description.strip(),
                    previous_word=(previous_word or "None").strip() or "None",
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or "{}"
    return normalize_whats_the_word_result(raw)
