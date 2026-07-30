import uuid

from app.models.intelligence import ContinuityObservation, ContinuityScan
from app.services.continuity.detector_service import generate_findings


def _observation(
    *,
    scan: ContinuityScan,
    subject_type: str = "character",
    subject_id: str = "char-1",
    subject_label: str = "Ilya",
    predicate: str,
    value: str,
    chapter: int,
) -> ContinuityObservation:
    return ContinuityObservation(
        id=uuid.uuid4(),
        identity_key=uuid.uuid4().hex,
        scan_id=scan.id,
        book_id=scan.book_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_label=subject_label,
        predicate=predicate,
        normalized_value=value.casefold(),
        display_value=value,
        chapter_number=chapter,
        content_version=chapter,
        evidence_excerpt=f"Evidence for {value}",
        confidence=0.96,
        extractor_version="test",
        provenance={"citation_quality": "exact"},
    )


def test_stable_character_conflict_requires_two_ordered_evidence_anchors():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "3": 3},
    )
    observations = [
        _observation(scan=scan, predicate="character.eyes", value="blue", chapter=1),
        _observation(scan=scan, predicate="character.eyes", value="green", chapter=3),
    ]

    findings = generate_findings(
        scan=scan,
        observations=observations,
        coverage={"chapters_analyzed": 2},
    )

    assert len(findings) == 1
    assert findings[0].category == "character_state"
    assert [link.role for link in findings[0].evidence] == [
        "earlier_state",
        "conflicting_state",
    ]
    assert [link.evidence_order for link in findings[0].evidence] == [1, 2]
    assert findings[0].content_versions == {"1": 1, "3": 3}


def test_mutable_character_trait_change_is_not_called_direct_contradiction():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "3": 1},
    )
    observations = [
        _observation(scan=scan, predicate="character.injury", value="broken wrist", chapter=1),
        _observation(scan=scan, predicate="character.injury", value="healed", chapter=3),
    ]

    assert (
        generate_findings(
            scan=scan,
            observations=observations,
            coverage={"chapters_analyzed": 2},
        )
        == []
    )


def test_age_progression_is_not_called_a_direct_contradiction():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "8": 1},
    )
    observations = [
        _observation(scan=scan, predicate="character.age", value="17", chapter=1),
        _observation(scan=scan, predicate="character.age", value="18", chapter=8),
    ]

    assert (
        generate_findings(
            scan=scan,
            observations=observations,
            coverage={"chapters_analyzed": 2},
        )
        == []
    )


def test_explicit_transformation_is_not_reported_as_a_direct_contradiction():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "3": 1},
    )
    earlier = _observation(
        scan=scan,
        predicate="character.eyes",
        value="blue",
        chapter=1,
    )
    transformed = _observation(
        scan=scan,
        predicate="character.eyes",
        value="gold",
        chapter=3,
    )
    transformed.provenance = {
        "citation_quality": "exact",
        "has_transition_evidence": True,
    }

    assert (
        generate_findings(
            scan=scan,
            observations=[earlier, transformed],
            coverage={"chapters_analyzed": 2},
        )
        == []
    )


def test_unreliable_narration_demotes_a_character_conflict_to_review():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "3": 1},
    )
    earlier = _observation(
        scan=scan,
        predicate="character.eyes",
        value="blue",
        chapter=1,
    )
    unreliable = _observation(
        scan=scan,
        predicate="character.eyes",
        value="green",
        chapter=3,
    )
    unreliable.provenance = {
        "citation_quality": "exact",
        "unreliable_narration": True,
    }

    findings = generate_findings(
        scan=scan,
        observations=[earlier, unreliable],
        coverage={"chapters_analyzed": 2},
    )

    assert findings[0].status == "review_needed"
    assert findings[0].severity == "medium"


def test_absence_finding_includes_checked_range_and_two_anchors():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={str(number): 1 for number in range(1, 9)},
    )
    introduced = _observation(
        scan=scan,
        subject_type="plot_thread",
        subject_id="thread-1",
        subject_label="The blue thread",
        predicate="plot.promise_introduced",
        value="introduced",
        chapter=1,
    )
    last_known = _observation(
        scan=scan,
        subject_type="plot_thread",
        subject_id="thread-1",
        subject_label="The blue thread",
        predicate="plot.last_known",
        value="developing",
        chapter=3,
    )

    findings = generate_findings(
        scan=scan,
        observations=[introduced, last_known],
        coverage={"chapters_analyzed": 8},
    )

    assert len(findings) == 1
    assert findings[0].category == "plot_payoff"
    assert findings[0].status == "review_needed"
    assert findings[0].coverage["checked_chapter_range"] == [1, 8]
    assert len(findings[0].evidence) == 2


def test_knowledge_used_before_acquisition_is_flagged_with_both_passages():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"2": 1, "5": 1},
    )
    premature_use = _observation(
        scan=scan,
        predicate="knowledge.used",
        value="the gate needs royal blood",
        chapter=2,
    )
    acquisition = _observation(
        scan=scan,
        predicate="knowledge.acquired",
        value="Nora learns the gate needs royal blood",
        chapter=5,
    )
    premature_use.provenance = {"citation_quality": "exact", "fact_key": "royal-blood-gate"}
    acquisition.provenance = {"citation_quality": "exact", "fact_key": "royal-blood-gate"}

    findings = generate_findings(
        scan=scan,
        observations=[premature_use, acquisition],
        coverage={"chapters_analyzed": 2},
    )

    assert len(findings) == 1
    assert findings[0].category == "knowledge"
    assert [link.role for link in findings[0].evidence] == [
        "premature_use",
        "later_acquisition",
    ]


def test_knowledge_detector_matches_compatible_fact_wording():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"2": 1, "5": 1},
    )
    premature_use = _observation(
        scan=scan,
        predicate="knowledge.used",
        value="royal blood opens the gate",
        chapter=2,
    )
    acquisition = _observation(
        scan=scan,
        predicate="knowledge.acquired",
        value="the gate can be opened with royal blood",
        chapter=5,
    )

    findings = generate_findings(
        scan=scan,
        observations=[premature_use, acquisition],
        coverage={"chapters_analyzed": 2},
    )

    assert len(findings) == 1
    assert findings[0].category == "knowledge"


def test_location_conflict_without_exact_citations_requires_review():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"4": 1},
    )
    harbor = _observation(
        scan=scan,
        predicate="character.location",
        value="harbor",
        chapter=4,
    )
    citadel = _observation(
        scan=scan,
        predicate="character.location",
        value="citadel",
        chapter=4,
    )
    citadel.provenance = {"citation_quality": "approximate"}

    findings = generate_findings(
        scan=scan,
        observations=[harbor, citadel],
        coverage={"chapters_analyzed": 1},
    )

    assert findings[0].status == "review_needed"
    assert findings[0].severity == "medium"


def test_same_chapter_locations_require_review_even_with_exact_citations():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"4": 1},
    )
    observations = [
        _observation(
            scan=scan,
            predicate="character.location",
            value="harbor",
            chapter=4,
        ),
        _observation(
            scan=scan,
            predicate="character.location",
            value="citadel",
            chapter=4,
        ),
    ]

    findings = generate_findings(
        scan=scan,
        observations=observations,
        coverage={"chapters_analyzed": 1},
    )

    assert findings[0].status == "review_needed"
    assert findings[0].severity == "medium"
    assert findings[0].confidence <= 0.68


def test_differently_worded_world_rules_require_review():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "6": 1},
    )
    observations = [
        _observation(
            scan=scan,
            subject_type="world_rule",
            subject_id="rule-1",
            subject_label="Moon gates",
            predicate="world.rule",
            value="open only at midnight",
            chapter=1,
        ),
        _observation(
            scan=scan,
            subject_type="world_rule",
            subject_id="rule-1",
            subject_label="Moon gates",
            predicate="world.rule",
            value="cannot open after sunset",
            chapter=6,
        ),
    ]

    findings = generate_findings(
        scan=scan,
        observations=observations,
        coverage={"chapters_analyzed": 2},
    )

    assert len(findings) == 1
    assert findings[0].category == "world_rule"
    assert findings[0].severity == "medium"
    assert findings[0].status == "review_needed"
    assert findings[0].confidence <= 0.72
    assert len(findings[0].evidence) == 2


def test_duplicate_plot_thread_records_enter_review_instead_of_auto_merging():
    scan = ContinuityScan(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        detector_version="test",
        chapter_versions={"1": 1, "2": 1},
    )
    observations = [
        _observation(
            scan=scan,
            subject_type="plot_thread",
            subject_id="thread-1",
            subject_label="The Missing Crown",
            predicate="plot.promise_introduced",
            value="introduced",
            chapter=1,
        ),
        _observation(
            scan=scan,
            subject_type="plot_thread",
            subject_id="thread-2",
            subject_label="the missing crown",
            predicate="plot.promise_introduced",
            value="introduced",
            chapter=2,
        ),
    ]

    findings = generate_findings(
        scan=scan,
        observations=observations,
        coverage={"chapters_analyzed": 2},
    )

    assert len(findings) == 1
    assert findings[0].category == "plot_thread_identity"
    assert findings[0].status == "review_needed"
