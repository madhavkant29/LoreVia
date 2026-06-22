# Processing allowances and HNSW rollout

The application defaults to `PROCESSING_ALLOWANCES_MODE=enforce`. Do not edit a
repository `.env` file. An explicit VPS environment value still overrides the
application default.

## Limits

Author and trial accounts receive 2,000,000 active words, 1,000,000 processed
words per calendar month, and 5 GB source storage. Architect accounts receive
8,000,000 active words, 4,000,000 processed words, and 25 GB source storage.
Free accounts retain read-only access to existing projects.

The corresponding server settings are `AUTHOR_ACTIVE_WORD_LIMIT`,
`AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT`, `AUTHOR_SOURCE_STORAGE_LIMIT_BYTES`, and
the equivalent `ARCHITECT_*` settings. Reservations older than one hour are
released by the 15-minute maintenance task.

## Deployment order

1. Back up the database and run Alembic with an explicit `ALEMBIC_DATABASE_URL`.
2. Verify `SELECT extversion FROM pg_extension WHERE extname = 'vector'` returns
   0.5.0 or newer. The migration aborts before index changes otherwise.
3. Copy and run `backend/scripts/benchmark_vector_indexes.sql.example` before and after migration
   and retain the plans in the PR/deployment record. Confirm HNSW index scans and
   compare execution time, rows removed, shared reads, and cache hits.
4. Run `python scripts/backfill_source_sizes.py` first as a dry run, then with
   `--apply` in bounded batches until `checked` reaches zero.
5. For a pre-enforcement audit, explicitly set report mode in the VPS. Compare
   user stats against representative customer projects and monitor stale releases
   and projected blocked actions.
6. Remove the report-mode override, or explicitly set
   `PROCESSING_ALLOWANCES_MODE=enforce`, after validation.

## Rollback

Return to report mode first. The HNSW migration downgrade recreates the prior
IVFFlat indexes before removing HNSW. The allowance migration downgrade removes
accounting data and source-size columns and should only run after preserving any
usage audit data needed by support. Application rollback is safe while report
mode remains active because legacy upload response fields are retained.
