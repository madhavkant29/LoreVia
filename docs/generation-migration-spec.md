# Atomic book-data generation migration specification

This document is the design and release checklist for the generation-aware migration. Repository policy permits agents to create and revise unpublished migrations, but published/shared/applied revisions are immutable. Migration execution remains a manual maintainer step for this release.

## Release order

1. Keep the current production backend running while taking a verified database backup.
2. Run the existing read-only release data preflight and resolve duplicate groups for book chunks, chapter summaries, and reading progress.
3. Stop API writes, Celery workers, and Celery Beat so the backfill has a stable dataset.
4. Review `20260909_add_manuscript_import_jobs_and_latency_indexes.py`, followed by `20260909_add_book_data_generations.py`, against the schema and backfill below. Scan both revisions for destructive operations before they are run.
5. Apply the two-revision chain to staging, validate the invariants below, and run the backend integration/rebuild smoke suite.
6. Apply the reviewed revision chain to production while application writes remain stopped.
7. Deploy the VPS API, worker, and Beat containers from the same commit. Start them only after `alembic current` reports the new revision.
8. Smoke-test authentication, upload, existing-book reading, chapter summary retrieval, a successful full rebuild, and a deliberately failed rebuild that retains the old data.
9. Deploy the matching Vercel commit and verify the frontend and backend report the same release SHA.

Do not deploy this backend before the migration. Its ORM queries expect the new table and columns.

## Schema

Create `book_data_generations` to match `app.models.generation.BookDataGeneration`:

- UUID primary key `id`.
- Required `book_id` with `ON DELETE CASCADE` to `books.id`.
- Required, unique, indexed `rebuild_run_id` limited to 32 characters.
- Required indexed `status` (`staging`, `active`, `retired`, or `failed`).
- Required `reason`, `created_at`, and `updated_at`; nullable `promoted_at` and `failed_at`.
- Partial unique index `uq_book_data_generations_active_book` on `book_id WHERE status = 'active'`.
- Index `ix_book_data_generations_status_updated` on `(status, updated_at)`.

Add nullable, indexed UUID `generation_id` columns with `ON DELETE CASCADE` foreign keys to `book_data_generations.id` on:

- `book_chunks`
- `chapter_summaries`
- `characters`
- `character_aliases`
- `character_states`
- `character_voice_profiles`
- `character_candidates`
- `character_mentions`
- `character_duplicate_suggestions`
- `character_relationship_candidates`
- `character_relationships`
- `plot_threads`
- `wiki_entries`
- `world_elements`
- `world_gap_analyses`

Nullable is intentional: `NULL` means author-curated data that survives generation swaps.

## Backfill

For each book, insert exactly one active baseline generation with a unique 32-character rebuild ID and set `promoted_at`.

Assign that generation to all rows in `book_chunks`, `chapter_summaries`, `wiki_entries`, `world_gap_analyses`, `character_mentions`, `character_duplicate_suggestions`, and `character_voice_profiles` belonging to the book.

Assign `character_aliases` to the baseline generation when their parent character is generated. Keep aliases for curated anchor characters at `generation_id = NULL`.

Assign it conditionally to:

- `character_relationships`, `plot_threads`, and `world_elements` only where `edited_by_author = false`.
- `character_candidates` unless the row records an author decision (`rejected`/`merged`, an explicit rejection reason, or a match to a curated anchor character). Automatic accepted/promoted candidates remain generated. Assign `character_relationship_candidates` unless the migration can prove the row is an author-owned decision.
- `characters` unless the character is manual, has `analysis_metadata.user_curated = true`, has `analysis_metadata.protected_from_repair = true`, is referenced by an author-edited relationship, or has an authored custom tag.
- `character_states` for the book, including states associated with a curated anchor character. States are generated projections even when their parent character is curated.

Leave all author-curated rows at `generation_id = NULL`.

## Logical identities

After deduplication and backfill:

- Add `uq_book_chunks_chapter_generation_chunk_index` on `(chapter_id, generation_id, chunk_index)` and partial unique index `uq_book_chunks_unversioned_chapter_chunk_index` on `(chapter_id, chunk_index) WHERE generation_id IS NULL`; retain the existing book/chunk lookup index.
- Add `uq_chapter_summaries_chapter_generation_mode` on `(chapter_id, generation_id, mode)` and partial unique index `uq_chapter_summaries_unversioned_chapter_mode` on `(chapter_id, mode) WHERE generation_id IS NULL`; retain the existing non-unique `(chapter_id, mode)` lookup index.
- Replace `uq_character_aliases_book_char_alias` with `uq_character_aliases_book_char_generation_alias` on `(book_id, character_id, generation_id, normalized_alias)` and add partial unique index `uq_character_aliases_unversioned_book_char_alias` for NULL-generation aliases.
- Replace `uq_character_duplicate_suggestions_pair` with `uq_character_duplicate_suggestions_generation_pair` on `(book_id, generation_id, primary_character_id, secondary_character_id)`.
- Replace `uq_character_voice_profiles_character_id` with `uq_character_voice_profiles_character_generation` on `(character_id, generation_id)` and add partial unique index `uq_character_voice_profiles_unversioned_character` on `(character_id) WHERE generation_id IS NULL`.
- Drop the legacy `uq_characters_book_normalized_active` index, then create `uq_characters_book_generation_normalized_active` on `(book_id, generation_id, normalized_name)` with the model's generated-row predicate.
- Add `uq_characters_book_normalized_curated` on `(book_id, normalized_name)` with the model's curated-row predicate.
- Add or retain `uq_reading_progress_user_id_book_id` on `(user_id, book_id)` after production duplicates are resolved.

## Required validation

- Every book has at most one active generation.
- No staging or failed generation is visible through an ordinary API query.
- Every non-curated generated baseline row has a non-null generation.
- No curated relationship references a character scheduled for cascade deletion; referenced characters must remain unscoped.
- The required identities reported by `release_data_preflight_service.py` are all present.
- A failed rebuild leaves the prior active generation and book features usable.
- A successful rebuild changes all derived views only when the final promotion transaction commits.
- Deleting a retired generation cascades only replaceable data and never deletes curated rows.

The revision includes a guarded `downgrade()` that clears `generation_id` before removing generation objects. It refuses to downgrade if multiple generations would violate a restored legacy identity, because silently deleting generation history would be lossy.
