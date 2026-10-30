from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROLLOUT_THRESHOLDS = {
    "prediction_coverage": 1.0,
    "major_character_precision": 0.98,
    "major_character_recall": 0.95,
    "character_precision": 0.95,
    "character_recall": 0.90,
    "identity_merge_precision": 0.99,
    "relationship_precision": 0.90,
    "relationship_recall": 0.80,
    "relationship_citation_coverage": 1.0,
    "extraction_source_coverage": 1.0,
    "high_confidence_continuity_precision": 0.90,
    "high_confidence_continuity_recall": 0.80,
    "citation_coverage": 1.0,
    "profile_claim_source_coverage": 1.0,
    "production_dismissal_rate": 0.15,
}


def load_evaluation_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("Evaluation corpus must contain a cases list.")
    validate_evaluation_cases(cases)
    return cases


def validate_evaluation_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) < 25:
        raise ValueError("The character/continuity corpus must contain at least 25 cases.")
    genres: dict[str, int] = defaultdict(int)
    seen_ids: set[str] = set()
    required_labels = {
        "characters",
        "identity_links",
        "relationships",
        "state_transitions",
        "timeline_events",
        "knowledge_events",
        "plot_threads",
        "findings",
    }
    for case in cases:
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in seen_ids:
            raise ValueError("Every evaluation case needs a unique non-empty id.")
        seen_ids.add(case_id)
        genre = str(case.get("genre") or "").strip().casefold()
        genres[genre] += 1
        if not str(case.get("text") or "").strip():
            raise ValueError(f"Evaluation case {case_id} has no text.")
        labels = case.get("labels")
        if not isinstance(labels, dict) or not required_labels.issubset(labels):
            missing = sorted(required_labels - set(labels or {}))
            raise ValueError(f"Evaluation case {case_id} is missing labels: {missing}.")
    expected_genres = {
        "fantasy",
        "romance",
        "mystery",
        "science_fiction",
        "contemporary",
    }
    if any(genres.get(genre, 0) < 5 for genre in expected_genres):
        raise ValueError("The corpus must contain at least five cases in every target genre.")


def evaluate_predictions(
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    case_ids = {str(case["id"]) for case in cases}
    prediction_by_id: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        if not isinstance(prediction, dict):
            raise ValueError("Predictions must be objects with case IDs.")
        case_id = str(prediction.get("case_id") or "").strip()
        if not case_id or case_id in prediction_by_id:
            raise ValueError("Prediction case IDs must be non-empty and unique.")
        if case_id not in case_ids:
            raise ValueError(f"Unknown prediction case ID: {case_id}")
        prediction_by_id[case_id] = prediction
    gold_characters: set[str] = set()
    predicted_characters: set[str] = set()
    gold_major_characters: set[str] = set()
    predicted_major_characters: set[str] = set()
    gold_links: set[str] = set()
    predicted_links: set[str] = set()
    gold_relationships: set[str] = set()
    predicted_relationships: set[str] = set()
    relationship_support_by_key: dict[str, bool] = {}
    gold_findings: set[str] = set()
    predicted_findings: set[str] = set()
    gold_high_confidence_findings: set[str] = set()
    predicted_high_confidence_findings: set[str] = set()
    citation_support_by_key: dict[str, bool] = {}
    profile_claim_count = 0
    sourced_profile_claim_count = 0
    fully_covered_sources = 0
    latency_by_version: dict[str, list[float]] = defaultdict(list)
    cost_by_version: dict[str, list[float]] = defaultdict(list)
    words_by_version: dict[str, int] = defaultdict(int)

    for case in cases:
        case_id = str(case["id"])
        labels = case["labels"]
        source_text = str(case.get("text") or "")
        prediction = prediction_by_id.get(case_id, {})
        fully_covered_sources += int(
            _prediction_covers_source(source_text, prediction.get("source_coverage"))
        )
        for character in labels.get("characters", []):
            key = _metric_key(case_id, character.get("canonical_name") or character.get("name"))
            gold_characters.add(key)
            if _is_major_character(character):
                gold_major_characters.add(key)
        for character in prediction.get("characters", []):
            key = _metric_key(case_id, character.get("canonical_name") or character.get("name"))
            predicted_characters.add(key)
            if _is_major_character(character):
                predicted_major_characters.add(key)
            metadata = character.get("analysis_metadata")
            claims = (
                metadata.get("profile_claims")
                if isinstance(metadata, dict)
                else character.get("profile_claims")
            )
            for claim in claims if isinstance(claims, list) else []:
                if not isinstance(claim, dict) or not claim.get("field") or not claim.get("value"):
                    continue
                profile_claim_count += 1
                quote = str(claim.get("quote") or "")
                if quote and quote in source_text:
                    sourced_profile_claim_count += 1
        for mention, canonical in (labels.get("identity_links") or {}).items():
            if _metric_key(mention) != _metric_key(canonical):
                gold_links.add(_metric_key(case_id, mention, canonical))
        for mention, canonical in (prediction.get("identity_links") or {}).items():
            if _metric_key(mention) != _metric_key(canonical):
                predicted_links.add(_metric_key(case_id, mention, canonical))
        for relationship in labels.get("relationships", []):
            if isinstance(relationship, dict):
                gold_relationships.add(_metric_key(case_id, _relationship_key(relationship)))
        for relationship in prediction.get("relationships", []):
            if isinstance(relationship, dict):
                key = _metric_key(case_id, _relationship_key(relationship))
                predicted_relationships.add(key)
                evidence = relationship.get("label_evidence") or relationship.get("evidence")
                quote = str(evidence.get("quote") or "") if isinstance(evidence, dict) else ""
                relationship_support_by_key[key] = (
                    relationship_support_by_key.get(key, True)
                    and bool(quote.strip())
                    and quote in source_text
                )
        for finding in labels.get("findings", []):
            key = _metric_key(case_id, _finding_key(finding))
            gold_findings.add(key)
            if _is_high_confidence_finding(finding):
                gold_high_confidence_findings.add(key)
        for finding in prediction.get("findings", []):
            key = _metric_key(case_id, _finding_key(finding))
            predicted_findings.add(key)
            if _is_high_confidence_finding(finding):
                predicted_high_confidence_findings.add(key)
            evidence = finding.get("evidence")
            citation_supported = (
                isinstance(evidence, list)
                and len(evidence) >= 2
                and all(
                    isinstance(anchor, dict)
                    and str(anchor.get("excerpt") or "").strip()
                    and str(anchor["excerpt"]) in source_text
                    for anchor in evidence
                )
            )
            citation_support_by_key[key] = (
                citation_support_by_key.get(key, True) and citation_supported
            )

        version = str(prediction.get("extractor_version") or "unknown")
        latency_by_version[version].append(float(prediction.get("latency_ms") or 0))
        cost_by_version[version].append(float(prediction.get("cost_usd") or 0))
        words_by_version[version] += int(prediction.get("word_count") or 0)

    character_metrics = _precision_recall(gold_characters, predicted_characters)
    major_character_metrics = _precision_recall(
        gold_major_characters or gold_characters,
        predicted_major_characters or predicted_characters,
    )
    merge_metrics = _precision_recall(gold_links, predicted_links)
    relationship_metrics = _precision_recall(gold_relationships, predicted_relationships)
    continuity_metrics = _precision_recall(gold_findings, predicted_findings)
    high_confidence_continuity_metrics = _precision_recall(
        gold_high_confidence_findings,
        predicted_high_confidence_findings,
    )
    return {
        "case_count": len(cases),
        "prediction_count": len(prediction_by_id),
        "missing_prediction_ids": sorted(case_ids - set(prediction_by_id)),
        "prediction_coverage": (
            round(len(prediction_by_id) / len(case_ids), 4) if case_ids else None
        ),
        "major_character_precision": major_character_metrics["precision"],
        "major_character_recall": major_character_metrics["recall"],
        "character_precision": character_metrics["precision"],
        "character_recall": character_metrics["recall"],
        "identity_merge_precision": merge_metrics["precision"],
        "identity_merge_recall": merge_metrics["recall"],
        "relationship_precision": relationship_metrics["precision"],
        "relationship_recall": relationship_metrics["recall"],
        "relationship_citation_coverage": (
            round(sum(relationship_support_by_key.values()) / len(predicted_relationships), 4)
            if predicted_relationships
            else None
        ),
        "extraction_source_coverage": (
            round(fully_covered_sources / len(cases), 4) if cases else None
        ),
        "identity_merge_accuracy": (
            round(
                len(gold_links & predicted_links) / len(gold_links | predicted_links),
                4,
            )
            if gold_links or predicted_links
            else 1.0
        ),
        "continuity_precision": continuity_metrics["precision"],
        "continuity_recall": continuity_metrics["recall"],
        "high_confidence_continuity_precision": high_confidence_continuity_metrics["precision"],
        "high_confidence_continuity_recall": high_confidence_continuity_metrics["recall"],
        "citation_coverage": (
            round(sum(citation_support_by_key.values()) / len(predicted_findings), 4)
            if predicted_findings
            else 1.0
        ),
        "profile_claim_source_coverage": (
            round(sourced_profile_claim_count / profile_claim_count, 4)
            if profile_claim_count
            else None
        ),
        "by_extractor_version": {
            version: {
                "case_count": len(latencies),
                "average_latency_ms": round(sum(latencies) / len(latencies), 2),
                "total_cost_usd": round(sum(cost_by_version[version]), 6),
                "average_cost_usd": round(
                    sum(cost_by_version[version]) / len(cost_by_version[version]),
                    6,
                ),
                "word_count": words_by_version[version],
                "latency_ms_per_100k_words": (
                    round(sum(latencies) * 100_000 / words_by_version[version], 2)
                    if words_by_version[version]
                    else None
                ),
                "cost_usd_per_100k_words": (
                    round(
                        sum(cost_by_version[version]) * 100_000 / words_by_version[version],
                        6,
                    )
                    if words_by_version[version]
                    else None
                ),
            }
            for version, latencies in latency_by_version.items()
        },
    }


def evaluate_rollout_gates(
    metrics: dict[str, Any],
    *,
    production_dismissal_rate: float | None = None,
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    for metric, threshold in ROLLOUT_THRESHOLDS.items():
        value = (
            production_dismissal_rate
            if metric == "production_dismissal_rate"
            else metrics.get(metric)
        )
        if value is None:
            results[metric] = {
                "status": "not_evaluated",
                "value": None,
                "threshold": threshold,
            }
            continue
        passes = (
            float(value) < threshold
            if metric == "production_dismissal_rate"
            else float(value) >= threshold
        )
        results[metric] = {
            "status": "passed" if passes else "failed",
            "value": float(value),
            "threshold": threshold,
        }
    evaluated = [result for result in results.values() if result["status"] != "not_evaluated"]
    return {
        "all_evaluated_gates_passed": all(result["status"] == "passed" for result in evaluated),
        "all_gates_evaluated": len(evaluated) == len(results),
        "rollout_ready": (
            len(evaluated) == len(results)
            and all(result["status"] == "passed" for result in evaluated)
        ),
        "gates": results,
    }


def _precision_recall(gold: set[str], predicted: set[str]) -> dict[str, float]:
    true_positives = len(gold & predicted)
    return {
        "precision": (
            round(true_positives / len(predicted), 4) if predicted else (1.0 if not gold else 0.0)
        ),
        "recall": round(true_positives / len(gold), 4) if gold else 1.0,
    }


def _metric_key(*parts: object) -> str:
    return "|".join(" ".join(str(part or "").split()).strip().casefold() for part in parts)


def _relationship_key(relationship: dict[str, Any]) -> str:
    return _metric_key(
        relationship.get("a") or relationship.get("character_a"),
        relationship.get("b") or relationship.get("character_b"),
        relationship.get("type") or relationship.get("rel_type"),
        relationship.get("from") or relationship.get("from_chapter"),
        relationship.get("to") or relationship.get("to_chapter"),
    )


def _prediction_covers_source(source_text: str, coverage: object) -> bool:
    """Verify one synthetic case supplied as one source chunk, including all batch outcomes."""
    if not isinstance(coverage, dict) or coverage.get("complete") is not True:
        return False
    if coverage.get("failure_stage"):
        return False
    if coverage.get("source_characters") != len(source_text):
        return False
    chunks = coverage.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != 1:
        return False
    chunk = chunks[0]
    if not isinstance(chunk, dict) or chunk.get("chunk_index") != 0:
        return False
    if (
        chunk.get("length") != len(source_text)
        or chunk.get("sha256") != hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    ):
        return False
    ranges = coverage.get("ranges")
    if (
        not isinstance(ranges, list)
        or not ranges
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("start"), int)
            or isinstance(item.get("start"), bool)
            or not isinstance(item.get("batch_index"), int)
            or isinstance(item.get("batch_index"), bool)
            for item in ranges
        )
    ):
        return False
    outcomes = coverage.get("batch_outcomes")
    if (
        not isinstance(outcomes, list)
        or not outcomes
        or any(
            not isinstance(outcome, dict)
            or outcome.get("status") != "succeeded"
            or not isinstance(outcome.get("batch_index"), int)
            or isinstance(outcome.get("batch_index"), bool)
            for outcome in outcomes
        )
        or {outcome["batch_index"] for outcome in outcomes}
        != {item.get("batch_index") for item in ranges}
        or len({outcome["batch_index"] for outcome in outcomes}) != len(outcomes)
    ):
        return False
    end = 0
    for item in sorted(ranges, key=lambda part: part["start"]):
        if item.get("chunk_index") != 0:
            return False
        start = item.get("start")
        stop = item.get("end")
        if (
            isinstance(start, bool)
            or isinstance(stop, bool)
            or not isinstance(start, int)
            or not isinstance(stop, int)
            or start < 0
            or start > end
            or stop <= start
            or stop > len(source_text)
        ):
            return False
        end = max(end, stop)
    return end == len(source_text)


def _finding_key(finding: dict[str, Any]) -> str:
    explicit = str(finding.get("key") or "").strip()
    if explicit:
        return explicit
    return _metric_key(
        finding.get("category"),
        finding.get("subject"),
        ",".join(str(item) for item in finding.get("chapters", [])),
    )


def _is_major_character(character: dict[str, Any]) -> bool:
    if "is_major" in character:
        return bool(character.get("is_major"))
    return str(character.get("role") or "").strip().casefold() in {
        "major",
        "protagonist",
        "antagonist",
        "deuteragonist",
    }


def _is_high_confidence_finding(finding: dict[str, Any]) -> bool:
    if "confidence" in finding:
        try:
            return float(finding.get("confidence") or 0) >= 0.8
        except (TypeError, ValueError):
            return False
    severity = str(finding.get("severity") or "").strip().casefold()
    return severity in {"high", "critical"} or not severity
