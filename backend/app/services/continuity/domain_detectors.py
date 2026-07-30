from __future__ import annotations

import re
from collections import defaultdict

from app.models.intelligence import (
    ContinuityFinding,
    ContinuityFindingEvidence,
    ContinuityObservation,
    ContinuityScan,
)

DETECTOR_VERSION = "continuity-rules-v2"


def detect_knowledge_before_acquisition(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[str, list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "character"
            and observation.subject_id
            and observation.predicate in {"knowledge.acquired", "knowledge.used"}
        ):
            grouped[observation.subject_id].append(observation)

    findings: list[ContinuityFinding] = []
    for candidates in grouped.values():
        acquired = sorted(
            (item for item in candidates if item.predicate == "knowledge.acquired"),
            key=lambda item: item.chapter_number,
        )
        used = sorted(
            (item for item in candidates if item.predicate == "knowledge.used"),
            key=lambda item: item.chapter_number,
        )
        if not acquired or not used:
            continue
        pair: tuple[ContinuityObservation, ContinuityObservation] | None = None
        for use in used:
            compatible_acquisitions = [
                item for item in acquired if _knowledge_facts_compatible(use, item)
            ]
            if not compatible_acquisitions:
                continue
            if any(item.chapter_number <= use.chapter_number for item in compatible_acquisitions):
                continue
            pair = (use, compatible_acquisitions[0])
            break
        if pair is None:
            continue
        use, acquisition = pair
        exact = _has_exact_evidence(use, acquisition)
        finding = ContinuityFinding(
            scan_id=scan.id,
            book_id=scan.book_id,
            category="knowledge",
            severity="high" if exact else "medium",
            confidence=min(use.confidence, acquisition.confidence, 0.94 if exact else 0.72),
            status="pending" if exact else "review_needed",
            title=f"{use.subject_label} may use knowledge before learning it",
            explanation=(
                f"Chapter {use.chapter_number} shows {use.subject_label} using "
                f'"{use.display_value}", but the first explicit acquisition is recorded in '
                f"Chapter {acquisition.chapter_number}."
            ),
            recommendation="Add an earlier acquisition beat or revise the premature use.",
            subject_type=use.subject_type,
            subject_id=use.subject_id,
            subject_label=use.subject_label,
            detector_version=DETECTOR_VERSION,
            content_versions={
                str(use.chapter_number): use.content_version,
                str(acquisition.chapter_number): acquisition.content_version,
            },
            coverage=coverage,
        )
        finding.evidence = [
            ContinuityFindingEvidence(
                observation=use,
                evidence_order=1,
                role="premature_use",
            ),
            ContinuityFindingEvidence(
                observation=acquisition,
                evidence_order=2,
                role="later_acquisition",
            ),
        ]
        findings.append(finding)
    return findings


def detect_object_state_conflicts(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[tuple[str, str], list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "object"
            and observation.subject_id
            and observation.predicate
            in {
                "object.state",
                "object.owner",
                "object.location",
                "object.properties",
            }
        ):
            grouped[(observation.subject_id, observation.predicate)].append(observation)

    findings: list[ContinuityFinding] = []
    for (_, predicate), candidates in grouped.items():
        ordered = sorted(candidates, key=lambda item: item.chapter_number)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.normalized_value == current.normalized_value or (
                current.provenance or {}
            ).get("has_transition_evidence"):
                continue
            label = predicate.removeprefix("object.").replace("_", " ")
            finding = ContinuityFinding(
                scan_id=scan.id,
                book_id=scan.book_id,
                category="object_state",
                severity="medium",
                confidence=min(previous.confidence, current.confidence, 0.72),
                status="review_needed",
                title=f"Check {current.subject_label}'s {label}",
                explanation=(
                    f'Chapter {previous.chapter_number} records "{previous.display_value}", '
                    f'while Chapter {current.chapter_number} records "{current.display_value}" '
                    "without a linked destruction, transfer, recovery, or movement event."
                ),
                recommendation="Link the transition evidence or correct one object state.",
                subject_type=current.subject_type,
                subject_id=current.subject_id,
                subject_label=current.subject_label,
                detector_version=DETECTOR_VERSION,
                content_versions={
                    str(previous.chapter_number): previous.content_version,
                    str(current.chapter_number): current.content_version,
                },
                coverage=coverage,
            )
            finding.evidence = _evidence_pair(
                previous,
                current,
                first_role="earlier_object_state",
                second_role="later_object_state",
            )
            findings.append(finding)
            break
    return findings


def detect_world_rule_conflicts(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[str, list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_id
            and observation.predicate == "world.rule"
            and observation.subject_type in {"world_element", "world_rule"}
        ):
            grouped[observation.subject_id].append(observation)

    findings: list[ContinuityFinding] = []
    for candidates in grouped.values():
        ordered = sorted(candidates, key=lambda item: item.chapter_number)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.normalized_value == current.normalized_value:
                continue
            if (current.provenance or {}).get("has_transition_evidence"):
                continue
            finding = ContinuityFinding(
                scan_id=scan.id,
                book_id=scan.book_id,
                category="world_rule",
                severity="medium",
                confidence=min(previous.confidence, current.confidence, 0.72),
                status="review_needed",
                title=f'Potentially conflicting rules for "{current.subject_label}"',
                explanation=(
                    f'Chapter {previous.chapter_number} states "{previous.display_value}", '
                    f'while Chapter {current.chapter_number} states "{current.display_value}". '
                    "Different rule wording is not automatically a logical contradiction."
                ),
                recommendation="Clarify the exception or make the governing rule consistent.",
                subject_type=current.subject_type,
                subject_id=current.subject_id,
                subject_label=current.subject_label,
                detector_version=DETECTOR_VERSION,
                content_versions={
                    str(previous.chapter_number): previous.content_version,
                    str(current.chapter_number): current.content_version,
                },
                coverage=coverage,
            )
            finding.evidence = _evidence_pair(
                previous,
                current,
                first_role="earlier_rule",
                second_role="conflicting_rule",
            )
            findings.append(finding)
            break
    return findings


def detect_fragmented_plot_threads(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[str, list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "plot_thread"
            and observation.subject_id
            and observation.predicate == "plot.promise_introduced"
        ):
            grouped[_normalized_thread_label(observation.subject_label)].append(observation)

    findings: list[ContinuityFinding] = []
    for candidates in grouped.values():
        unique_subjects = {item.subject_id for item in candidates}
        if len(unique_subjects) < 2:
            continue
        first, duplicate = sorted(candidates, key=lambda item: item.chapter_number)[:2]
        finding = ContinuityFinding(
            scan_id=scan.id,
            book_id=scan.book_id,
            category="plot_thread_identity",
            severity="low",
            confidence=min(first.confidence, duplicate.confidence, 0.68),
            status="review_needed",
            title=f'Possible duplicate plot thread: "{first.subject_label}"',
            explanation=(
                "Two stable thread records have the same normalized title but different "
                "identities. Review their descriptions, entities, and chronology before merging."
            ),
            recommendation="Merge the threads if they track the same promise, clue, or payoff.",
            subject_type="plot_thread",
            subject_id=first.subject_id,
            subject_label=first.subject_label,
            detector_version=DETECTOR_VERSION,
            content_versions={
                str(first.chapter_number): first.content_version,
                str(duplicate.chapter_number): duplicate.content_version,
            },
            coverage=coverage,
        )
        finding.evidence = _evidence_pair(
            first,
            duplicate,
            first_role="thread_one",
            second_role="thread_two",
        )
        findings.append(finding)
    return findings


def _knowledge_key(observation: ContinuityObservation) -> str:
    provenance_key = str((observation.provenance or {}).get("fact_key") or "").strip()
    return provenance_key.casefold() or observation.normalized_value


def _knowledge_facts_compatible(
    first: ContinuityObservation,
    second: ContinuityObservation,
) -> bool:
    first_key = _knowledge_key(first)
    second_key = _knowledge_key(second)
    if first_key == second_key:
        return True
    first_terms = _knowledge_terms(first_key)
    second_terms = _knowledge_terms(second_key)
    if not first_terms or not second_terms:
        return False
    overlap = len(first_terms & second_terms)
    return overlap / min(len(first_terms), len(second_terms)) >= 0.7


def _knowledge_terms(value: str) -> set[str]:
    ignored = {
        "a",
        "an",
        "and",
        "is",
        "it",
        "of",
        "that",
        "the",
        "to",
    }
    return {
        term
        for term in re.findall(r"[a-z0-9]+", value.casefold())
        if len(term) > 1 and term not in ignored
    }


def _normalized_thread_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _has_exact_evidence(*observations: ContinuityObservation) -> bool:
    return all(
        (observation.provenance or {}).get("citation_quality") == "exact"
        and not (observation.provenance or {}).get("unreliable_narration")
        for observation in observations
    )


def _evidence_pair(
    first: ContinuityObservation,
    second: ContinuityObservation,
    *,
    first_role: str,
    second_role: str,
) -> list[ContinuityFindingEvidence]:
    return [
        ContinuityFindingEvidence(
            observation=first,
            evidence_order=1,
            role=first_role,
        ),
        ContinuityFindingEvidence(
            observation=second,
            evidence_order=2,
            role=second_role,
        ),
    ]
