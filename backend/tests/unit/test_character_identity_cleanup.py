import uuid

import pytest
from sqlalchemy import select

from app.api.v1.routes.books.characters import (
    add_book_character_alias,
    delete_book_character_alias,
    get_character_identity_diagnostics,
    list_book_character_aliases,
    undo_character_identity_action,
)
from app.models.book import Book
from app.models.character import (
    Character,
    CharacterAlias,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterIdentityAction,
    CharacterIdentityConstraint,
    CharacterMention,
    CharacterSuppression,
)
from app.models.user import User
from app.schemas.character import CharacterAliasBody
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.services.character_identity.repair import CharacterIdentityRepairJob
from app.services.character_identity.resolver import (
    reconcile_pending_first_name_alias_candidates,
    resolve_character_mention,
)
from app.services.character_identity.scoring import score_identity_evidence
from app.utils.characters.candidates import (
    decide_character_candidate_disposition,
    recurring_role_review_supported,
)
from app.utils.characters.duplicates import score_duplicate_characters
from app.utils.characters.identity import has_explicit_full_name_alias_link


def test_full_name_alias_link_requires_explicit_nonconflicting_identity_evidence():
    assert not has_explicit_full_name_alias_link("Mara Vale", aliases=[], evidence={})
    assert not has_explicit_full_name_alias_link("Mara Vale", aliases=["Mara Voss"], evidence={})
    assert has_explicit_full_name_alias_link("Mara Vale", aliases=["Mara Vale"], evidence={})
    assert has_explicit_full_name_alias_link(
        "Mara Vale", aliases=[], evidence={"cluster_names": ["Mara Vale"]}
    )
    assert not has_explicit_full_name_alias_link(
        "Mara Vale",
        aliases=["Mara Vale"],
        evidence={"anti_merge_names": ["Mara Vale"]},
    )
    assert not has_explicit_full_name_alias_link(
        "Mara Vale",
        aliases=["Mara Vale"],
        evidence={},
        reason_codes=["ambiguous_roster_match"],
    )


def test_classify_candidate_kind_handles_cleanup_cases():
    assert classify_candidate_kind("Gregor Samsa") == CandidateKind.CANONICAL_NAME
    assert classify_candidate_kind("Gregor") == CandidateKind.ALIAS
    assert classify_candidate_kind("Mr. Samsa") == CandidateKind.TITLE_NAME
    assert classify_candidate_kind("Madame Meursault") == CandidateKind.CANONICAL_NAME
    assert classify_candidate_kind("Monsieur Meursault") == CandidateKind.CANONICAL_NAME
    assert classify_candidate_kind("Mme Masson") == CandidateKind.CANONICAL_NAME
    assert classify_candidate_kind("Madame") == CandidateKind.FRAGMENT
    assert classify_candidate_kind("Gregor's father") == CandidateKind.KINSHIP_DESCRIPTOR
    assert classify_candidate_kind("the cleaner") == CandidateKind.ROLE_DESCRIPTOR
    for role in (
        "the warden",
        "the porter",
        "the doorkeeper",
        "the lawyer",
        "the examining magistrate",
        "examining magistrate",
    ):
        assert classify_candidate_kind(role) == CandidateKind.ROLE_DESCRIPTOR
    assert classify_candidate_kind("Porter Vale") == CandidateKind.CANONICAL_NAME
    assert classify_candidate_kind("Mr") == CandidateKind.FRAGMENT
    assert classify_candidate_kind("he") == CandidateKind.PRONOUN
    assert classify_candidate_kind("the door") == CandidateKind.OBJECT_OR_PLACE


def test_recurring_unnamed_role_reaches_review_only_with_verified_person_evidence():
    evidence = {
        "mention_count": 3,
        "strong_mention_count": 2,
        "source_mention_count_verified": True,
        "has_attributed_speech": True,
        "verifier": {"final": {"confidence_band": "accept"}},
    }
    assert recurring_role_review_supported("the guard", evidence) is True
    assert recurring_role_review_supported("the warden", evidence) is True
    assert recurring_role_review_supported("examining magistrate", evidence) is True
    disposition = decide_character_candidate_disposition(
        name="the guard",
        confidence=0.9,
        evidence=evidence,
        reason_codes=["recurring_role_person_needs_review"],
    )
    assert disposition.status == "pending"
    assert disposition.action == "queue_review"
    assert recurring_role_review_supported("the guard", {**evidence, "mention_count": 1}) is False
    assert (
        recurring_role_review_supported(
            "the guard", {**evidence, "source_mention_count_verified": False}
        )
        is False
    )
    assert recurring_role_review_supported("the guard", {**evidence, "verifier": {}}) is False
    assert recurring_role_review_supported("the door", evidence) is False


def test_identity_scoring_blocks_title_surname_false_positive():
    mr_samsa = Character(
        book_id=uuid.uuid4(),
        name="Mr. Samsa",
        aliases=[],
        first_chapter=1,
        mention_count=5,
    )
    gregor = Character(
        book_id=mr_samsa.book_id,
        name="Gregor Samsa",
        aliases=[],
        first_chapter=1,
        mention_count=10,
    )

    scores = score_identity_evidence(surface_text="Mr. Samsa", character=mr_samsa, target=gregor)

    assert scores.merge_confidence < 0.75
    assert score_duplicate_characters(mr_samsa, gregor) is None


@pytest.mark.asyncio
async def test_repair_job_soft_merges_exact_duplicates_and_aliases_first_names(db):
    user = User(
        email="identity-cleanup@example.com", username="identity-cleanup", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Cleanup",
        format="pdf",
        s3_key="books/identity-cleanup.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    grete_a = Character(book_id=book.id, name="Grete", aliases=[], first_chapter=1, mention_count=5)
    grete_b = Character(book_id=book.id, name="Grete", aliases=[], first_chapter=1, mention_count=1)
    gregor_full = Character(
        book_id=book.id, name="Gregor Samsa", aliases=[], first_chapter=1, mention_count=8
    )
    gregor_alias = Character(
        book_id=book.id, name="Gregor", aliases=[], first_chapter=1, mention_count=2
    )
    db.add_all([grete_a, grete_b, gregor_full, gregor_alias])
    await db.flush()

    result = await CharacterIdentityRepairJob(db, book_id=book.id).apply()
    await db.flush()

    assert result.auto_merged == 1
    assert result.auto_aliases == 1
    assert grete_b.merged_into_character_id == grete_a.id
    assert grete_b.visibility_state == "noise"
    assert gregor_alias.merged_into_character_id == gregor_full.id
    alias = (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == book.id,
                CharacterAlias.character_id == gregor_full.id,
                CharacterAlias.normalized_alias == "gregor",
            )
        )
    ).scalar_one_or_none()
    assert alias is not None


@pytest.mark.asyncio
async def test_repair_does_not_merge_or_alias_into_reviewed_character(db):
    user = User(
        email=f"repair-reviewed-{uuid.uuid4().hex[:8]}@example.com",
        username=f"repair-reviewed-{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Preserve reviewed identity",
        format="pdf",
        s3_key="books/reviewed-identity.pdf",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    reviewed = Character(
        book_id=book.id,
        name="Mara Vale",
        first_chapter=1,
        mention_count=10,
        analysis_metadata={"user_reviewed": True, "review_note": "Keep as written."},
    )
    duplicate = Character(book_id=book.id, name="Mara Vale", first_chapter=1, mention_count=1)
    short_name = Character(book_id=book.id, name="Mara", first_chapter=1, mention_count=1)
    db.add_all([reviewed, duplicate, short_name])
    await db.flush()

    job = CharacterIdentityRepairJob(db, book_id=book.id)
    preview = await job.preview()
    assert preview.planned_merges == []
    assert preview.planned_aliases == []

    applied = await job.apply()
    await db.flush()
    assert applied.auto_merged == 0
    assert applied.auto_aliases == 0
    assert reviewed.analysis_metadata["review_note"] == "Keep as written."
    assert duplicate.merged_into_character_id is None
    assert short_name.merged_into_character_id is None


@pytest.mark.asyncio
async def test_repair_preview_and_apply_do_not_merge_when_merge_option_is_disabled(db):
    user = User(
        email=f"repair-no-merge-{uuid.uuid4().hex[:8]}@example.com",
        username=f"repair-no-merge-{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Preserve distinct cast",
        format="pdf",
        s3_key="books/preserve-distinct-cast.pdf",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    primary = Character(book_id=book.id, name="Grete", first_chapter=1, mention_count=5)
    duplicate = Character(book_id=book.id, name="Grete", first_chapter=1, mention_count=1)
    noise = Character(book_id=book.id, name="the door", first_chapter=1, mention_count=1)
    db.add_all([primary, duplicate, noise])
    await db.flush()

    job = CharacterIdentityRepairJob(
        db,
        book_id=book.id,
        allow_merge_safe_pairs=False,
        allow_demote_obvious_noise=True,
    )
    preview = await job.preview()
    assert preview.to_payload()["allow_merge_safe_pairs"] is False
    assert preview.planned_merges == []
    assert preview.planned_aliases == []
    assert str(noise.id) in preview.planned_suppressions

    applied = await job.apply()
    await db.flush()
    assert applied.auto_merged == 0
    assert primary.merged_into_character_id is None
    assert duplicate.merged_into_character_id is None
    assert noise.visibility_state == "noise"


@pytest.mark.asyncio
async def test_repair_preview_and_apply_do_not_demote_when_demotion_option_is_disabled(db):
    user = User(
        email=f"repair-no-demote-{uuid.uuid4().hex[:8]}@example.com",
        username=f"repair-no-demote-{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Preserve suspect cast",
        format="pdf",
        s3_key="books/preserve-suspect-cast.pdf",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    primary = Character(book_id=book.id, name="Grete", first_chapter=1, mention_count=5)
    duplicate = Character(book_id=book.id, name="Grete", first_chapter=1, mention_count=1)
    noise = Character(book_id=book.id, name="the door", first_chapter=1, mention_count=1)
    db.add_all([primary, duplicate, noise])
    await db.flush()

    job = CharacterIdentityRepairJob(
        db,
        book_id=book.id,
        allow_merge_safe_pairs=True,
        allow_demote_obvious_noise=False,
    )
    preview = await job.preview()
    assert preview.to_payload()["allow_demote_obvious_noise"] is False
    assert (str(primary.id), str(duplicate.id)) in preview.planned_merges
    assert preview.planned_suppressions == []

    applied = await job.apply()
    await db.flush()
    assert applied.auto_suppressed == 0
    assert duplicate.merged_into_character_id == primary.id
    assert noise.visibility_state != "noise"


@pytest.mark.asyncio
async def test_repair_job_dismisses_low_confidence_duplicate_suggestions(db):
    user = User(
        email="identity-suggestions@example.com",
        username="identity-suggestions",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Suggestions",
        format="pdf",
        s3_key="books/identity-suggestions.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    left = Character(book_id=book.id, name="Anna", aliases=[], first_chapter=1, mention_count=1)
    right = Character(book_id=book.id, name="Annie", aliases=[], first_chapter=1, mention_count=1)
    db.add_all([left, right])
    await db.flush()
    suggestion = CharacterDuplicateSuggestion(
        book_id=book.id,
        primary_character_id=left.id,
        secondary_character_id=right.id,
        confidence=50,
        status="pending",
    )
    db.add(suggestion)
    await db.flush()

    result = await CharacterIdentityRepairJob(db, book_id=book.id).apply()
    await db.flush()

    assert result.blocked_suggestions == 1
    assert suggestion.status == "dismissed"
    assert suggestion.auto_dismissed is True
    assert suggestion.dismissal_reason == "low_confidence_duplicate_suggestion"


@pytest.mark.asyncio
async def test_undo_auto_alias_restores_source_and_blocks_reapplication(db):
    user = User(email="identity-undo@example.com", username="identity-undo", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Undo",
        format="pdf",
        s3_key="books/identity-undo.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    target = Character(
        book_id=book.id, name="Gregor Samsa", aliases=["Gregor"], first_chapter=1, mention_count=8
    )
    db.add(target)
    await db.flush()
    source = Character(
        book_id=book.id,
        name="Gregor",
        aliases=[],
        first_chapter=1,
        mention_count=2,
        merged_into_character_id=target.id,
        visibility_state="noise",
        approval_state="rejected",
        is_auto_suppressed=True,
        suppression_reason="single_token_first_name_alias",
    )
    db.add(source)
    await db.flush()
    alias = CharacterAlias(
        book_id=book.id,
        character_id=target.id,
        alias_text="Gregor",
        normalized_alias="gregor",
        alias_kind="first_name",
        source="repair",
        confidence=0.9,
    )
    action = CharacterIdentityAction(
        book_id=book.id,
        action_type="auto_alias",
        source_character_id=source.id,
        target_character_id=target.id,
        surface_text="Gregor",
        confidence=0.9,
        reason="single_token_first_name_alias",
        reversible=True,
        reversible_data={},
    )
    db.add_all([alias, action])
    await db.flush()

    result = await undo_character_identity_action(
        book_id=book.id,
        action_id=action.id,
        db=db,
        current_user=user,
    )
    await db.flush()

    assert result["undone"] == str(action.id)
    assert source.merged_into_character_id is None
    assert source.visibility_state == "quarantined"
    assert source.approval_state == "pending_review"
    assert target.aliases == []
    assert (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == book.id, CharacterAlias.normalized_alias == "gregor"
            )
        )
    ).scalar_one_or_none() is None
    constraint = (
        await db.execute(
            select(CharacterIdentityConstraint).where(
                CharacterIdentityConstraint.book_id == book.id,
                CharacterIdentityConstraint.constraint_type == "not_same_character",
            )
        )
    ).scalar_one_or_none()
    assert constraint is not None
    assert source.merged_into_character_id is None


@pytest.mark.asyncio
async def test_alias_routes_manage_alias_records_and_diagnostics_reports_identity_state(db):
    user = User(
        email="identity-routes@example.com", username="identity-routes", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Routes",
        format="pdf",
        s3_key="books/identity-routes.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    character = Character(
        book_id=book.id, name="Grete Samsa", aliases=[], first_chapter=1, mention_count=4
    )
    db.add(character)
    await db.flush()

    alias = await add_book_character_alias(
        book_id=book.id,
        character_id=character.id,
        body=CharacterAliasBody(alias_text="Grete", alias_kind="first_name", confidence=0.95),
        db=db,
        current_user=user,
    )

    aliases = await list_book_character_aliases(
        book_id=book.id,
        character_id=character.id,
        db=db,
        current_user=user,
    )
    assert alias.alias_text == "Grete"
    assert alias.normalized_alias == "grete"
    assert character.aliases == ["Grete"]
    assert [item.normalized_alias for item in aliases] == ["grete"]

    db.add_all(
        [
            CharacterSuppression(
                book_id=book.id,
                character_id=character.id,
                surface_text="the sister",
                normalized_text="the sister",
                candidate_kind="role_descriptor",
                reason="role_descriptor",
                confidence=0.7,
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=1,
                raw_name="the sister",
                proposed_name="the sister",
                normalized_name="the sister",
                aliases=[],
                status="suppressed",
                confidence=40,
                reason_codes=["role_descriptor"],
                evidence={},
            ),
            CharacterIdentityAction(
                book_id=book.id,
                action_type="auto_alias",
                source_character_id=None,
                target_character_id=character.id,
                surface_text="Grete",
                confidence=0.95,
                reason="single_token_first_name_alias",
                reversible=True,
                reversible_data={},
            ),
        ]
    )
    await db.commit()

    diagnostics = await get_character_identity_diagnostics(
        book_id=book.id, db=db, current_user=user
    )
    assert diagnostics["suppressed_count"] == 1
    assert diagnostics["auto_alias_count"] == 1
    assert diagnostics["hidden_candidate_count"] == 1
    assert diagnostics["suppression_reasons"] == {"role_descriptor": 1}
    assert diagnostics["recent_identity_actions"][0]["action_type"] == "auto_alias"

    deleted = await delete_book_character_alias(
        book_id=book.id,
        character_id=character.id,
        alias_id=alias.id,
        db=db,
        current_user=user,
    )
    await db.refresh(character)

    assert deleted == {"deleted": str(alias.id)}
    assert character.aliases == []
    assert (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == book.id, CharacterAlias.normalized_alias == "grete"
            )
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_identity_resolver_suppresses_noise_and_resolves_aliases(db):
    user = User(
        email="identity-resolver@example.com", username="identity-resolver", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Resolver",
        format="pdf",
        s3_key="books/identity-resolver.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    full_name = Character(
        book_id=book.id,
        name="Gregor Samsa",
        normalized_name=None,
        aliases=[],
        first_chapter=1,
        mention_count=6,
    )
    db.add(full_name)
    await db.flush()

    fragment_result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Mr",
        evidence={},
    )
    alias_result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Gregor",
        evidence={},
    )
    supported_alias_result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Gregor",
        evidence={"entity": {"aliases": ["Gregor Samsa"]}},
    )
    exact_result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Gregor Samsa",
        evidence={},
    )
    title_result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Mr. Samsa",
        evidence={},
    )
    await db.flush()

    assert fragment_result.action == "auto_suppress"
    assert fragment_result.reason == "fragment_suppressed"
    assert alias_result.action == "needs_review"
    assert alias_result.target_character_id is None
    assert supported_alias_result.action == "auto_alias"
    assert supported_alias_result.target_character_id == full_name.id
    assert exact_result.action == "auto_merge"
    assert exact_result.target_character_id == full_name.id
    assert title_result.action == "needs_review"
    assert title_result.target_character_id is None
    assert (
        await db.execute(
            select(CharacterSuppression).where(
                CharacterSuppression.book_id == book.id,
                CharacterSuppression.normalized_text == "mr",
            )
        )
    ).scalar_one_or_none() is not None
    assert (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == book.id,
                CharacterAlias.character_id == full_name.id,
                CharacterAlias.normalized_alias == "gregor",
            )
        )
    ).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_identity_resolver_holds_ambiguous_first_name_for_review(db):
    user = User(
        email="identity-ambiguous-first@example.com",
        username="identity-ambiguous-first",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Ambiguous First Name",
        format="pdf",
        s3_key="books/ambiguous-first-name.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    db.add_all(
        [
            Character(
                book_id=book.id,
                name="John Carter",
                aliases=[],
                first_chapter=1,
                mention_count=4,
            ),
            Character(
                book_id=book.id,
                name="John Reed",
                aliases=[],
                first_chapter=1,
                mention_count=5,
            ),
        ]
    )
    await db.flush()

    result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="John",
        evidence={},
    )

    assert result.action == "needs_review"
    assert result.target_character_id is None
    assert result.reason == "ambiguous_single_token_first_name"
    aliases = (
        (
            await db.execute(
                select(CharacterAlias).where(
                    CharacterAlias.book_id == book.id,
                    CharacterAlias.normalized_alias == "john",
                )
            )
        )
        .scalars()
        .all()
    )
    assert aliases == []


@pytest.mark.asyncio
async def test_identity_resolver_keeps_recurring_unnamed_person_for_review(db):
    user = User(email="recurring-role@example.com", username="recurring-role", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Recurring role",
        format="manual",
        s3_key="books/recurring-role.txt",
    )
    db.add(book)
    await db.flush()

    evidence = {
        "mention_count": 3,
        "strong_mention_count": 2,
        "source_mention_count_verified": True,
        "has_attributed_speech": True,
        "verifier": {"final": {"confidence_band": "accept"}},
    }
    recurring = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="the guard",
        evidence=evidence,
    )
    magistrate = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="examining magistrate",
        evidence=evidence,
    )
    one_off = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="the nurse",
        evidence={"mention_count": 1},
    )

    assert recurring.action == "needs_review"
    assert recurring.reason == "recurring_role_person_needs_review"
    assert magistrate.action == "needs_review"
    assert magistrate.reason == "recurring_role_person_needs_review"
    assert one_off.action == "auto_suppress"
    suppressions = (
        (
            await db.execute(
                select(CharacterSuppression).where(CharacterSuppression.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert [item.normalized_text for item in suppressions] == ["the nurse"]


@pytest.mark.asyncio
async def test_identity_resolver_does_not_merge_into_rejected_hidden_character(db):
    user = User(
        email="identity-hidden@example.com", username="identity-hidden", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Hidden",
        format="pdf",
        s3_key="books/identity-hidden.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    db.add(
        Character(
            book_id=book.id,
            name="Samsa",
            normalized_name="samsa",
            aliases=[],
            first_chapter=1,
            visibility_state="noise",
            approval_state="rejected",
        )
    )
    await db.flush()

    result = await resolve_character_mention(
        db,
        book_id=book.id,
        chapter_number=1,
        surface_text="Samsa",
        evidence={},
    )

    assert result.action == "needs_review"
    assert result.target_character_id is None


@pytest.mark.asyncio
async def test_book_scope_alias_reconcile_attaches_pending_candidate_from_another_chapter(db):
    user = User(
        email="identity-reconcile@example.com", username="identity-reconcile", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Identity Reconcile",
        format="pdf",
        s3_key="books/identity-reconcile.pdf",
        status="ready",
        mode="author",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()

    full_name = Character(
        book_id=book.id,
        name="Gregor Samsa",
        aliases=[],
        first_chapter=1,
        mention_count=4,
    )
    db.add(full_name)
    await db.flush()
    candidate = CharacterCandidate(
        book_id=book.id,
        chapter_number=2,
        raw_name="Gregor",
        proposed_name="Gregor",
        normalized_name="gregor",
        aliases=[],
        status="pending",
        confidence=90,
        reason_codes=["candidate_dossier_needs_review"],
        evidence={},
    )
    mention = CharacterMention(
        book_id=book.id,
        chapter_number=2,
        raw_name="Gregor",
        normalized_name="gregor",
        resolver_status="unresolved",
        evidence={},
    )
    db.add_all([candidate, mention])
    await db.flush()

    assert await reconcile_pending_first_name_alias_candidates(db, book_id=book.id) == 0
    assert candidate.status == "pending"
    assert mention.matched_character_id is None

    candidate.aliases = ["Gregor Samsa"]
    reconciled = await reconcile_pending_first_name_alias_candidates(db, book_id=book.id)
    await db.flush()

    assert reconciled == 1
    assert candidate.status == "accepted"
    assert candidate.matched_character_id == full_name.id
    assert candidate.reason_codes == ["first_name_alias_reconciled"]
    assert mention.matched_character_id == full_name.id
    assert mention.resolver_status == "auto_alias"

    protected = Character(
        book_id=book.id,
        name="Mara Vale",
        aliases=[],
        first_chapter=1,
        mention_count=4,
        approval_state="protected",
    )
    db.add(protected)
    await db.flush()
    protected_candidate = CharacterCandidate(
        book_id=book.id,
        chapter_number=2,
        raw_name="Mara",
        proposed_name="Mara",
        normalized_name="mara",
        aliases=["Mara Vale"],
        status="pending",
        confidence=90,
        reason_codes=["candidate_dossier_needs_review"],
        evidence={},
    )
    db.add(protected_candidate)
    await db.flush()

    assert await reconcile_pending_first_name_alias_candidates(db, book_id=book.id) == 0
    assert protected_candidate.status == "pending"
    assert protected_candidate.matched_character_id is None
