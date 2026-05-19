# LoreVia Backend Stabilization Runbook

Last updated: 2026-05-19

This runbook covers the backend-only stabilization checks for the current processing and reader pipeline.

It is intended for local verification, staging verification, and production sanity checks after deploys that touch:

- manuscript upload validation
- extraction and analysis state
- character persistence and review quality
- reader chapter recovery
- summary delivery

## What should be true after deploy

- new uploads are validated by file type before ingestion starts
- chapter processing state is explicit, not inferred from missing data
- summaries return `ready`, `pending`, or `failed`
- junk single-token extraction noise does not persist into the Character Bible
- stored chapter drift queues repair instead of reparsing inline in the reader route
- reader chapter responses expose both `analysis_status` and `source_integrity`

## Migration and startup checks

Verify:

- the schema includes `chapters.analysis_state`
- the schema includes `characters.analysis_metadata`
- the app boots with the moderation and social models loaded
- extraction, analysis, and API services start without import-time route/helper conflicts

Recommended checks:

```powershell
docker compose -f docker-compose-local.yml ps
docker compose -f docker-compose-local.yml exec -T api pytest tests/unit/test_summary_service.py -q
```

## Upload validation checks

Verify all of the following:

1. Valid minimal PDF upload is accepted.
2. Valid minimal DOCX upload is accepted.
3. Valid minimal EPUB upload is accepted.
4. Invalid ZIP-disguised DOCX is rejected with `400`.
5. Binary or null-byte text upload is rejected with `400`.

Expected behavior:

- validation fails before ingestion task scheduling
- rejection messages are format-specific and do not silently fall through to parsing

## Processing-state checks

For a newly uploaded book, verify:

1. extraction starts with explicit chapter state
2. analysis transitions through `queued` or `running`
3. reader summary endpoints return `pending` before data exists
4. completed chapters return `ready`
5. failed chapters return `failed` and preserve `last_error`

Expected response fields:

- `is_fully_ready`
- `pipeline.extraction`
- `pipeline.analysis`
- `retry_actions`
- chapter `analysis_status`

## Character quality checks

Verify:

1. noise candidates such as `Well`, `Would`, `Come`, and `Back` do not auto-persist
2. legitimate compact names with grounding still persist
3. manual characters return normalized `analysis_metadata`
4. merged character records do not leave the secondary identity readable after commit

Expected character metadata fields:

- `persistence_reason`
- `evidence_count`
- `summary_quality`
- `needs_review`
- `quality_flags`
- `grounding_passage_count`
- `confidence_band`

## Reader recovery checks

Use a chapter with stale or mismatched stored payload state.

Verify:

1. the reader returns the best available chapter payload
2. the chapter does not synchronously reparse source in-route
3. repair is queued once
4. `source_integrity.recovery_status` becomes `queued`
5. successful repair updates stored text/media and marks `recovered`
6. failed repair preserves readable output and marks `failed`

Expected response fields:

- `analysis_status`
- `source_integrity.text_present`
- `source_integrity.media_marker_count`
- `source_integrity.stored_media_count`
- `source_integrity.recovery_status`
- `source_integrity.last_recovery_error`

## Suggested backend verification suites

Run these first:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests/unit/test_character_utils.py tests/unit/test_books_routes.py tests/unit/test_reader_routes.py tests/unit/test_summary_service.py tests/unit/test_upload_security_utils.py tests/unit/test_chapter_recovery_service.py tests/unit/test_pipeline_state_service.py -q
```

Then run these integration slices:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests/integration/test_ingestion_pipeline.py tests/integration/test_reader.py tests/integration/test_access_control.py tests/integration/test_book_cover_and_merge.py -q
```

Final gate:

```powershell
docker compose -f docker-compose-local.yml exec -T api pytest tests -q
```

## If something fails

- If upload tests fail, check whether fixtures still use fake bytes for structured formats.
- If merge tests fail, inspect character re-pointing and secondary deletion behavior before changing tests.
- If reader recovery tests fail, inspect inflight-key clearing and `source_integrity` persistence first.
- If summary tests fail, make sure no request-time generation path was reintroduced.
