from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.models.intelligence import (
    ContinuityFinding,
    ContinuityFindingEvidence,
    ContinuityObservation,
    ContinuityScan,
)
from app.services.continuity.domain_detectors import (
    detect_fragmented_plot_threads,
    detect_knowledge_before_acquisition,
    detect_object_state_conflicts,
    detect_world_rule_conflicts,
)

DETECTOR_VERSION = "continuity-rules-v2"

STABLE_CHARACTER_PREDICATES = {
    "character.eye_color",
    "character.eyes",
    "character.birth_date",
    "character.birth_year",
    "character.species",
    "character.blood_type",
    "character.dominant_hand",
}


def generate_findings(
    *,
    scan: ContinuityScan,
    observations: Iterable[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    observation_list = list(observations)
    findings = [
        *_detect_stable_character_conflicts(scan, observation_list, coverage),
        *_detect_same_chapter_location_conflicts(scan, observation_list, coverage),
        *_detect_unsupported_relationship_changes(scan, observation_list, coverage),
        *_detect_unresolved_plot_promises(scan, observation_list, coverage),
        *detect_knowledge_before_acquisition(scan, observation_list, coverage),
        *detect_object_state_conflicts(scan, observation_list, coverage),
        *detect_world_rule_conflicts(scan, observation_list, coverage),
        *detect_fragmented_plot_threads(scan, observation_list, coverage),
    ]
    return findings


def _detect_stable_character_conflicts(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[tuple[str, str], list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "character"
            and observation.subject_id
            and observation.predicate in STABLE_CHARACTER_PREDICATES
        ):
            grouped[(observation.subject_id, observation.predicate)].append(observation)

    findings: list[ContinuityFinding] = []
    for (_, predicate), candidates in grouped.items():
        ordered = sorted(candidates, key=lambda item: (item.chapter_number, str(item.id)))
        for previous, current in zip(ordered, ordered[1:]):
            if previous.normalized_value == current.normalized_value:
                continue
            if (current.provenance or {}).get("has_transition_evidence"):
                continue
            trait_label = predicate.removeprefix("character.").replace("_", " ")
            unreliable = any(
                bool((item.provenance or {}).get("unreliable_narration"))
                for item in (previous, current)
            )
            exact_evidence = (
                all(
                    (item.provenance or {}).get("citation_quality") == "exact"
                    for item in (previous, current)
                )
                and not unreliable
            )
            finding = ContinuityFinding(
                scan_id=scan.id,
                book_id=scan.book_id,
                category="character_state",
                severity="high" if exact_evidence else "medium",
                confidence=min(
                    previous.confidence,
                    current.confidence,
                    0.97 if exact_evidence else 0.74,
                ),
                status="pending" if exact_evidence else "review_needed",
                title=f"{current.subject_label}'s {trait_label} changes",
                explanation=(
                    f"Chapter {previous.chapter_number} describes {trait_label} as "
                    f'"{previous.display_value}", while Chapter {current.chapter_number} '
                    f'describes it as "{current.display_value}". The passages conflict unless '
                    "the change is intentional or one viewpoint is unreliable."
                ),
                recommendation=(
                    "Confirm the intended canon, mark the change intentional, or revise one passage."
                ),
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
            finding.evidence = [
                ContinuityFindingEvidence(
                    observation=previous,
                    evidence_order=1,
                    role="earlier_state",
                ),
                ContinuityFindingEvidence(
                    observation=current,
                    evidence_order=2,
                    role="conflicting_state",
                ),
            ]
            findings.append(finding)
            break
    return findings


def _detect_same_chapter_location_conflicts(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[tuple[str, int], list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "character"
            and observation.subject_id
            and observation.predicate in {"character.location", "character.current_location"}
        ):
            grouped[(observation.subject_id, observation.chapter_number)].append(observation)
    findings: list[ContinuityFinding] = []
    for candidates in grouped.values():
        values: dict[str, ContinuityObservation] = {}
        for candidate in candidates:
            values.setdefault(candidate.normalized_value, candidate)
        if len(values) < 2:
            continue
        earlier, conflicting = list(values.values())[:2]
        if (conflicting.provenance or {}).get("has_transition_evidence"):
            continue
        finding = ContinuityFinding(
            scan_id=scan.id,
            book_id=scan.book_id,
            category="timeline",
            severity="medium",
            confidence=min(earlier.confidence, conflicting.confidence, 0.68),
            status="review_needed",
            title=f"Check {earlier.subject_label}'s location sequence",
            explanation=(
                f"Chapter {earlier.chapter_number} places {earlier.subject_label} at "
                f'"{earlier.display_value}" and "{conflicting.display_value}". Chapter-level '
                "evidence cannot establish simultaneity, so review the scene order, elapsed "
                "time, travel, or an intentional viewpoint effect."
            ),
            recommendation="Clarify the transition or correct one location reference.",
            subject_type=earlier.subject_type,
            subject_id=earlier.subject_id,
            subject_label=earlier.subject_label,
            detector_version=DETECTOR_VERSION,
            content_versions={str(earlier.chapter_number): earlier.content_version},
            coverage=coverage,
        )
        finding.evidence = [
            ContinuityFindingEvidence(
                observation=earlier,
                evidence_order=1,
                role="location_one",
            ),
            ContinuityFindingEvidence(
                observation=conflicting,
                evidence_order=2,
                role="location_two",
            ),
        ]
        findings.append(finding)
    return findings


def _detect_unsupported_relationship_changes(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    grouped: dict[str, list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.subject_type == "relationship"
            and observation.subject_id
            and observation.predicate == "relationship.type"
        ):
            grouped[observation.subject_id].append(observation)
    findings: list[ContinuityFinding] = []
    for candidates in grouped.values():
        ordered = sorted(candidates, key=lambda item: item.chapter_number)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.normalized_value == current.normalized_value or (
                current.provenance or {}
            ).get("has_transition_evidence"):
                continue
            finding = ContinuityFinding(
                scan_id=scan.id,
                book_id=scan.book_id,
                category="relationship",
                severity="medium",
                confidence=min(previous.confidence, current.confidence, 0.7),
                status="review_needed",
                title=f"Check the relationship transition for {current.subject_label}",
                explanation=(
                    f'The tracked relationship changes from "{previous.display_value}" in '
                    f'Chapter {previous.chapter_number} to "{current.display_value}" in '
                    f"Chapter {current.chapter_number}, but no supporting transition is attached."
                ),
                recommendation="Add or link the scene that earns the relationship change.",
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
            finding.evidence = [
                ContinuityFindingEvidence(
                    observation=previous,
                    evidence_order=1,
                    role="earlier_relationship",
                ),
                ContinuityFindingEvidence(
                    observation=current,
                    evidence_order=2,
                    role="later_relationship",
                ),
            ]
            findings.append(finding)
            break
    return findings


def _detect_unresolved_plot_promises(
    scan: ContinuityScan,
    observations: list[ContinuityObservation],
    coverage: dict,
) -> list[ContinuityFinding]:
    by_thread: dict[str, list[ContinuityObservation]] = defaultdict(list)
    for observation in observations:
        if observation.subject_type == "plot_thread" and observation.subject_id:
            by_thread[observation.subject_id].append(observation)

    checked_chapters = sorted(int(number) for number in scan.chapter_versions)
    if len(checked_chapters) < 4:
        return []
    checked_end = checked_chapters[-1]
    findings: list[ContinuityFinding] = []
    for candidates in by_thread.values():
        introduced = next(
            (item for item in candidates if item.predicate == "plot.promise_introduced"),
            None,
        )
        last_known = next(
            (item for item in candidates if item.predicate == "plot.last_known"),
            None,
        )
        payoff = next((item for item in candidates if item.predicate == "plot.payoff"), None)
        if (
            introduced is None
            or last_known is None
            or payoff is not None
            or last_known.normalized_value in {"resolved", "abandoned"}
            or last_known.chapter_number > checked_end - 3
        ):
            continue
        finding = ContinuityFinding(
            scan_id=scan.id,
            book_id=scan.book_id,
            category="plot_payoff",
            severity="medium",
            confidence=min(introduced.confidence, last_known.confidence, 0.74),
            status="review_needed",
            title=f'Check the payoff for "{introduced.subject_label}"',
            explanation=(
                f"The thread is introduced in Chapter {introduced.chapter_number} and last "
                f"surfaced in Chapter {last_known.chapter_number}. No explicit payoff was "
                f"recorded through Chapter {checked_end}. This is an absence-based review, "
                "so an implicit payoff or wording the extractor missed may exist."
            ),
            recommendation=(
                "Review the checked range for an implicit payoff, or add a clearer reveal or resolution."
            ),
            subject_type=introduced.subject_type,
            subject_id=introduced.subject_id,
            subject_label=introduced.subject_label,
            detector_version=DETECTOR_VERSION,
            content_versions={
                str(introduced.chapter_number): introduced.content_version,
                str(last_known.chapter_number): last_known.content_version,
            },
            coverage={
                **coverage,
                "checked_chapter_range": [checked_chapters[0], checked_end],
                "limitation": "Absence findings depend on plot-thread extraction coverage.",
            },
        )
        finding.evidence = [
            ContinuityFindingEvidence(
                observation=introduced,
                evidence_order=1,
                role="introduction",
            ),
            ContinuityFindingEvidence(
                observation=last_known,
                evidence_order=2,
                role="last_known",
            ),
        ]
        findings.append(finding)
    return findings
