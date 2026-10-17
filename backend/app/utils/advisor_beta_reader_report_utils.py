from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.schemas.advisor import BetaReaderReportOut
from app.utils.advisor_beta_reader_analysis_utils import stable_beta_reader_id

MAX_STORED_BETA_READER_REPORTS = 5


def _bounded_text(value: object, max_chars: int) -> str:
    return " ".join(str(value or "").split()).strip()[:max_chars]


def _bounded_text_list(value: object, *, limit: int, max_chars: int) -> list[str]:
    source = value if isinstance(value, list) else []
    return [cleaned for item in source[:limit] if (cleaned := _bounded_text(item, max_chars))]


def bound_beta_reader_report(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    payload = copy.deepcopy(raw)
    payload["overused_terms"] = list(payload.get("overused_terms") or [])[:30]
    payload["character_voices"] = list(payload.get("character_voices") or [])[:20]
    payload["findings"] = list(payload.get("findings") or [])[:20]
    payload["revision_candidates"] = list(payload.get("revision_candidates") or [])[:20]
    payload["overall_impression"] = _bounded_text(payload.get("overall_impression"), 1200)
    payload["reader_vibe"] = _bounded_text(payload.get("reader_vibe"), 1200)
    payload["story_understanding"] = _bounded_text(payload.get("story_understanding"), 1200)
    payload["strengths"] = _bounded_text_list(payload.get("strengths"), limit=8, max_chars=600)
    payload["reader_questions"] = _bounded_text_list(
        payload.get("reader_questions"), limit=8, max_chars=600
    )
    payload["prioritized_revisions"] = _bounded_text_list(
        payload.get("prioritized_revisions"), limit=8, max_chars=600
    )
    payload["warnings"] = _bounded_text_list(payload.get("warnings"), limit=30, max_chars=500)
    for collection_name in ("overused_terms", "findings", "revision_candidates"):
        for item in payload[collection_name]:
            if isinstance(item, dict):
                item["evidence"] = [
                    {
                        "chapter_number": evidence.get("chapter_number"),
                        "excerpt": " ".join(str(evidence.get("excerpt") or "").split())[:240],
                    }
                    for evidence in (item.get("evidence") or [])[:3]
                    if isinstance(evidence, dict) and str(evidence.get("excerpt") or "").strip()
                ]
    for item in payload["overused_terms"]:
        if not isinstance(item, dict):
            continue
        item["term"] = _bounded_text(item.get("term"), 240)
        chapter_counts = (
            item.get("chapter_counts") if isinstance(item.get("chapter_counts"), dict) else {}
        )
        item["chapter_counts"] = {
            _bounded_text(key, 12): max(0, int(value))
            for key, value in list(chapter_counts.items())[:500]
            if _bounded_text(key, 12) and isinstance(value, (int, float))
        }
    for item in payload["character_voices"]:
        if not isinstance(item, dict):
            continue
        item["character_name"] = _bounded_text(item.get("character_name"), 160)
        item["closest_character_name"] = (
            _bounded_text(item.get("closest_character_name"), 160) or None
        )
        item["shared_signals"] = _bounded_text_list(
            item.get("shared_signals"), limit=9, max_chars=160
        )
        item["shared_phrases"] = _bounded_text_list(
            item.get("shared_phrases"), limit=6, max_chars=120
        )
        signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
        item["signals"] = {
            _bounded_text(key, 80): int(value)
            for key, value in list(signals.items())[:12]
            if _bounded_text(key, 80) and isinstance(value, (int, float))
        }
    for collection_name in ("findings", "revision_candidates"):
        for item in payload[collection_name]:
            if not isinstance(item, dict):
                continue
            item["title"] = _bounded_text(item.get("title"), 160)
            item["description"] = _bounded_text(item.get("description"), 1000)
            item["recommendation"] = _bounded_text(item.get("recommendation"), 800)
            if collection_name == "findings":
                item["reader_question"] = _bounded_text(item.get("reader_question"), 500) or None
    try:
        return BetaReaderReportOut.model_validate(payload).model_dump(mode="json")
    except ValidationError:
        return None


def normalize_ai_beta_reader_state(raw: object) -> dict[str, list[dict[str, Any]]]:
    source = raw if isinstance(raw, dict) else {}
    reports: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in source.get("reports") or []:
        bounded = bound_beta_reader_report(item)
        if bounded is None or bounded["report_id"] in seen_ids:
            continue
        bounded["is_stale"] = False
        reports.append(bounded)
        seen_ids.add(bounded["report_id"])
    reports.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"reports": reports[:MAX_STORED_BETA_READER_REPORTS]}


def find_cached_beta_reader_report(
    raw_state: object,
    *,
    request_hash: str,
    source_fingerprint: str,
) -> dict[str, Any] | None:
    state = normalize_ai_beta_reader_state(raw_state)
    return next(
        (
            dict(report)
            for report in state["reports"]
            if report.get("request_hash") == request_hash
            and report.get("source_fingerprint") == source_fingerprint
        ),
        None,
    )


def merge_beta_reader_report(raw_state: object, report: dict[str, Any]) -> dict[str, Any]:
    bounded = bound_beta_reader_report(report)
    if bounded is None:
        raise ValueError("Invalid AI beta reader report.")
    state = normalize_ai_beta_reader_state(raw_state)
    reports = [
        bounded,
        *(item for item in state["reports"] if item["report_id"] != bounded["report_id"]),
    ]
    return {"reports": reports[:MAX_STORED_BETA_READER_REPORTS]}


def build_beta_reader_revision_candidates(
    *,
    overused_terms: list[dict[str, Any]],
    character_voices: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for finding in findings:
        candidates.append(
            {
                "id": stable_beta_reader_id("candidate", finding["id"]),
                "source_item_id": finding["id"],
                "category": finding["category"],
                "severity": finding["severity"],
                "title": finding["title"],
                "description": finding["description"],
                "recommendation": finding["recommendation"],
                "chapter_number": finding.get("chapter_number"),
                "evidence": finding.get("evidence") or [],
            }
        )
    for term in overused_terms[:5]:
        chapter_counts = term.get("chapter_counts") or {}
        chapter_number = (
            int(max(chapter_counts, key=chapter_counts.get)) if chapter_counts else None
        )
        candidates.append(
            {
                "id": stable_beta_reader_id("candidate", term["id"]),
                "source_item_id": term["id"],
                "category": "repetition",
                "severity": "medium" if term.get("burst_detected") else "low",
                "title": f"Review repeated {term['kind']}: “{term['term']}”",
                "description": (
                    f"The {term['kind']} appears {term['count']} times "
                    f"({term['rate_per_1000']} per 1,000 words)."
                ),
                "recommendation": "Keep intentional repetitions and vary or remove the distracting instances.",
                "chapter_number": chapter_number,
                "evidence": term.get("evidence") or [],
            }
        )
    for voice in character_voices:
        score = voice.get("distinctness_score")
        if not isinstance(score, int) or score >= 35:
            continue
        candidates.append(
            {
                "id": stable_beta_reader_id("candidate", voice["id"]),
                "source_item_id": voice["id"],
                "category": "voice",
                "severity": "high" if score < 20 else "medium",
                "title": f"Distinguish {voice['character_name']}’s dialogue",
                "description": (
                    f"{voice['character_name']} is closest to "
                    f"{voice.get('closest_character_name') or 'another character'} "
                    f"with a distinctness score of {score}%."
                ),
                "recommendation": "Strengthen character-specific diction, rhythm, reactions, and verbal habits.",
                "chapter_number": None,
                "evidence": [],
            }
        )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda item: (severity_order[item["severity"]], item["title"]))
    return candidates[:20]


def beta_reader_report_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
