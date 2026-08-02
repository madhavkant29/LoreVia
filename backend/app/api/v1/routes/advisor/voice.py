from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_continuity_checker
from app.api.v1.routes.advisor.chat import (
    _advisor_sse,
    _advisor_stream_response,
    _safe_prompt_str,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_voice_consistency_cache, set_voice_consistency_cache
from app.engine.search.semantic import semantic_search
from app.models.book import Book
from app.models.character import Character, CharacterVoiceProfile
from app.schemas.advisor import VoiceConsistencyRequest
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.advisor_utils import (
    VOICE_CONSISTENCY_SYSTEM,
    VOICE_CONSISTENCY_USER,
    build_character_voice_context,
    build_story_context,
    identify_character_mentions,
    make_editorial_cache_key,
    normalize_voice_consistency_result,
)
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    score_voice_match,
)
from app.utils.llm_usage_utils import create_tracked_chat_completion
from app.utils.logging.errors import public_error_message
from app.utils.retry_utils import LLM_MAX_RETRIES

router = APIRouter()


@router.post("/{book_id}/advisor/voice-consistency")
async def voice_consistency_review(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    cache_key = make_editorial_cache_key(book_id, body.text, body.chapter_num, body.character_id)
    cached = await get_voice_consistency_cache(str(book.id), cache_key)
    if cached is not None:
        return {
            **cached,
            "warnings": list(cached.get("warnings") or []),
            "cached": True,
        }

    total_ch = book.total_chapters or 9999
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=LLM_MAX_RETRIES)

    try:
        hits = await semantic_search(
            db,
            book_id,
            body.text[:600],
            total_ch,
            limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            candidate_limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            similarity_threshold=settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
            usage_user_id=current_user.id,
            usage_feature="advisor_voice_consistency_search",
        )
        passages_block = (
            "\n\n".join(
                f"Ch. {h['chapter_num']} - {h.get('chapter_title') or 'Untitled'}:\n{h['text'][:320]}"
                for h in hits
            )
            or "No closely matching passages found."
        )

        story_ctx = await build_story_context(db, book_id, total_ch)
        character_rows = (
            (
                await db.execute(
                    select(
                        Character.id,
                        Character.name,
                        Character.aliases,
                        Character.role,
                        Character.first_chapter,
                        Character.arc_summary,
                        Character.personality_tags,
                        Character.motivations,
                        Character.fears,
                        Character.trait_state,
                    )
                    .where(Character.book_id == book_id)
                    .order_by(
                        Character.mention_count.desc(), Character.first_chapter, Character.name
                    )
                )
            )
            .mappings()
            .all()
        )
        character_payloads = [dict(row) for row in character_rows]
        selected_character = None
        if body.character_id is not None:
            selected_character = next(
                (row for row in character_payloads if str(row["id"]) == str(body.character_id)),
                None,
            )
            if selected_character is None:
                raise HTTPException(400, detail="Selected character does not belong to this book.")
            relevant_characters = [selected_character]
        else:
            relevant_characters = identify_character_mentions(body.text, character_payloads)
        all_voice_profiles = (
            (
                await db.execute(
                    select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book_id)
                )
            )
            .scalars()
            .all()
        )
        profiles_by_character_id = {profile.character_id: profile for profile in all_voice_profiles}
        attributed_dialogue = extract_dialogue_samples_by_character(body.text, character_payloads)
        warnings: list[str] = []
        if len(relevant_characters) == 1 and not attributed_dialogue.get(
            relevant_characters[0]["name"]
        ):
            attributed_dialogue[relevant_characters[0]["name"]] = [body.text[:4000]]
            if body.character_id is not None:
                warnings.append(
                    f"Dialogue could not be confidently attributed to {relevant_characters[0]['name']}; "
                    "the review used the full submitted passage instead."
                )
        character_context = build_character_voice_context(relevant_characters)
        chapter_hint = (
            f"This passage will appear in Chapter {body.chapter_num}."
            if body.chapter_num
            else "Chapter number not specified."
        )

        system_msg = VOICE_CONSISTENCY_SYSTEM.format(
            title=_safe_prompt_str(book.title),
            story_context=_safe_prompt_str(story_ctx),
        )
        user_msg = VOICE_CONSISTENCY_USER.format(
            chapter_hint=chapter_hint,
            character_context=character_context,
            passages=passages_block,
            text=body.text[:4000],
        )

        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_voice_consistency",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.2,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        result = normalize_voice_consistency_result(raw)
        character_matches: list[dict[str, Any]] = []
        for character in relevant_characters:
            char_id = character.get("id")
            char_name = character.get("name")
            profile = profiles_by_character_id.get(uuid.UUID(str(char_id))) if char_id else None
            samples = attributed_dialogue.get(str(char_name), [])
            sample_metrics = compute_voice_metrics(samples)
            profile_payload = {
                "sample_dialogue_count": profile.sample_dialogue_count if profile else 0,
                "sample_word_count": profile.sample_word_count if profile else 0,
                "avg_sentence_length": profile.avg_sentence_length if profile else 0,
                "avg_word_length_x100": profile.avg_word_length_x100 if profile else 0,
                "contraction_rate_x1000": profile.contraction_rate_x1000 if profile else 0,
                "question_rate_x1000": profile.question_rate_x1000 if profile else 0,
                "exclamation_rate_x1000": profile.exclamation_rate_x1000 if profile else 0,
                "ellipsis_rate_x1000": profile.ellipsis_rate_x1000 if profile else 0,
                "dash_rate_x1000": profile.dash_rate_x1000 if profile else 0,
                "uppercase_rate_x1000": profile.uppercase_rate_x1000 if profile else 0,
                "formality_score_x1000": profile.formality_score_x1000 if profile else 0,
                "lexical_complexity_x1000": profile.lexical_complexity_x1000 if profile else 0,
                "emotional_intensity_x1000": profile.emotional_intensity_x1000 if profile else 0,
            }
            score, signals = score_voice_match(profile_payload, sample_metrics)
            closest_other_character = None
            closest_other_score = -1
            character_uuid = uuid.UUID(str(char_id)) if char_id else None
            for candidate_profile in all_voice_profiles:
                if character_uuid is not None and candidate_profile.character_id == character_uuid:
                    continue
                candidate_score, _ = score_voice_match(
                    {
                        "sample_dialogue_count": candidate_profile.sample_dialogue_count,
                        "sample_word_count": candidate_profile.sample_word_count,
                        "avg_sentence_length": candidate_profile.avg_sentence_length,
                        "avg_word_length_x100": candidate_profile.avg_word_length_x100,
                        "contraction_rate_x1000": candidate_profile.contraction_rate_x1000,
                        "question_rate_x1000": candidate_profile.question_rate_x1000,
                        "exclamation_rate_x1000": candidate_profile.exclamation_rate_x1000,
                        "ellipsis_rate_x1000": candidate_profile.ellipsis_rate_x1000,
                        "dash_rate_x1000": candidate_profile.dash_rate_x1000,
                        "uppercase_rate_x1000": candidate_profile.uppercase_rate_x1000,
                        "formality_score_x1000": candidate_profile.formality_score_x1000,
                        "lexical_complexity_x1000": candidate_profile.lexical_complexity_x1000,
                        "emotional_intensity_x1000": candidate_profile.emotional_intensity_x1000,
                    },
                    sample_metrics,
                )
                if candidate_score > closest_other_score:
                    closest_other_score = candidate_score
                    closest_other_character = next(
                        (
                            row["name"]
                            for row in character_rows
                            if str(row["id"]) == str(candidate_profile.character_id)
                        ),
                        None,
                    )
            character_matches.append(
                {
                    "character_name": char_name,
                    "match_score": score,
                    "baseline_sample_size": int(profile.sample_dialogue_count if profile else 0),
                    "sample_dialogue_count": int(sample_metrics.get("sample_dialogue_count") or 0),
                    "strongest_signals": signals,
                    "closest_other_character": closest_other_character,
                    "closest_other_score": closest_other_score
                    if closest_other_score >= 0
                    else None,
                }
            )

        response_payload = {
            "review": result,
            "retrieved_passages": [
                {
                    "chapter_num": h["chapter_num"],
                    "chapter_title": h.get("chapter_title"),
                    "chunk_index": h.get("chunk_index"),
                    "excerpt": h["text"][:220],
                    "relevance": round(h.get("score", 0.0), 3),
                }
                for h in hits[:4]
            ],
            "characters_reviewed": [character["name"] for character in relevant_characters],
            "character_matches": character_matches,
            "warnings": warnings,
        }
        response_payload["cached"] = False
        await set_voice_consistency_cache(str(book.id), cache_key, response_payload)
        return response_payload
    finally:
        await client.close()


@router.post("/{book_id}/advisor/voice-consistency-stream")
async def voice_consistency_review_stream(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Comparing the passage to voice baselines..."})
            payload = await voice_consistency_review(
                book_id=book_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())
