from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import get_openai_client
from app.core.redis import get_voice_consistency_cache, set_voice_consistency_cache
from app.models.book import Book
from app.schemas.advisor import VoiceConsistencyRequest
from app.services.voice_consistency_review_service import (
    VoiceBaselineSourceError,
    load_voice_baseline_samples,
    load_voice_review_characters,
    personalize_voice_review_payload,
    review_voice_sections,
)
from app.utils.advisor_prompt_utils import safe_prompt_str
from app.utils.advisor_utils import (
    VOICE_CONSISTENCY_SYSTEM,
    VOICE_CONSISTENCY_USER,
    build_story_context,
    identify_character_mentions,
)
from app.utils.characters.narrator import (
    contextual_first_person_narrators,
    detect_explicit_first_person_narrator,
    explicit_first_person_narrators,
)
from app.utils.intelligence_utils import compute_voice_metrics, score_voice_match
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
    is_transient_llm_provider_error,
    require_complete_llm_response,
)
from app.utils.voice_review_coverage import (
    aggregate_voice_review_coverage,
    complete_cached_voice_review,
    unattributed_quoted_ranges,
)
from app.utils.voice_review_utils import (
    VOICE_CURRENT_SAMPLE_MINIMUMS,
    VoiceReviewFormatError,
    attributed_voice_samples,
    closest_alternate_voice_match,
    disambiguate_voice_aliases,
    first_person_narration_samples,
    grounded_voice_profile_claims,
    make_voice_review_cache_key,
    voice_baseline_size,
    voice_baseline_style_summary,
    voice_baseline_sufficient,
    voice_current_sample_sufficient,
    voice_independent_source_texts,
    voice_review_character_context,
    voice_review_context_signature,
    voice_samples_have_reliable_attribution,
    voice_source_anchors_for_section,
)


async def run_voice_consistency_review(
    *,
    db: AsyncSession,
    book: Book,
    body: VoiceConsistencyRequest,
    current_user: Any,
    cache_version: int,
    billing_user: Any | None = None,
    allowed_chapter_range: tuple[int | None, int | None] | None = None,
) -> dict[str, Any]:
    """Build an evidence-backed review without holding a transaction through model calls."""
    book_id = book.id
    billing_user_id = (billing_user or current_user).id
    total_ch = int(book.total_chapters or 0)

    try:
        story_ctx = await build_story_context(db, book_id, total_ch)
        character_payloads = disambiguate_voice_aliases(
            await load_voice_review_characters(db, book_id=book_id)
        )
        explicit_narrators = (
            explicit_first_person_narrators(body.text, character_payloads)
            if body.voice_mode == "first_person_narration"
            else []
        )
        dialogue_narrator = (
            detect_explicit_first_person_narrator(body.text, character_payloads)
            if body.voice_mode == "dialogue"
            else None
        )
        contextual_narrators = (
            contextual_first_person_narrators(body.text, character_payloads)
            if body.voice_mode == "first_person_narration" and not explicit_narrators
            else []
        )
        narrator_identity_conflict = body.character_id is not None and any(
            str(character["id"]) != str(body.character_id) for character in explicit_narrators
        )
        selected_character = None
        if body.character_id is not None:
            selected_character = next(
                (row for row in character_payloads if str(row["id"]) == str(body.character_id)),
                None,
            )
            if selected_character is None:
                raise HTTPException(400, detail="Selected character does not belong to this book.")
            relevant_characters = [selected_character]
            detected_characters = relevant_characters
        elif body.voice_mode == "first_person_narration":
            narrator = detect_explicit_first_person_narrator(body.text, character_payloads)
            if narrator is None and len(contextual_narrators) == 1:
                narrator = contextual_narrators[0]
            detected_characters = [narrator] if narrator is not None else []
            relevant_characters = detected_characters
        else:
            detected_characters = identify_character_mentions(
                body.text, character_payloads, limit=len(character_payloads)
            )
            relevant_characters = detected_characters[:5]
        skipped_characters = detected_characters[len(relevant_characters) :]
        warnings: list[str] = []
        if narrator_identity_conflict:
            warnings.append(
                "This passage explicitly identifies more than one first-person narrator. "
                "Select a single-POV passage before reviewing this character."
                if len(explicit_narrators) > 1
                else "This passage explicitly identifies a different first-person narrator "
                "than the selected character. Select the correct narrator or passage."
            )
        if body.voice_mode == "first_person_narration" and not relevant_characters:
            warnings.append(
                "The passage does not unambiguously identify its first-person narrator. "
                "Select the narrator to review this voice; no identity was guessed."
            )
        elif (
            body.voice_mode == "first_person_narration"
            and body.character_id is None
            and not explicit_narrators
            and len(contextual_narrators) == 1
        ):
            warnings.append(
                "Narrator identity is inferred only from direct address and a nearby first-person "
                "response. This is tentative, not proof; no confident verdict or match score is shown."
            )
        if skipped_characters:
            warnings.append(
                "This passage mentions more than five known characters. "
                "The following characters were not reviewed: "
                + ", ".join(str(item["name"]) for item in skipped_characters)
                + ". Select one to review it separately."
            )
        baseline_by_name: dict[str, list[dict[str, Any]]] = {}
        current_by_name: dict[str, list[dict[str, Any]]] = {}
        source_cache: dict[str, str] = {}
        eligible_characters: list[dict[str, Any]] = []
        for character in relevant_characters:
            name = str(character["name"])
            aliases = list(character.get("aliases") or [])
            baseline = await load_voice_baseline_samples(
                db,
                book_id=book_id,
                character_name=name,
                aliases=aliases,
                submitted_text=body.text,
                submitted_chapter=body.chapter_num,
                voice_mode=body.voice_mode,
                source_cache=source_cache,
                known_character_names=[str(item["name"]) for item in character_payloads],
                allowed_chapter_range=allowed_chapter_range,
            )
            current = (
                first_person_narration_samples(
                    body.text,
                    chapter_number=body.chapter_num or 0,
                    include_offsets=True,
                )
                if body.voice_mode == "first_person_narration"
                else attributed_voice_samples(
                    body.text,
                    character_name=name,
                    aliases=aliases,
                    chapter_number=body.chapter_num or 0,
                    include_offsets=True,
                    first_person_speaker=(dialogue_narrator is character),
                )
            )
            if (
                body.voice_mode == "first_person_narration"
                and body.character_id is None
                and not explicit_narrators
                and len(contextual_narrators) == 1
            ):
                for sample in current:
                    sample["attribution_confidence"] = "contextual"
            baseline_by_name[name] = baseline
            current_by_name[name] = current
            if any(item.get("attribution_confidence") == "contextual" for item in baseline):
                warnings.append(
                    (
                        f"{name}: some first-person baseline prose is only linked by a "
                        "direct address followed by a narrator response. "
                        if body.voice_mode == "first_person_narration"
                        else f"{name}: some baseline dialogue was linked through a nearby pronoun. "
                    )
                    + "The comparison is tentative, and no numeric voice match is shown."
                )
            if any(
                item.get("attribution_confidence") == "unverified_narrator" for item in baseline
            ):
                warnings.append(
                    f"{name}: some first-person baseline chapters do not independently identify "
                    "this narrator. Findings are tentative, and no numeric voice match is shown."
                )
            if any(item.get("attribution_confidence") == "contextual" for item in current):
                warnings.append(
                    (
                        f"{name}: first-person narration is only tentatively linked by direct address. "
                        if body.voice_mode == "first_person_narration"
                        else f"{name}: some dialogue was linked through a nearby pronoun. "
                    )
                    + "This is not definitive speaker evidence. No numeric voice match is shown."
                )
            minimum_words = 120 if body.voice_mode == "first_person_narration" else 60
            evidence_label = (
                "first-person narrative"
                if body.voice_mode == "first_person_narration"
                else "attributed dialogue"
            )
            if not voice_baseline_sufficient(baseline, min_words=minimum_words):
                excerpts, words = voice_baseline_size(baseline)
                warnings.append(
                    f"{name}: only {excerpts} {evidence_label} baseline excerpts ({words} words) "
                    f"outside this passage; at least 3 excerpts and {minimum_words} words are required."
                )
            elif narrator_identity_conflict:
                warnings.append(
                    f"{name}: narrator attribution is contradictory in this passage; "
                    "no voice verdict was made."
                )
            elif not current:
                warnings.append(
                    f"{name}: no {evidence_label} in this passage could be confidently identified; "
                    "no voice verdict was made for this character."
                )
            else:
                eligible_characters.append(character)
                if not voice_current_sample_sufficient(current, voice_mode=body.voice_mode):
                    source_count, word_count = voice_baseline_size(current)
                    minimum_sources, minimum_words = VOICE_CURRENT_SAMPLE_MINIMUMS[body.voice_mode]
                    warnings.append(
                        f"{name}: this passage has only {source_count} independent "
                        f"{evidence_label} excerpts ({word_count} words); "
                        f"at least {minimum_sources} excerpts and {minimum_words} words "
                        "are needed for a reliable voice match. Findings remain tentative."
                    )

        baseline_evidence = [
            {
                "character_name": name,
                "sample_count": voice_baseline_size(samples)[0],
                "word_count": voice_baseline_size(samples)[1],
                "chapters": sorted({item["chapter_number"] for item in samples}),
                "baseline_attribution_confidence": (
                    "unattributed"
                    if not samples
                    else (
                        "explicit"
                        if body.voice_mode == "first_person_narration"
                        and voice_samples_have_reliable_attribution(samples)
                        else (
                            (
                                "contextual"
                                if all(
                                    item.get("attribution_confidence") in {"explicit", "contextual"}
                                    for item in samples
                                )
                                else "unverified_narrator"
                            )
                            if body.voice_mode == "first_person_narration"
                            else (
                                "contextual"
                                if not voice_samples_have_reliable_attribution(samples)
                                else "explicit"
                            )
                        )
                    )
                ),
                "attribution_confidence": (
                    (
                        "user_selected_narrator"
                        if body.character_id is not None
                        else (
                            "contextual"
                            if any(
                                item.get("attribution_confidence") == "contextual"
                                for item in current_by_name[name]
                            )
                            else "explicit"
                        )
                    )
                    if body.voice_mode == "first_person_narration" and current_by_name[name]
                    else (
                        "contextual"
                        if any(
                            item.get("attribution_confidence") == "contextual"
                            for item in current_by_name[name]
                        )
                        else "explicit"
                        if current_by_name[name]
                        else "unattributed"
                    )
                ),
            }
            for name, samples in baseline_by_name.items()
        ]

        # No scored result or successful empty review without independent evidence.
        if not eligible_characters:
            evidence_kind = (
                "established first-person narration"
                if body.voice_mode == "first_person_narration"
                else "independently attributed dialogue"
            )
            return {
                "review": {
                    "status": "insufficient_evidence",
                    "issues": [],
                    "overall_verdict": (
                        f"There is not enough {evidence_kind} to judge character voice yet."
                    ),
                },
                "retrieved_passages": [],
                "voice_mode": body.voice_mode,
                "characters_reviewed": [],
                "characters_detected": [character["name"] for character in detected_characters],
                "character_matches": [],
                "baseline_evidence": baseline_evidence,
                "warnings": warnings
                or ["No character could be confidently resolved in this passage."],
                "coverage": aggregate_voice_review_coverage([], total_characters=len(body.text)),
                "coverage_by_character": [],
                "cached": False,
            }

        comparison_characters: list[dict[str, Any]] = []
        comparison_baselines = dict(baseline_by_name)
        if body.voice_mode == "dialogue" and any(
            voice_samples_have_reliable_attribution(current_by_name[str(character["name"])])
            and voice_current_sample_sufficient(
                current_by_name[str(character["name"])], voice_mode="dialogue"
            )
            for character in eligible_characters
        ):
            comparison_candidates = [
                character
                for character in character_payloads
                if str(character["name"]) not in comparison_baselines
            ]
            comparison_characters = comparison_candidates[:8]
            if len(comparison_candidates) > len(comparison_characters):
                warnings.append(
                    "Alternate voice similarity was checked against only the eight "
                    "most-mentioned other characters; it is not a complete cast comparison."
                )
            for character in comparison_characters:
                name = str(character["name"])
                comparison_baselines[name] = await load_voice_baseline_samples(
                    db,
                    book_id=book_id,
                    character_name=name,
                    aliases=list(character.get("aliases") or []),
                    submitted_text=body.text,
                    submitted_chapter=body.chapter_num,
                    voice_mode="dialogue",
                    source_cache=source_cache,
                    allowed_chapter_range=allowed_chapter_range,
                )

        baseline_signature = voice_review_context_signature(
            story_context=story_ctx,
            characters=[*relevant_characters, *comparison_characters],
            baseline_by_name=comparison_baselines,
        )
        cache_key = make_voice_review_cache_key(
            book_id,
            body.text,
            body.chapter_num,
            body.character_id,
            baseline_signature,
            body.scene_context,
            body.voice_mode,
        )
        cached = await get_voice_consistency_cache(str(book.id), cache_key, version=cache_version)
        if isinstance(cached, dict) and complete_cached_voice_review(
            cached,
            submitted_text=body.text,
            character_names=[str(character["name"]) for character in eligible_characters],
            voice_mode=body.voice_mode,
            baseline_by_name=baseline_by_name,
        ):
            return await personalize_voice_review_payload(
                db,
                book_id=book_id,
                user_id=current_user.id,
                payload={
                    **cached,
                    "warnings": list(cached.get("warnings") or []),
                    "cached": True,
                },
            )

        system_msg = VOICE_CONSISTENCY_SYSTEM.format(title=safe_prompt_str(book.title))
        # Baseline and context queries have finished. Never hold their transaction
        # idle while the external model processes multiple passage sections.
        await db.commit()
        client = get_openai_client()
        results: list[dict[str, Any]] = []
        character_matches: list[dict[str, Any]] = []
        for character in eligible_characters:
            name = str(character["name"])
            baseline = baseline_by_name[name]
            baseline_style = voice_baseline_style_summary(baseline)
            baseline_block = "\n".join(
                f"Chapter {item['chapter_number']}: {item['excerpt']}" for item in baseline
            )

            async def model_call(section: dict[str, Any]) -> str:
                source_anchors = voice_source_anchors_for_section(
                    body.text, section, current_by_name[name]
                )
                user_msg = VOICE_CONSISTENCY_USER.format(
                    chapter_hint=(
                        f"Submitted chapter: {body.chapter_num or 'custom passage'}. "
                        f"Author-provided scene context: {body.scene_context or 'none supplied'}."
                    ),
                    character_context=voice_review_character_context(
                        name,
                        body.voice_mode,
                        source_anchors,
                        profile_claims=grounded_voice_profile_claims(character, baseline),
                        baseline_style=baseline_style,
                    ),
                    passages=baseline_block,
                    text=section["text"],
                )
                response = await create_tracked_chat_completion(
                    client=client,
                    feature="advisor_voice_consistency",
                    model=settings.OPENAI_INTEL_MODEL,
                    db=db,
                    user_id=billing_user_id,
                    book_id=book.id,
                    temperature=0.2,
                    max_tokens=1400,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                )
                require_complete_llm_response(response)
                return response.choices[0].message.content or "{}"

            try:
                result = await review_voice_sections(
                    body.text,
                    character_name=name,
                    baseline_samples=baseline,
                    submitted_samples=current_by_name[name],
                    model_call=model_call,
                    source_chapter=body.chapter_num,
                )
            except VoiceReviewFormatError as exc:
                raise HTTPException(
                    503,
                    detail="Voice review could not verify complete source evidence. Please retry.",
                ) from exc
            except (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                RateLimitError,
                TimeoutError,
            ) as exc:
                transient = is_transient_llm_provider_error(exc)
                raise HTTPException(
                    503 if transient else 502,
                    detail={
                        "kind": "llm_provider",
                        "message": (
                            "The AI service is temporarily unavailable. Your passage is unchanged; "
                            "retry shortly."
                            if transient
                            else "The AI service could not process this voice review. "
                            "Your passage is unchanged; contact support if this persists."
                        ),
                    },
                ) from exc
            results.append({"character_name": name, **result})
            skipped_sections = len(result["coverage"]["unattributed_ranges"])
            if skipped_sections:
                warnings.append(
                    f"{name}: {skipped_sections} source section(s) contained no attributable "
                    "voice for this character. They were scanned for attribution but not "
                    "compared with the baseline."
                )
            if (
                not voice_current_sample_sufficient(
                    current_by_name[name], voice_mode=body.voice_mode
                )
                or not voice_samples_have_reliable_attribution(current_by_name[name])
                or not voice_samples_have_reliable_attribution(baseline)
            ):
                for issue in result["issues"]:
                    if issue["classification"] == "confirmed":
                        issue["classification"] = "possible"
                        issue["confidence"] = min(issue["confidence"], 0.75)
            if not (
                voice_samples_have_reliable_attribution(current_by_name[name])
                and voice_samples_have_reliable_attribution(baseline)
                and voice_current_sample_sufficient(
                    current_by_name[name], voice_mode=body.voice_mode
                )
            ):
                continue
            current_texts = voice_independent_source_texts(current_by_name[name])
            sample_metrics = compute_voice_metrics(current_texts)
            baseline_metrics = compute_voice_metrics(voice_independent_source_texts(baseline))
            score, signals = score_voice_match(baseline_metrics, sample_metrics)
            alternate_name, alternate_score = closest_alternate_voice_match(
                character_name=name,
                submitted_excerpts=(current_texts if body.voice_mode == "dialogue" else []),
                own_score=score,
                baseline_by_name=comparison_baselines,
            )
            character_matches.append(
                {
                    "character_name": name,
                    "match_score": score,
                    "baseline_sample_size": voice_baseline_size(baseline)[0],
                    "baseline_word_count": voice_baseline_size(baseline)[1],
                    "sample_dialogue_count": int(sample_metrics.get("sample_dialogue_count") or 0),
                    "strongest_signals": signals,
                    "closest_other_character": alternate_name,
                    "closest_other_score": alternate_score,
                }
            )

        tentative_attribution = any(
            item.get("attribution_confidence") in {"contextual", "unverified_narrator"}
            for character in eligible_characters
            for item in (
                *current_by_name[str(character["name"])],
                *baseline_by_name[str(character["name"])],
            )
        )
        limited_current_evidence = any(
            not voice_current_sample_sufficient(
                current_by_name[str(character["name"])], voice_mode=body.voice_mode
            )
            for character in eligible_characters
        )
        overall_coverage = aggregate_voice_review_coverage(results, total_characters=len(body.text))
        unattributed_source = bool(overall_coverage["unattributed_ranges"])
        comparison_coverage_available = "not_compared_ranges" in overall_coverage
        unreviewed_quotes = (
            unattributed_quoted_ranges(body.text, overall_coverage["not_compared_ranges"])
            if body.voice_mode == "dialogue"
            and body.character_id is None
            and comparison_coverage_available
            else []
        )
        if body.voice_mode == "dialogue" and body.character_id is None:
            overall_coverage["unattributed_quoted_ranges"] = unreviewed_quotes
        if unattributed_source:
            warnings.append(
                "Some source sections had no attributable voice for any reviewed character. "
                "The review is incomplete for those sections."
            )
        if not comparison_coverage_available:
            warnings.append(
                "Exact attributed-voice coverage could not be verified. "
                "This review is incomplete and will not be cached as a complete verdict."
            )
        if unreviewed_quotes:
            warnings.append(
                f"{len(unreviewed_quotes)} quoted source range(s) could not be attributed "
                "to a reviewed character or compared with a baseline. "
                "Select a speaker for a focused review if you know who spoke."
            )
        status = (
            "complete"
            if len(eligible_characters) == len(relevant_characters)
            and not skipped_characters
            and not tentative_attribution
            and not limited_current_evidence
            and not unattributed_source
            and comparison_coverage_available
            and not unreviewed_quotes
            else "partial_evidence"
        )
        result = {
            "status": status,
            "issues": [issue for reviewed in results for issue in reviewed["issues"]],
            "overall_verdict": (
                "Narrator attribution in the baseline is tentative; review the possible "
                "differences below against the manuscript before drawing a conclusion."
                if tentative_attribution and body.voice_mode == "first_person_narration"
                else (
                    "Speaker attribution is tentative; review the possible differences below "
                    "against the manuscript before drawing a conclusion."
                    if tentative_attribution
                    else (
                        "Current passage evidence is too limited for a reliable voice match. "
                        "Treat any possible difference as tentative."
                        if limited_current_evidence
                        else (
                            "Some source sections had no attributable voice for any reviewed "
                            "character. Findings below apply only to reviewed sections; this "
                            "is not a complete voice verdict."
                            if unattributed_source
                            else (
                                "Some quoted dialogue could not be assigned to a reviewed "
                                "character. Findings below apply only to attributable voice; "
                                "this is not a complete voice verdict."
                                if unreviewed_quotes
                                else (
                                    "Exact voice comparison coverage could not be verified; "
                                    "this is not a complete voice verdict."
                                    if not comparison_coverage_available
                                    else " ".join(
                                        f"{reviewed['character_name']}: "
                                        f"{reviewed['overall_verdict']}"
                                        for reviewed in results
                                    )
                                )
                            )
                        )
                    )
                )
            ),
        }
        response_payload = {
            "review": result,
            "voice_mode": body.voice_mode,
            "retrieved_passages": [
                {
                    "chapter_num": item["chapter_number"],
                    "chapter_title": None,
                    "chunk_index": None,
                    "excerpt": item["excerpt"],
                    "relevance": 1.0,
                }
                for name in baseline_by_name
                for item in baseline_by_name[name][:6]
            ],
            "characters_reviewed": [character["name"] for character in eligible_characters],
            "characters_detected": [character["name"] for character in detected_characters],
            "character_matches": character_matches,
            "baseline_evidence": baseline_evidence,
            "warnings": warnings,
            "coverage": overall_coverage,
            "coverage_by_character": [
                {"character_name": reviewed["character_name"], **reviewed["coverage"]}
                for reviewed in results
            ],
        }
        response_payload["cached"] = False
        if status == "complete":
            await set_voice_consistency_cache(
                str(book.id),
                cache_key,
                response_payload,
                expected_version=cache_version,
            )
        return await personalize_voice_review_payload(
            db, book_id=book_id, user_id=current_user.id, payload=response_payload
        )
    except VoiceBaselineSourceError as exc:
        raise HTTPException(
            503,
            detail={
                "kind": "manuscript_source",
                "message": (
                    "Stored manuscript text for the voice baseline could not be loaded. "
                    "Please retry, and contact support if it persists."
                ),
            },
        ) from exc
