"""Evaluate retrieval quality across reader/advisor continuity flows.

Example:
    python scripts/evaluate_retrieval.py --cases scripts/retrieval_eval_cases.sample.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Series, SeriesBook
from app.utils.advisor_utils import retrieve_series_continuity_passages


@dataclass(frozen=True)
class RetrievalCase:
    name: str
    flow: str
    query: str
    max_chapter: int
    expected_chapters: tuple[int, ...]
    expected_chunk_substring: str | None
    book_id: uuid.UUID | None = None
    book_title: str | None = None
    series_id: uuid.UUID | None = None
    series_name: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate LoreVia retrieval settings against a labeled case file."
    )
    parser.add_argument("--cases", required=True, help="Path to retrieval case JSON.")
    return parser.parse_args()


def _load_cases(path: Path) -> list[RetrievalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases: list[RetrievalCase] = []
    for item in payload:
        cases.append(
            RetrievalCase(
                name=str(item["name"]),
                flow=str(item["flow"]),
                query=str(item["query"]),
                max_chapter=int(item.get("max_chapter", 9999)),
                expected_chapters=tuple(
                    int(chapter) for chapter in item.get("expected_chapters", [])
                ),
                expected_chunk_substring=item.get("expected_chunk_substring"),
                book_id=uuid.UUID(item["book_id"]) if item.get("book_id") else None,
                book_title=item.get("book_title"),
                series_id=uuid.UUID(item["series_id"]) if item.get("series_id") else None,
                series_name=item.get("series_name"),
            )
        )
    return cases


async def _resolve_book_id(case: RetrievalCase) -> uuid.UUID:
    if case.book_id is not None:
        return case.book_id
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Book.id).where(Book.title == case.book_title))
        book_id = result.scalar()
    if book_id is None:
        raise SystemExit(f"Book title not found for case {case.name}: {case.book_title}")
    return book_id


async def _resolve_prior_book_ids(
    case: RetrievalCase, current_book_id: uuid.UUID
) -> list[uuid.UUID]:
    async with AsyncSessionLocal() as db:
        series_id = case.series_id
        if series_id is None and case.series_name:
            series_id = await db.scalar(select(Series.id).where(Series.name == case.series_name))
        if series_id is None:
            raise SystemExit(f"Series not found for case {case.name}")
        rows = (
            (
                await db.execute(
                    select(SeriesBook.book_id)
                    .where(SeriesBook.series_id == series_id, SeriesBook.book_id != current_book_id)
                    .order_by(SeriesBook.position)
                )
            )
            .scalars()
            .all()
        )
    return list(rows)


def _recall_at(results: list[dict[str, Any]], expected_chapters: tuple[int, ...], k: int) -> float:
    if not expected_chapters:
        return 0.0
    found = any(int(result.get("chapter_num") or 0) in expected_chapters for result in results[:k])
    return 1.0 if found else 0.0


def _mrr_at(results: list[dict[str, Any]], expected_chapters: tuple[int, ...], k: int) -> float:
    for index, result in enumerate(results[:k], start=1):
        if int(result.get("chapter_num") or 0) in expected_chapters:
            return 1.0 / index
    return 0.0


def _chunk_match_at(
    results: list[dict[str, Any]], expected_chunk_substring: str | None, k: int
) -> float:
    if not expected_chunk_substring:
        return 0.0
    needle = expected_chunk_substring.casefold()
    for result in results[:k]:
        if needle in str(result.get("text") or "").casefold():
            return 1.0
    return 0.0


async def _run_case(
    case: RetrievalCase, config: dict[str, dict[str, float | int]]
) -> list[dict[str, Any]]:
    book_id = await _resolve_book_id(case)
    async with AsyncSessionLocal() as db:
        if case.flow == "reader":
            return await semantic_search(
                db,
                book_id,
                case.query,
                case.max_chapter,
                limit=int(config["reader"]["return_chunks"]),
                candidate_limit=int(config["reader"]["candidate_chunks"]),
                similarity_threshold=float(config["reader"]["threshold"]),
                usage_feature="retrieval_eval_reader",
            )
        if case.flow == "advisor_general":
            return await semantic_search(
                db,
                book_id,
                case.query,
                case.max_chapter,
                limit=int(config["advisor_general"]["chunks"]),
                candidate_limit=int(config["advisor_general"]["chunks"]),
                similarity_threshold=float(config["advisor_general"]["threshold"]),
                usage_feature="retrieval_eval_advisor_general",
            )
        if case.flow == "advisor_continuity":
            return await semantic_search(
                db,
                book_id,
                case.query,
                case.max_chapter,
                limit=int(config["advisor_continuity"]["chunks"]),
                candidate_limit=int(config["advisor_continuity"]["chunks"]),
                similarity_threshold=float(config["advisor_continuity"]["threshold"]),
                usage_feature="retrieval_eval_advisor_continuity",
            )
        if case.flow == "series_continuity":
            prior_book_ids = await _resolve_prior_book_ids(case, book_id)
            return await retrieve_series_continuity_passages(
                db=db,
                prior_book_ids=prior_book_ids,
                query=case.query,
                similarity_threshold=float(config["series_continuity"]["threshold"]),
                candidate_limit=int(config["series_continuity"]["candidate_chunks"]),
                return_limit=int(config["series_continuity"]["return_chunks"]),
                book_id=book_id,
            )
    raise SystemExit(f"Unsupported flow {case.flow}")


async def _evaluate_config(
    name: str, config: dict[str, dict[str, float | int]], cases: list[RetrievalCase]
) -> None:
    recall3 = recall5 = mrr5 = chunk5 = avg_context = 0.0
    for case in cases:
        results = await _run_case(case, config)
        recall3 += _recall_at(results, case.expected_chapters, 3)
        recall5 += _recall_at(results, case.expected_chapters, 5)
        mrr5 += _mrr_at(results, case.expected_chapters, 5)
        chunk5 += _chunk_match_at(results, case.expected_chunk_substring, 5)
        avg_context += len(results)
    total = max(len(cases), 1)
    print(name)
    print(f"  Recall@3: {recall3 / total:.3f}")
    print(f"  Recall@5: {recall5 / total:.3f}")
    print(f"  MRR@5: {mrr5 / total:.3f}")
    print(f"  ChunkMatch@5: {chunk5 / total:.3f}")
    print(f"  AvgContexts: {avg_context / total:.2f}")


async def _main() -> None:
    args = _parse_args()
    cases = _load_cases(Path(args.cases))
    baseline = {
        "reader": {"threshold": 0.65, "candidate_chunks": 3, "return_chunks": 3},
        "advisor_general": {"threshold": 0.30, "chunks": 5},
        "advisor_continuity": {"threshold": 0.25, "chunks": 10},
        "series_continuity": {"threshold": 0.22, "candidate_chunks": 6, "return_chunks": 6},
    }
    tuned = {
        "reader": {"threshold": 0.55, "candidate_chunks": 10, "return_chunks": 4},
        "advisor_general": {"threshold": 0.28, "chunks": 8},
        "advisor_continuity": {"threshold": 0.22, "chunks": 12},
        "series_continuity": {"threshold": 0.22, "candidate_chunks": 10, "return_chunks": 6},
    }
    await _evaluate_config("baseline", baseline, cases)
    await _evaluate_config("tuned", tuned, cases)


if __name__ == "__main__":
    asyncio.run(_main())
