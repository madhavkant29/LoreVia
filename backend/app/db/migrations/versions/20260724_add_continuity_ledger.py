"""Add the backend-only continuity evidence ledger.

Revision ID: 20260724_continuity_ledger
Revises: 20260624_add_latency_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_continuity_ledger"
down_revision: str | Sequence[str] | None = "20260624_add_latency_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    inspector = _inspector()
    if table not in set(inspector.get_table_names()):
        return
    existing = {
        index_name
        for index in inspector.get_indexes(table)
        if isinstance(index_name := index.get("name"), str)
    }
    if name not in existing:
        op.create_index(name, table, columns)


def _replace_quality_outcome_constraint(*, expanded: bool) -> None:
    inspector = _inspector()
    if "ai_quality_events" not in set(inspector.get_table_names()):
        return
    constraint_name = "ck_ai_quality_events_outcome"
    existing = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints("ai_quality_events")
    }
    if constraint_name in existing:
        op.drop_constraint(constraint_name, "ai_quality_events", type_="check")
    outcomes = [
        "accepted",
        "promoted",
        "merged",
        "rejected",
        "suppressed",
        "resolved",
        "manual_created",
        "corrected",
        "corrected_after_promotion",
    ]
    if expanded:
        outcomes.extend(
            [
                "false_positive",
                "missed_character",
                "incorrect_merge",
                "incorrect_suppression",
                "intentional_change",
            ]
        )
    quoted = ", ".join(f"'{outcome}'" for outcome in outcomes)
    op.create_check_constraint(
        constraint_name,
        "ai_quality_events",
        f"outcome IN ({quoted})",
    )


def upgrade() -> None:
    tables = set(_inspector().get_table_names())
    if "character_states" in tables:
        character_state_columns = {
            column["name"] for column in _inspector().get_columns("character_states")
        }
        if "observed_trait_keys" not in character_state_columns:
            op.add_column(
                "character_states",
                sa.Column(
                    "observed_trait_keys",
                    postgresql.ARRAY(sa.String()),
                    nullable=True,
                ),
            )

    if "continuity_scans" not in tables:
        op.create_table(
            "continuity_scans",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("scope", sa.String(), nullable=False, server_default="full_book"),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column(
                "continuity_status",
                sa.String(),
                nullable=False,
                server_default="insufficient_evidence",
            ),
            sa.Column("detector_version", sa.String(), nullable=False),
            sa.Column(
                "chapter_versions",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "coverage",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "metrics",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Numeric(14, 6), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    _ensure_index("continuity_scans", "ix_continuity_scans_book_id", ["book_id"])
    _ensure_index("continuity_scans", "ix_continuity_scans_user_id", ["user_id"])
    _ensure_index("continuity_scans", "ix_continuity_scans_status", ["status"])
    _ensure_index(
        "continuity_scans", "ix_continuity_scans_continuity_status", ["continuity_status"]
    )
    _ensure_index(
        "continuity_scans", "ix_continuity_scans_book_created", ["book_id", "created_at"]
    )
    _ensure_index("continuity_scans", "ix_continuity_scans_book_status", ["book_id", "status"])

    tables = set(_inspector().get_table_names())
    if "continuity_observations" not in tables:
        op.create_table(
            "continuity_observations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("identity_key", sa.String(length=64), nullable=False),
            sa.Column(
                "scan_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("continuity_scans.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "chapter_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("chapters.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "scene_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("novel_scenes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "source_chunk_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("book_chunks.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("subject_type", sa.String(), nullable=False),
            sa.Column("subject_id", sa.String(), nullable=True),
            sa.Column("subject_label", sa.String(), nullable=False),
            sa.Column("predicate", sa.String(), nullable=False),
            sa.Column("normalized_value", sa.Text(), nullable=False),
            sa.Column("display_value", sa.Text(), nullable=False),
            sa.Column(
                "value_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("evidence_excerpt", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("extractor_version", sa.String(), nullable=False),
            sa.Column(
                "provenance",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "is_author_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "identity_key",
                name="uq_continuity_observations_identity",
            ),
        )

    for name, columns in (
        ("ix_continuity_observations_scan", ["scan_id"]),
        ("ix_continuity_observations_book_id", ["book_id"]),
        ("ix_continuity_observations_chapter_id", ["chapter_id"]),
        ("ix_continuity_observations_scene_id", ["scene_id"]),
        ("ix_continuity_observations_source_chunk_id", ["source_chunk_id"]),
        ("ix_continuity_observations_subject_type", ["subject_type"]),
        ("ix_continuity_observations_subject_id", ["subject_id"]),
        ("ix_continuity_observations_predicate", ["predicate"]),
        ("ix_continuity_observations_chapter_number", ["chapter_number"]),
        (
            "ix_continuity_observations_book_subject",
            ["book_id", "subject_type", "subject_id"],
        ),
        (
            "ix_continuity_observations_book_predicate_chapter",
            ["book_id", "predicate", "chapter_number"],
        ),
    ):
        _ensure_index("continuity_observations", name, columns)

    tables = set(_inspector().get_table_names())
    if "continuity_findings" not in tables:
        op.create_table(
            "continuity_findings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "scan_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("continuity_scans.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "book_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=True),
            sa.Column("subject_type", sa.String(), nullable=False),
            sa.Column("subject_id", sa.String(), nullable=True),
            sa.Column("subject_label", sa.String(), nullable=False),
            sa.Column("detector_version", sa.String(), nullable=False),
            sa.Column(
                "content_versions",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "coverage",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("decision", sa.String(), nullable=True),
            sa.Column("action", sa.String(), nullable=True),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column(
                "decided_by_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    for name, columns in (
        ("ix_continuity_findings_scan", ["scan_id"]),
        ("ix_continuity_findings_book_id", ["book_id"]),
        ("ix_continuity_findings_category", ["category"]),
        ("ix_continuity_findings_status", ["status"]),
        ("ix_continuity_findings_subject_id", ["subject_id"]),
        ("ix_continuity_findings_is_stale", ["is_stale"]),
        ("ix_continuity_findings_book_status", ["book_id", "status"]),
        ("ix_continuity_findings_book_category", ["book_id", "category"]),
    ):
        _ensure_index("continuity_findings", name, columns)

    tables = set(_inspector().get_table_names())
    if "continuity_finding_evidence" not in tables:
        op.create_table(
            "continuity_finding_evidence",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "finding_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("continuity_findings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "observation_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("continuity_observations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("evidence_order", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False, server_default="supporting"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "finding_id",
                "evidence_order",
                name="uq_continuity_finding_evidence_order",
            ),
            sa.UniqueConstraint(
                "finding_id",
                "observation_id",
                name="uq_continuity_finding_observation",
            ),
        )

    _ensure_index(
        "continuity_finding_evidence",
        "ix_continuity_finding_evidence_finding_id",
        ["finding_id"],
    )
    _ensure_index(
        "continuity_finding_evidence",
        "ix_continuity_finding_evidence_observation_id",
        ["observation_id"],
    )
    _replace_quality_outcome_constraint(expanded=True)


def downgrade() -> None:
    if "ai_quality_events" in set(_inspector().get_table_names()):
        op.execute(
            sa.text(
                """
                UPDATE ai_quality_events
                SET outcome = CASE outcome
                    WHEN 'false_positive' THEN 'rejected'
                    WHEN 'missed_character' THEN 'manual_created'
                    WHEN 'incorrect_merge' THEN 'corrected'
                    WHEN 'incorrect_suppression' THEN 'corrected'
                    WHEN 'intentional_change' THEN 'accepted'
                    ELSE outcome
                END
                WHERE outcome IN (
                    'false_positive',
                    'missed_character',
                    'incorrect_merge',
                    'incorrect_suppression',
                    'intentional_change'
                )
                """
            )
        )
        _replace_quality_outcome_constraint(expanded=False)
    tables = set(_inspector().get_table_names())
    for table in (
        "continuity_finding_evidence",
        "continuity_findings",
        "continuity_observations",
        "continuity_scans",
    ):
        if table in tables:
            op.drop_table(table)
    if "character_states" in set(_inspector().get_table_names()):
        character_state_columns = {
            column["name"] for column in _inspector().get_columns("character_states")
        }
        if "observed_trait_keys" in character_state_columns:
            op.drop_column("character_states", "observed_trait_keys")
