# Character intelligence completion audit

> Historical audit: the evidence below was recorded on 2026-10-29. Its test counts,
> uncommitted-work statement, and release decision are not current. Do not use this
> document alone to approve PR #66 or a production deployment.

## Current PR status, 2026-11-01

- PR #66 was last confirmed open and unmerged; its live GitHub state has not
  been rechecked in this audit. The `author` branch was pushed through commit
  `84fe78ea56f6117c84f15dcddd0e86965b1a6b62`; the local worktree was clean
  after that push. Current `main` was merged into `author` in `77e343f1`.
- The latest local backend Docker run on that commit passed 3,266 tests with one
  skip. Ruff lint and formatting passed. Frontend Vitest passed 1,540 tests in
  281 files; frontend type checking, lint, and a production build passed. The
  frontend E2E jobs and cached security scans were verified in earlier passes;
  they have not been rerun after the latest commit.
- Voice Review now bounds collaborator baselines to shared chapters, rejects
  requests for unshared chapters, binds saved jobs to the access scope, and
  exposes incomplete per-voice progress without a clean verdict. These paths
  have local regression tests; they have not been observed in production.
- A subsequent unpublished review found that saved Voice Review jobs could
  outlive changes to the approved cast or earlier baseline chapters. The local
  fix binds jobs to those inputs and the reviewed chapter's saved version,
  checks them before and after worker execution, and hides stale findings.
  Immutable editor-saved chapter keys must now load exactly for Voice Review,
  extraction, and analysis; a missing current key cannot silently fall back to
  an older standard chapter.
  Processing also preserves leading and trailing whitespace in the deserialized
  chapter source, so extraction coverage and reprocess hashes cover that source
  without trimming it in the loader.
  Separate findings survive when the same quotation appears at distinct chapter
  positions while overlapping citations are deduplicated. The new regression
  tests and full backend suite were subsequently run by the user on the
  rebuilt disposable local API image and passed. This work is not in the
  pushed PR head above.
- A further local UI review found that the Voice Review card's focused action
  selected a character but left a long chapter over the 12,000-character
  passage limit, making the follow-up impossible. It now selects a bounded
  source excerpt around the cited voice range, counts Unicode characters like
  the backend, and preserves manual edits. The two affected Vitest files pass
  (32 tests); type checking, lint, and the surface size check pass. The new
  Playwright smoke test could not complete because its local Next server did
  not open a port during startup. The full frontend suite was stopped while
  the user rebuilt Docker locally. These edits are also uncommitted and
  absent from the pushed PR head.
- The saved Voice Review status endpoint now detects changed chapter versions,
  baseline revisions, and cast state even before the first partial result is
  checkpointed. A database-backed API regression was added. The user rebuilt
  the disposable local API image and reported the full backend suite passing:
  3,276 passed, one skipped in 181.85 seconds. The full frontend Vitest suite
  also passed: 1,543 tests across 281 files. Frontend lint and type checking
  passed. Browser smoke testing remains unverified because this session could
  not reach the local Next server from Playwright. The Next production build
  was blocked by Windows sandbox EPERM errors while creating generated route
  directories; that is not a reported TypeScript or webpack compilation error.
- The disposable `lorevia_test` database reported Alembic head while its
  pytest-managed schema was incomplete, so its `alembic check` failure is not
  a valid fresh-migration result. The separate disposable `lorevia` database
  also reported head and showed three older schema differences: one missing
  subscription-email status index and two UI-preference unique objects
  reflected as indexes rather than constraints. Their remote state is unknown.
- A new inspection of the disposable local migration database was not run:
  automatic approval review rejected the Docker command because its usage
  limit was reached. This was an approval-review failure, not a safety finding.
- Production readiness remains unproven. The VPS migration revision and Vault
  constraint prerequisite have not been checked, the matching frontend and
  backend rollout has not occurred, and live extraction/Voice Review quality
  cannot be measured under the user's offline-only provider constraint.

Status: **incomplete**. This audit covers the local checkout on 2026-10-29. It does not claim that the new extractor improves the Meta project's live cast. The user has asked to keep provider evaluation offline and to defer VPS deployment until the goal is verified.

Evidence is classified as **verified locally**, **partial**, or **missing**. Passing unit tests prove the behavior tested, not live model accuracy or the state of production data.

## Original implementation plan

| Requirement | Evidence in the current checkout | Status |
| --- | --- | --- |
| Diagnose the Meta upload, including stored chapter text, extraction batches, candidate dispositions, final cast, voice and Advisor failures | `backend/scripts/report_character_bible_diagnostics.py` supports read-only source verification and now uses the same recorded-key plus standard-key fallback as processing, avoiding false missing-source reports for stale chapter keys. The user supplied counts from the old VPS code (7 cast, 21 pending candidates, 165 open threads), and old logs identify the Voice Review provider connection error and character-picker lazy-load error. No current-code report against the stored Meta manuscript exists. | Partial |
| Cover every extracted passage and make failed batches visibly incomplete | `backend/app/services/extraction_chapter_llm_service.py` records source ranges and batch outcomes, raises on failed batches, and records incomplete profile enrichment. `backend/tests/unit/test_extraction_chapter_llm_service.py` covers success, missing source, invalid output, failed batches, and source offsets. `backend/tests/unit/test_character_extractor.py` verifies that text beyond 12,000 characters reaches the model request. | Verified locally for tested paths; live coverage missing |
| Resolve people, references, profiles and relationships across chapters using exact evidence | The character extractor, narrator helper, profile-enrichment service, relationship evidence helper, and generation-aware resolver have focused tests. The discovery prompt now asks for recurring unnamed individuals; a mocked-discovery test confirms that a repeated, source-backed role survives cleaning and source-range aggregation, then reaches author review. Role classification now recognizes warden, porter, doorkeeper, lawyer, and examining magistrate references; the resolver and both cast-promotion gates keep these unnamed roles in review. A database-backed resolution test confirms that a strongly supported examining magistrate is recorded as a pending candidate without creating a cast member. One-off roles remain suppressed. A fresh Docker Compose Local run of the 34-case synthetic corpus checks 58/58 named hints and 65/65 correctly supplied names surviving the deterministic cleaner, with 17/17 jointly scored identity sets preserved. Only 13/65 correctly supplied names were immediately eligible for automatic cast entry under simulated local verifier acceptance; 29 required another verifier decision, and 23 locally accepted candidates remained in review. This does not measure model discovery, final-cast recall, or claim accuracy. | Partial |
| Repair the Voice Review server error and character-choice request | The supplied old-production logs identify an `openai.APIConnectionError` for Voice Review (request `df25de05-199c-405d-87b2-b2601defdfe0`) and a separate `MissingGreenlet` while serializing the character picker (`char.aliases`, request `423ce6b6-e9bc-4c8f-8cd5-b0e7f3661ffe`). The current checkout loads aliases and governance fields explicitly for navigation queries; a real database/API regression test covers the sparse picker including aliases and status. Voice orchestration releases DB transactions before provider calls, the streaming endpoint handles transient provider failures, and API tests cover failure responses. Voice baseline retrieval also tries the standard chapter storage key when a recorded key is missing or unavailable. Streamed failures log a category and book ID without manuscript text; the JSON logger adds the request ID. No new-code production request has been observed. | Partial |
| Produce multiple evidence-backed Recommended Checks and expose scan failures | `backend/app/utils/advisor_suggestions_utils.py` partitions all evidence into bounded groups, including the 165-thread case; `backend/app/services/advisor_proactive_scan_service.py` runs bounded scans. Tests cover grouping, deduplication, multi-finding output, failures, and progress. Live proactive-audit quality remains unmeasured. | Partial |
| Correct Character Bible labels and add overview actions to Recommended Checks and Chapter Reports | Frontend unit tests and Playwright E2E tests cover labels, overview dialog, deep links, and dismissal. | Verified locally |
| Evaluate quality and offer a safe targeted reprocess from stored text that preserves author decisions | The 34-case story corpus and 16-case voice corpus are original synthetic data; validators pass. `backend/app/services/manuscript_reprocess_service.py` provides a source-hash preflight and staged reprocess; tests cover stale previews, missing source, preserved decisions and reservations. The shared chapter loader now preserves object-storage keys exactly, so a key containing repeated whitespace is not mistaken for a missing chapter; its regression and 105 related tests pass. The evaluation runner has no current pipeline prediction file, so its precision/recall rollout gates cannot be run. The Meta book has not been reprocessed with this code. | Partial |

## Voice Consistency expansion

| Requirement | Local evidence | Status |
| --- | --- | --- |
| 1. Analyse up to 12,000 characters with exact coverage or report incompleteness | `split_voice_passage`, `voice_ranges_cover_text`, `review_voice_sections`, coverage aggregation, and long-passage backend/E2E tests. | Verified locally |
| 2. Build source-backed character baselines without self-comparison | Baseline retrieval reads stored chapter sources, falls back to the standard chapter key when needed, excludes the submitted chapter or matching source, and records sample chapters. Style metrics summarize source excerpts. | Verified locally for tested paths; live baseline quality missing |
| 3. Resolve selected/automatic speakers, aliases, dialogue, and first-person narrators conservatively | Narrator and dialogue helpers plus focused tests cover shared surnames, false quoted self-identification, direct address, and unattributed speech. | Verified locally for tested cases; general accuracy unmeasured |
| 4. Detect meaningful differences and alternate-voice similarity | Prompts and scoring use attributed current and baseline samples; tests cover issue classes and alternate similarities. No live-model predictions have been scored. | Partial |
| 5. Require source-exact submitted and baseline citations for each finding | Review validation checks cited text, source chapter, evidence strength, classification, explanation and revision direction. Malformed or fabricated citations fail. | Verified locally for tested cases |
| 6. Record intentional, incorrect and resolved decisions across reviews | `VoiceReviewDecision` model, new migration, API, and integration tests cover persistence and suppression. | Verified locally; migration not applied remotely |
| 7. Return insufficient evidence below baseline sample and word thresholds | Baseline thresholds and API tests cover insufficient-evidence results without a confident score. | Verified locally |
| 8. Retrieve diverse earlier passages using full-passage signals | Retrieval helper and tests cover multiple sections, selected characters, chapter exclusion and diverse samples. | Verified locally for tested cases |
| 9. Show coverage, attribution, evidence and limitations while preserving edits/results on failures | Frontend unit and E2E tests cover partial, insufficient, retry, decisions, and long passage states. | Verified locally |
| 10. Release DB transactions for provider calls; handle malformed, temporary and partial failures; cache only validated complete results | Orchestration and review services implement these paths; API and unit tests cover them. | Verified locally for simulated failures; provider behavior unmeasured |
| 11. Add the specified synthetic cases and run local CI equivalents | Voice corpus has 16 cases including long, narrator, shared-name, intentional-change, insufficient-evidence and fabricated-citation cases. Backend, frontend, E2E and container checks have been run locally. Real provider calls were explicitly declined. | Partial: live quality gate absent |

## Latest local checks

- Backend Docker Compose Local: **3,237 passed, 1 skipped** on the latest rebuilt API image, including character embedding, freeze-path, recurring unnamed-role discovery, classification, cast-promotion review, database-backed role resolution, voice baseline storage fallback, character navigation, exact chapter-storage-key, read-only report fallback, and staged-rebuild recovery tests. Ruff lint and format checks pass.
- Focused checks on rebuilt images passed **64 Voice Review tests**, the request-ID logging regression, the character navigation API regression (including `id,name,aliases,status`), and **105 ingestion, reprocessing, and Voice Review tests** after the shared source-loader fix.
- Character embedding now runs before chapter extraction records are replaced. The provider call uses an independent usage session, with no chapter transaction open; resolution consumes the precomputed vectors. Unanchored proposals are skipped. Focused tests check that embedding failure leaves existing records untouched, freeze during provider work avoids replacement, and freeze after replacement rolls back staged writes. Source-anchored proposals that resolution later holds for review may still use embedding tokens.
- Fresh offline character evaluation in Docker Compose Local: 34 cases; 58/58 named hints; 65/65 model-supplied gold names survived cleaning; 17/17 joint identity cases preserved; 13/65 gold candidates immediately auto-save eligible; 0/12 unlabeled name hints auto-save eligible. The role review safeguard reduced automatic eligibility by four. These figures estimate conditional gate behavior, not live precision or recall.
- A fresh gate breakdown on the same 34 synthetic cases found 36/65 correct names locally accepted, 29/65 sent to verifier review, and 0 rejected. Of the 36 local accepts, 13 were auto-save eligible and 23 remained held; the principal hold reasons were insufficient cross-chapter support (15) and single-token ambiguity (10). The separate 12 unlabeled hints included four local accepts but zero final auto-save eligibles. The resolver combines verified exact-name candidate evidence from later chapters, with a database-backed promotion test. This short-text corpus cannot establish how often that path promotes real-book characters, so the gate thresholds were not relaxed merely to raise the synthetic score.
- The read-only character report now verifies source through the processing loader. A stale recorded key falls back to the deterministic chapter key; the report tests confirm both successful hash comparison and absence of manuscript text in output. The schema requires a non-null chapter key, so a missing-key fallback is tested at the loader level rather than through an impossible database row. The focused report and loader suite passed **42 tests** on a rebuilt local API image.
- Frontend unit tests, type check, lint, build, four E2E shards, authenticated audit and public audit passed on the current frontend source. The E2E-generated `next-env.d.ts` change was restored after the earlier host run.
- Fresh frontend rerun on 2026-10-29: type check and lint passed. Vitest initially failed before collecting tests because the Codex Windows sandbox denied atomic renames in its temporary cache directory; rerunning with `TEMP` and `TMP` scoped to ignored `frontend/node_modules/.vitest-tmp` passed **281 files and 1,534 tests** under host Node 25.
- Docker Desktop recovered. The production image built successfully with the pinned `frontend/Dockerfile` Node **24.20.0**, including compilation and generation of 107 static pages. The builder image then ran the exact frontend CI scripts under the same Node 24 environment: **281 files and 1,534 tests passed**, type check passed, and ESLint passed. A disposable E2E image combined official Node 24.20.0 with Playwright 1.55.1 and Chromium. All six GitHub E2E commands passed in isolated containers: shard 1 **107**, shard 2 **107**, shard 3 **106**, shard 4 **106**, author audit **1**, and public audit **1**. This closes the Node version gap in local E2E evidence, though a local run cannot guarantee hosted Actions behavior. No tracked frontend files changed during these checks.
- Fresh backend static CI checks after the staged-rebuild edits: Ruff lint passes, Ruff format reports 819 files already formatted, the pricing catalog is synced, the production service contract is complete, and the repository credential scan passes. These do not replace the database-backed test and migration gates.
- The manuscript edit-path review found that normal chapter saves recheck the editor rebuild marker after locking the book row, while scene create/update/delete/reorder/restore routes reject an active editor rebuild. Chapter deletion is deliberately allowed and invokes the cancellation path. The new chapter snapshot includes content version, structure version, number, title, storage key, and word count so cancellation cannot restore old analysis onto a reorganized chapter. Database-backed regressions for failure and cancellation passed in the full backend suite.
- Fresh disposable local Postgres migration chain reached the new head `20261029_rebuild_chapter_snapshot`; `alembic check` reported no drift. The `book_data_generations.chapter_state_snapshot` column existed at head, disappeared on downgrade by one revision while the table remained, and reappeared on upgrade to head. This verification used the explicitly identified disposable Docker Compose Local `lorevia_test` database, never a remote database. The pytest fixture drops application tables but leaves `alembic_version`, so the migration was tested after rebuilding the local test schema from base rather than trusting its marker alone. Remote migrations have not been run.
- Three unpublished migrations exist: Voice Review adds one backend-only decision table; the Vault Note follow-up intentionally removes an obsolete path-only unique constraint after checking the source-aware constraint exists; the staged-rebuild follow-up adds a nullable JSONB snapshot column. The full migration chain and the staged-rebuild migration's downgrade/reapply were tested on the disposable local database. The older two migrations were reviewed previously; their individual downgrade paths were not rerun during this audit pass.
- Current frontend production image built and passed the cached offline HIGH/CRITICAL Trivy image gate. The rebuilt backend API and worker images both passed Trivy v0.74.0's cached HIGH/CRITICAL image gate with zero findings and the exact offline-tokenizer smoke check from CI. Nginx and Redis image gates passed in the prior local CI simulation. The cached vulnerability database does not prove a future GitHub scan with updated advisory data will pass.
- Trivy v0.74.0 also scanned the current source checkout after excluding local ignored caches, build output and secret-bearing env files. The HIGH/CRITICAL filesystem vulnerability gate found **0** findings with the cached database; the configuration gate found **0** findings across five detected config files. The filesystem scan suppresses development/test dependencies by default, matching the CI action's normal Trivy behavior. This does not replace a future GitHub run with refreshed advisory data.

## Outstanding proof before marking the goal achieved

1. Obtain predictions from the actual extraction and Advisor pipeline on the synthetic corpus, then evaluate character precision/recall, identity merges, supported profile and relationship claims, continuity findings, latency and cost against the rollout thresholds. The user's offline-only constraint currently prevents provider-backed measurements.
2. Inspect a current-code read-only diagnostic for the Meta project's stored manuscript and candidate dispositions. The only available production report was generated before this code is deployed; no customer manuscript is available in the local checkout.
3. Preview and run targeted reprocessing of the Meta project only after the user accepts its preflight and deploys the verified version. Preserve author edits and decisions and compare the new cast, relationships, evidence and Advisor results with the previous report.
4. Recheck the eventual PR diff and migrations before push or deployment. The checkout currently contains uncommitted work; nothing here has been deployed to the VPS.
5. Before using Meta reprocessing, review its preflight against the deployed source and chapter state. The staged-rebuild recovery bug has been repaired locally: `prepare_rebuild` snapshots prior chapter state and source identity; failure restores unchanged chapters after a partial staged result; cancellation after an edit or reorganization leaves changed chapters pending while restoring untouched chapters; finalized generations cannot be overwritten by stale cancellation. The full backend suite passed **3,237 tests with 1 skipped**, including the database-backed recovery regressions, and the new migration was verified by a real local rollback/reapply. The remaining check is the actual Meta preflight and reprocess after deployment, which this audit cannot perform against the current VPS version.

## Preproduction code review, 2026-10-29

- The diff changes no auth dependency, login/session route, frontend auth store, Nginx configuration, Compose file, or deployment script. The new reprocess preflight uses `get_current_user` and `get_owned_book`; the new voice-decision route uses `get_current_user` and the existing book AI-scan access check. The Advisor scan worker checks that the loaded book belongs to the enqueued user. This is evidence against a direct auth regression, not proof of live sign-in behavior.
- The three new migrations are sequential. Voice decisions add a backend-only table; the Vault revision drops only the obsolete path-only uniqueness constraint after verifying the source-aware constraint exists; the chapter-snapshot revision adds a nullable JSONB column. Local full-chain upgrade and the last revision's downgrade/reapply passed. The Vault revision has an intentional `drop_constraint`, so the remote migration safety guard may require an exact reviewed revision allowlist. The production Alembic revision and constraint state are not yet known.
- **Cross-version compatibility:** the new backend requires a preflight fingerprint for full-manuscript reprocessing. The currently deployed frontend's POST body does not send one, so that action will return HTTP 409 between a backend-first VPS deploy and promotion of the matching Vercel frontend. Promoting the new frontend first makes its new preflight request unavailable on the old backend. This is a controlled release-window risk; do not claim a seamless zero-downtime rollout. A coordinated maintenance window or a separately shipped compatibility bridge is needed before production promotion.
- `deploy.sh` takes a `pg_dump` backup, builds images, stops application services, runs release data preflight and Alembic upgrade, verifies schema, then restarts the stack and checks health. It requires an explicit remote `ALEMBIC_DATABASE_URL` and `ALEMBIC_CONFIRM_REMOTE`. It deploys `main` by default; the public frontend is deployed separately on Vercel. Neither current VPS/Vercel release state nor their exact matching commit is verified here.
- **Release decision:** the local code is a tested candidate, but it is not a deployable release artifact yet. The checkout is uncommitted and unpushed, the production migration target has not been inspected, and the frontend/backend cross-version window needs an explicit plan. Treat production promotion as NO-GO until those are resolved; do not mistake the local test pass for a production GO.
