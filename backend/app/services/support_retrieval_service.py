from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import LLM_PROVIDER_EXCEPTIONS, get_openai_client
from app.models.user import User
from app.schemas.support import (
    SupportActionOut,
    SupportAnswerOut,
    SupportRecentMessage,
    SupportSourceOut,
    SupportUiContext,
)
from app.utils.llm_usage_utils import create_tracked_chat_completion

SUPPORT_CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "support" / "articles.json"
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]+")
MIN_GROUNDED_SCORE = 1.8
SUPPORT_AI_FEATURE = "support_assistant"
COMPACT_ANSWER_MAX_CHARS = 700
SUPPORT_AI_SYSTEM = """You are LoreVia Support Assistant.
Answer only questions about using LoreVia, account/billing navigation, app troubleshooting, and support workflows.
Use only the provided support guide excerpts and safe UI context. Do not infer from or request manuscript text.
If the guide excerpts do not support an answer, say you cannot verify it and suggest creating a support case.
Default to one short paragraph. Use a numbered list only for navigation or troubleshooting steps, with at most four steps.
Give a fuller answer only when the user explicitly asks for full, detailed, or step-by-step help, or when a process requires it."""
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "how",
    "i",
    "is",
    "it",
    "my",
    "of",
    "or",
    "should",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}


@dataclass(frozen=True)
class SupportArticle:
    slug: str
    title: str
    summary: str
    audience: tuple[str, ...]
    routes: tuple[str, ...]
    workspace: str
    plan_notes: str
    permission_notes: str
    keywords: tuple[str, ...]
    tool_ids: tuple[str, ...]
    steps: tuple[str, ...]
    warnings: tuple[str, ...]
    deep_links: tuple[dict[str, Any], ...]
    error_codes: tuple[str, ...]

    @property
    def lexical_text(self) -> str:
        return " ".join(
            (
                self.title,
                self.summary,
                *self.keywords,
                *self.steps,
                *self.warnings,
                self.plan_notes,
                self.permission_notes,
            )
        )


def _tokens(value: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(value.lower()) if token not in QUERY_STOPWORDS}


@lru_cache(maxsize=1)
def load_support_corpus() -> tuple[str, tuple[SupportArticle, ...]]:
    payload = json.loads(SUPPORT_CORPUS_PATH.read_text(encoding="utf-8"))
    version = str(payload["corpus_version"])
    articles: list[SupportArticle] = []
    slugs: set[str] = set()
    for raw in payload.get("articles", []):
        slug = str(raw["slug"])
        if slug in slugs:
            raise ValueError(f"Duplicate support article slug: {slug}")
        slugs.add(slug)
        articles.append(
            SupportArticle(
                slug=slug,
                title=str(raw["title"]),
                summary=str(raw["summary"]),
                audience=tuple(raw.get("audience", [])),
                routes=tuple(raw.get("routes", [])),
                workspace=str(raw.get("workspace", "all")),
                plan_notes=str(raw.get("plan_notes", "")),
                permission_notes=str(raw.get("permission_notes", "")),
                keywords=tuple(raw.get("keywords", [])),
                tool_ids=tuple(raw.get("tool_ids", [])),
                steps=tuple(raw.get("steps", [])),
                warnings=tuple(raw.get("warnings", [])),
                deep_links=tuple(raw.get("deep_links", [])),
                error_codes=tuple(raw.get("error_codes", [])),
            )
        )
    if not articles:
        raise ValueError("Support corpus contains no articles")
    return version, tuple(articles)


def _route_matches(pattern: str, route: str) -> bool:
    escaped = re.escape(pattern)
    escaped = escaped.replace(re.escape(":bookId"), r"[^/]+")
    escaped = escaped.replace(re.escape(":chapter"), r"[^/]+")
    return re.fullmatch(escaped, route.split("?", 1)[0]) is not None


def rank_support_articles(
    message: str,
    context: SupportUiContext,
    *,
    limit: int = 3,
) -> list[tuple[SupportArticle, float]]:
    _, articles = load_support_corpus()
    query_tokens = _tokens(message)
    ranked: list[tuple[SupportArticle, float]] = []
    for article in articles:
        article_tokens = _tokens(article.lexical_text)
        overlap = query_tokens & article_tokens
        score = sum(1.0 + math.log1p(len(token)) / 5 for token in overlap)
        phrase_text = article.lexical_text.lower()
        score += sum(2.0 for keyword in article.keywords if keyword.lower() in message.lower())
        if context.route and any(
            _route_matches(route, context.route)
            for route in article.routes
            if ":bookId" not in route or context.book_id is not None
        ):
            score += 2.5
        if context.tool_id and context.tool_id in article.tool_ids:
            score += 3.0
        if context.workspace_shell and article.workspace in {"all", context.workspace_shell}:
            score += 0.75
        if context.error_code and context.error_code in article.error_codes:
            score += 4.0
        if message.lower().strip() in phrase_text:
            score += 1.0
        ranked.append((article, score))
    ranked.sort(key=lambda item: (-item[1], item[0].title))
    return ranked[:limit]


def _resolve_href(href: str, context: SupportUiContext) -> str:
    if ":bookId" not in href:
        return href
    return href.replace(":bookId", str(context.book_id)) if context.book_id else "/library"


def _source_out(article: SupportArticle) -> SupportSourceOut:
    return SupportSourceOut(
        slug=article.slug,
        title=article.title,
        summary=article.summary,
        url=f"/help?guide={article.slug}",
    )


def _actions_for_article(
    article: SupportArticle, context: SupportUiContext
) -> list[SupportActionOut]:
    return [
        SupportActionOut(
            label=str(link["label"]),
            href=_resolve_href(str(link["href"]), context),
            external=bool(link.get("external", False)),
        )
        for link in article.deep_links[:3]
    ]


def _support_sources(ranked: list[tuple[SupportArticle, float]]) -> list[SupportSourceOut]:
    source_articles = [article for article, score in ranked if score >= MIN_GROUNDED_SCORE][:2]
    return [_source_out(article) for article in source_articles]


def _wants_full_support_answer(message: str) -> bool:
    text = message.lower()
    return any(
        phrase in text
        for phrase in (
            "full answer",
            "detailed answer",
            "more detail",
            "step by step",
            "step-by-step",
            "explain fully",
            "thorough",
        )
    )


def _needs_support_steps(message: str) -> bool:
    text = message.lower()
    return any(
        phrase in text
        for phrase in (
            "how",
            "where",
            "access",
            "open",
            "find",
            "navigate",
            "step",
            "failed",
            "not work",
            "cannot",
            "can't",
            "error",
            "retry",
            "stuck",
        )
    )


def _truncate_at_sentence(value: str, max_chars: int) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    candidate = text[:max_chars].rstrip()
    sentence_end = max(candidate.rfind(". "), candidate.rfind("! "), candidate.rfind("? "))
    if sentence_end >= max_chars // 2:
        return candidate[: sentence_end + 1]
    return candidate.rstrip(" ,;:-") + "..."


def _compact_generated_answer(answer: str, *, allow_detailed: bool) -> str:
    normalized = answer.replace("\r\n", "\n").strip()
    if allow_detailed or not normalized:
        return normalized

    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    first_step = next(
        (index for index, line in enumerate(lines) if re.match(r"^\d+[.)]\s+", line)),
        None,
    )
    if first_step is not None:
        intro = _truncate_at_sentence(" ".join(lines[:first_step]), 350)
        step_lines = [
            _truncate_at_sentence(line, 220)
            for line in lines[first_step:]
            if re.match(r"^\d+[.)]\s+", line)
        ][:4]
        return "\n\n".join(part for part in (intro, "\n".join(step_lines)) if part)

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    return _truncate_at_sentence(blocks[0], COMPACT_ANSWER_MAX_CHARS) if blocks else ""


def _build_support_ai_user_prompt(
    *,
    message: str,
    context: SupportUiContext,
    ranked: list[tuple[SupportArticle, float]],
    recent_messages: list[SupportRecentMessage],
    allow_detailed: bool,
) -> str:
    guide_blocks = []
    for article, score in ranked[:3]:
        guide_blocks.append(
            "\n".join(
                (
                    f"Title: {article.title}",
                    f"Score: {score:.2f}",
                    f"Summary: {article.summary}",
                    f"Plan notes: {article.plan_notes}",
                    f"Permission notes: {article.permission_notes}",
                    "Steps:",
                    *[f"- {step}" for step in article.steps],
                    "Warnings:",
                    *[f"- {warning}" for warning in article.warnings],
                    "Actions:",
                    *[
                        f"- {link.get('label')}: {_resolve_href(str(link.get('href', '')), context)}"
                        for link in article.deep_links[:3]
                    ],
                )
            )
        )
    safe_context = context.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"request_id"},
    )
    detail_instruction = (
        "The user asked for fuller help; include enough detail to be useful."
        if allow_detailed
        else "Keep the answer compact unless a short numbered path is needed."
    )
    conversation = [{"role": item.role, "content": item.content} for item in recent_messages[-6:]]
    return "\n\n".join(
        (
            f"User question:\n{message}",
            f"Recent support conversation:\n{json.dumps(conversation, ensure_ascii=True)}",
            f"Safe UI context:\n{json.dumps(safe_context, sort_keys=True)}",
            f"Style instruction:\n{detail_instruction}",
            "Support guide excerpts:\n" + "\n\n---\n\n".join(guide_blocks),
        )
    )


def _allowance_http_error(exc: HTTPException) -> bool:
    detail = exc.detail
    return isinstance(detail, dict) and detail.get("kind") in {"llm_budget", "llm_tokens"}


def answer_support_question(message: str, context: SupportUiContext) -> SupportAnswerOut:
    ranked = rank_support_articles(message, context)
    top_article, top_score = ranked[0]
    if top_score < MIN_GROUNDED_SCORE:
        return SupportAnswerOut(
            answer=(
                "I cannot verify that from LoreVia's support guides. I do not want to guess. "
                "You can rephrase the question with the screen or error you see, or create a support case."
            ),
            confidence=0.0,
            escalation_available=True,
            declined=True,
        )

    allow_detailed = _wants_full_support_answer(message)
    include_steps = allow_detailed or _needs_support_steps(message)
    selected_steps = top_article.steps if allow_detailed else top_article.steps[:4]
    steps = (
        "\n".join(f"{index}. {step}" for index, step in enumerate(selected_steps, 1))
        if include_steps
        else ""
    )
    warning = f"\n\nImportant: {top_article.warnings[0]}" if top_article.warnings else ""
    answer = top_article.summary
    if steps:
        answer += f"\n\n{steps}"
    if warning:
        answer += warning
    confidence = min(0.98, 0.45 + top_score / 20)
    return SupportAnswerOut(
        answer=answer,
        sources=_support_sources(ranked),
        actions=_actions_for_article(top_article, context),
        confidence=confidence,
        escalation_available=True,
    )


async def answer_support_question_ai(
    db: AsyncSession,
    *,
    message: str,
    context: SupportUiContext,
    current_user: User,
    recent_messages: list[SupportRecentMessage] | None = None,
) -> SupportAnswerOut:
    conversation = recent_messages or []
    retrieval_message = " ".join(
        [item.content for item in conversation[-4:] if item.role == "user"] + [message]
    )
    ranked = rank_support_articles(retrieval_message, context)
    top_article, top_score = ranked[0]
    if not settings.SUPPORT_ASSISTANT_ENABLED or not settings.OPENAI_API_KEY:
        return answer_support_question(message, context)

    allow_detailed = _wants_full_support_answer(message)
    max_tokens = 520 if allow_detailed else 220
    try:
        response = await create_tracked_chat_completion(
            client=get_openai_client(),
            feature=SUPPORT_AI_FEATURE,
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=context.book_id,
            budget_class="interactive",
            temperature=0.15,
            max_tokens=max_tokens,
            metadata={
                "budget_class": "interactive",
                "corpus_version": load_support_corpus()[0],
                "top_support_article": top_article.slug,
                "ui_route": context.route,
            },
            messages=[
                {"role": "system", "content": SUPPORT_AI_SYSTEM},
                {
                    "role": "user",
                    "content": _build_support_ai_user_prompt(
                        message=message,
                        context=context,
                        ranked=ranked,
                        recent_messages=conversation,
                        allow_detailed=allow_detailed,
                    ),
                },
            ],
        )
    except HTTPException as exc:
        if _allowance_http_error(exc):
            raise
        return answer_support_question(message, context)
    except LLM_PROVIDER_EXCEPTIONS:
        return answer_support_question(message, context)

    answer = _compact_generated_answer(
        response.choices[0].message.content or "",
        allow_detailed=allow_detailed,
    )
    if not answer:
        return answer_support_question(message, context)
    grounded = top_score >= MIN_GROUNDED_SCORE
    return SupportAnswerOut(
        answer=answer,
        sources=_support_sources(ranked) if grounded else [],
        actions=_actions_for_article(top_article, context) if grounded else [],
        confidence=min(0.98, 0.55 + top_score / 20) if grounded else 0.0,
        escalation_available=True,
        declined=not grounded,
    )


def support_guide_summaries() -> list[dict[str, Any]]:
    _, articles = load_support_corpus()
    return [
        {
            "slug": article.slug,
            "title": article.title,
            "summary": article.summary,
            "routes": list(article.routes),
            "workspace": article.workspace,
        }
        for article in articles
    ]
