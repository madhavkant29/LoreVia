from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROLLOUT_THRESHOLDS = {
    "major_character_precision": 0.98,
    "major_character_recall": 0.95,
    "character_precision": 0.95,
    "character_recall": 0.90,
    "identity_merge_precision": 0.99,
    "high_confidence_continuity_precision": 0.90,
    "citation_coverage": 1.0,
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
    prediction_by_id = {
        str(prediction.get("case_id") or ""): prediction for prediction in predictions
    }
    gold_characters: set[str] = set()
    predicted_characters: set[str] = set()
    gold_major_characters: set[str] = set()
    predicted_major_characters: set[str] = set()
    gold_links: set[str] = set()
    predicted_links: set[str] = set()
    gold_findings: set[str] = set()
    predicted_findings: set[str] = set()
    gold_high_confidence_findings: set[str] = set()
    predicted_high_confidence_findings: set[str] = set()
    cited_findings: set[str] = set()
    latency_by_version: dict[str, list[float]] = defaultdict(list)
    cost_by_version: dict[str, list[float]] = defaultdict(list)
    words_by_version: dict[str, int] = defaultdict(int)

    for case in cases:
        case_id = str(case["id"])
        labels = case["labels"]
        prediction = prediction_by_id.get(case_id, {})
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
        for mention, canonical in (labels.get("identity_links") or {}).items():
            if _metric_key(mention) != _metric_key(canonical):
                gold_links.add(_metric_key(case_id, mention, canonical))
        for mention, canonical in (prediction.get("identity_links") or {}).items():
            if _metric_key(mention) != _metric_key(canonical):
                predicted_links.add(_metric_key(case_id, mention, canonical))
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
            if (
                isinstance(evidence, list)
                and len(evidence) >= 2
                and all(str(anchor.get("excerpt") or "").strip() for anchor in evidence)
            ):
                cited_findings.add(key)

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
    continuity_metrics = _precision_recall(gold_findings, predicted_findings)
    high_confidence_continuity_metrics = _precision_recall(
        gold_high_confidence_findings,
        predicted_high_confidence_findings,
    )
    return {
        "case_count": len(cases),
        "prediction_count": len(prediction_by_id),
        "major_character_precision": major_character_metrics["precision"],
        "major_character_recall": major_character_metrics["recall"],
        "character_precision": character_metrics["precision"],
        "character_recall": character_metrics["recall"],
        "identity_merge_precision": merge_metrics["precision"],
        "identity_merge_recall": merge_metrics["recall"],
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
            round(len(cited_findings) / len(predicted_findings), 4) if predicted_findings else 1.0
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
