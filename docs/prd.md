# LoreVia Product Requirements Document

Last updated: 2026-06-04

## 1. Product Summary

LoreVia is an AI-powered manuscript intelligence platform for fiction authors. It helps writers upload, draft, revise, analyze, and maintain continuity across novels, series, screenplays, character arcs, plot threads, world-building material, and collaborator feedback.

The product is not a generic document chatbot. LoreVia is organized around the author workflow: manuscript ingestion, chapter-aware intelligence, character and relationship tracking, spoiler-safe recall, grounded Q&A, drafting support, export tools, and optional public or collaborator surfaces.

## 2. Problem Statement

Long-form fiction projects become difficult to manage as manuscripts grow. Authors lose track of character state, unresolved plot threads, relationship changes, world rules, timeline details, and cross-book continuity. Generic writing tools can assist with local prose but do not maintain structured story memory across chapters, drafts, and series.

LoreVia solves this by turning manuscripts and world documents into a structured, searchable, spoiler-aware intelligence layer that supports both reading and author revision workflows.

## 3. Goals

- Help fiction authors preserve continuity across long manuscripts and series.
- Provide grounded answers, summaries, search results, and advisor feedback based on manuscript evidence.
- Build evolving character, relationship, plot, world-building, and timeline intelligence from uploaded or drafted content.
- Support author drafting workflows directly inside the product, including rich text editing, chapter versions, scenes, reports, and export.
- Keep reader-facing intelligence spoiler-safe according to chapter progress and reading state.
- Provide reliable asynchronous processing for extraction, analysis, embeddings, and intelligence tasks.
- Support subscription-based access controls, rate limits, and billing foundations.
- Keep operational behavior suitable for VPS deployment with local Docker Compose parity.

## 4. Non-Goals

- LoreVia is not a replacement for a human editor or beta reader.
- LoreVia does not guarantee factual copyright ownership or legal publication clearance.
- LoreVia should not expose unpublished private manuscripts publicly unless explicit public-reading controls are enabled.
- LoreVia should not rely on a single large prompt as the only source of story memory.
- LoreVia should not treat stopwords or weak entity signals as hard exclusions when character evidence exists.

## 5. Target Users

### 5.1 Primary Persona: Fiction Author

An author drafting or revising a novel, screenplay, or series who needs help tracking continuity, character state, plot promises, world rules, and manuscript quality.

Primary jobs:

- Upload or paste manuscript content.
- Continue drafting in an author workspace.
- Review chapter consistency and continuity issues.
- Track characters, relationships, plot threads, world elements, and timelines.
- Export manuscript and reference materials.

### 5.2 Secondary Persona: Returning Reader Or Collaborator

A reader, reviewer, or collaborator who needs spoiler-safe context while reading a manuscript.

Primary jobs:

- Resume reading with a recap.
- Inspect character and relationship context up to the current chapter.
- Search prior text without seeing future spoilers.
- Save notes, quotes, and feedback.

### 5.3 Secondary Persona: Series Author

An author working across multiple books in a shared series.

Primary jobs:

- Group books into a series.
- Compare characters and world elements across books.
- Generate series-level bibles and continuity analysis.
- Ask cross-book advisor questions.

### 5.4 Internal Persona: Admin / Operator

An authorized operator responsible for usage visibility, rate limit overrides, queue awareness, and safe production operation.

Primary jobs:

- Inspect metrics and queue status.
- Manage per-user rate limit overrides.
- Verify billing and subscription behavior.
- Maintain safe deployment and migration practices.

## 6. User Journeys

### 6.1 Manuscript Upload To Intelligence Workspace

1. User registers or logs in.
2. User uploads a supported file or imports pasted manuscript text.
3. Backend validates format, size, metadata, tier limits, and storage requirements.
4. Background workers parse the file into chapters, chunks, source text, media, and optional scenes.
5. Workers generate embeddings, summaries, character profiles, relationships, plot threads, world elements, and progress notifications.
6. User enters the book workspace and sees processing state, chapter navigation, characters, graphs, summaries, search, timeline, and advisor tools.

### 6.2 Author Drafting And Revision

1. User opens the manuscript workspace.
2. User edits chapter content, book-level drafts, scenes, notes, front matter, and workspace settings.
3. User runs readability, continuity, voice, synopsis, prose tightening, or editorial review tools.
4. User restores prior chapter versions if needed.
5. Derived intelligence is regenerated when manuscript content changes.
6. User exports manuscript, continuity report, character cards, or character bible.

### 6.3 Spoiler-Safe Reading

1. User opens a book chapter.
2. Reader progress determines the safe chapter boundary.
3. User taps text, asks a question, searches, views a graph, or requests recall.
4. Backend returns only spoiler-safe data up to the allowed chapter.
5. User saves notes or quotes with chapter context.

### 6.4 Series Continuity

1. User creates a series and attaches books in order.
2. User runs series-level advisor, bible generation, world analysis, or cross-book matching.
3. System compares characters, wiki entries, and world elements across books.
4. User reviews likely matches, continuity gaps, and unresolved cross-book issues.

## 7. Current Product Scope

### 7.1 Account And Authentication

Requirements:

- Users can register with legal acceptance metadata.
- Users can log in with email/password.
- Users can authenticate through Supabase OAuth where configured.
- Users can refresh sessions, log out, reset passwords, and complete one-time username setup.
- Sessions use httpOnly cookies, refresh token rotation, Redis-backed refresh sessions, and token versioning.

### 7.2 Library And Upload

Requirements:

- Users can list books with covers, processing state, archive/hidden state, stats, mode, work type, and series metadata.
- Users can upload PDF, EPUB, DOCX, DOC, and text-like manuscripts.
- Users can paste/import manuscript text and append chapters to an existing book.
- Upload/import flows support reader mode, author mode, prose, screenplay/Fountain-style works, cover options, tags, genre, and series assignment.
- Processing progress must be visible and refreshable from the frontend.
- Archive and hide controls must preserve data while removing books from active workflows.

### 7.3 Parsing, Chunking, And Storage

Requirements:

- Backend parses source files into chapters, chunks, source text, media references, and optional screenplay structures.
- PDF parsing handles heading detection, repeated header/footer cleanup, page artifact scrubbing, source chapter number extraction, diagnostics, and cover extraction.
- Storage supports local filesystem and S3/R2-compatible storage through a shared abstraction.
- Asset URLs must avoid exposing raw storage internals and should use signed or tokenized access when needed.

### 7.4 Background Processing

Requirements:

- Celery workers process extraction, analysis, embedding, and intelligence queues separately.
- Processing is cancellation-aware and checks hidden/canceled book state.
- Workers generate summaries, embeddings, character profiles, relationships, plot threads, world elements, voice profiles, and notifications.
- Processing progress must update book and writer workspace state.
- Worker tasks must be retryable and observable through logs and queue metrics.

### 7.5 Character Intelligence

Requirements:

- The system extracts characters, aliases, roles, traits, descriptions, motivations, fears, archetypes, arcs, growth events, evidence, and voice indicators.
- Character visibility must use `character_visibility_score()` and `VISIBILITY_THRESHOLD`, not hard stopword gates.
- Character profiles support merging, deletion, editing in author mode, sharing by token, and export.
- Character state snapshots must support spoiler-safe views by chapter.
- Character chat responses should be grounded in the profile and relevant manuscript context.

### 7.6 Relationship, Timeline, Plot, And Recall

Requirements:

- The system extracts relationship records between characters with status, description, confidence, evidence, and chapter range.
- Relationship graph endpoints aggregate duplicate nodes and spoiler-safe edges.
- Relationship evolution views show changes over time.
- Timeline views combine events, character appearances, plot threads, and relationship markers.
- Plot threads include type, importance, status, character links, notes, and chapter context.
- Recall generates a "previously on" recap from recent summaries, progress, active characters, and open threads.

### 7.7 Reader Intelligence

Requirements:

- Reader chapter pages support progress tracking, smart tap context, quote capture, summary panels, media, and chapter navigation.
- Semantic search and thematic search must honor the current spoiler boundary.
- Grounded Q&A must include citations or cited source context where available.
- Smart tap should prefer character context for recognized names and fall back to semantic or lexical search for other text.
- Chapter read state must drive spoiler-safe intelligence boundaries.

### 7.8 Author Manuscript Workspace

Requirements:

- Authors can edit manuscript chapters, full-book drafts, standalone scenes, notes, front matter, chapter metadata, and workspace settings.
- Rich text editing preserves analysis-friendly plain text and display-friendly HTML.
- Chapter versioning supports snapshot, list, inspect, and restore.
- Restoring a chapter version must purge stale derived intelligence so it can be regenerated.
- Novel scenes can be created, updated, deleted, listed, and inserted into chapters.
- Screenplay manuscripts support scene headings, dialogue, action, transitions, shots, parentheticals, and statistics.

### 7.9 Advisor And Editorial Tools

Requirements:

- Story advisor chat supports book and series context.
- Advisor responses use intent classification, semantic retrieval, story context, recent chat history, and cached results where appropriate.
- Proactive suggestions identify trait contradictions, dropped threads, long-absent characters, high-importance arcs, unresolved clues, and underused minor characters.
- Editorial review, inline continuity review, prose tightening, synopsis generation, voice consistency review, readability metrics, emotional arc, and pre-writing checks are available from author workflows.
- Continuity reports can be exported in supported document formats.

### 7.10 World-Building And Wiki

Requirements:

- Authors can upload, replace, read, update, and delete world-building documents.
- World documents are parsed into structured elements such as places, organizations, objects, events, concepts, eras, and characters.
- The system detects gaps, conflicts, missing-in-story elements, and world/story mismatches.
- Integration mapping suggests ways to use underdeveloped world elements.
- World logic queries return cited answers and simulation-style reasoning where applicable.
- World wiki entries can be generated and compared across books.
- Canon overrides let authors define preferred identities and aliases.
- Series-level world analysis compares world-building across books.

### 7.11 Notes, Quotes, Vaults, And Exports

Requirements:

- Users can save book notes, chapter notes, quotes, vault notes, tags, backlinks, and generated/user note metadata.
- Vault notes support ZIP import/export, folder tree browsing, graph relations, and generated character-bible note previews.
- Export studio supports manuscripts as PDF, DOCX, EPUB, and vault archives.
- Character card and character bible exports support Markdown, PDF, DOCX, and vault formats.
- Exported artifacts should include useful metadata and preserve source context where possible.

### 7.12 Series Management

Requirements:

- Users can create series, attach/detach books, set book order, set status, view series lists, and use series-level advisor workflows.
- Series features power character bible generation, cross-book continuity checks, world analysis, and cross-book wiki matching.

### 7.13 Public, Collaboration, And Beta Reading

Requirements:

- Public book and chapter routes exist but must remain guarded by explicit feature flags until public reading is intentionally enabled.
- Public assets such as covers, media, and character cards must use tokenized access.
- Collaborator and beta-reading surfaces should respect author intent, invitation state, launch flags, and manuscript privacy.
- Public forum writes must remain gated while launch status requires it.

### 7.14 Billing, Limits, And Admin

Requirements:

- Users can create Paddle checkout links and open billing portals when Paddle is configured.
- Webhooks verify signatures, deduplicate events, and update subscription rows.
- Tier limits govern books, uploads, summaries, questions, advisor messages, exports, world documents, and other resource-heavy actions.
- Admin users can inspect metrics, queue depth, and per-user rate limit overrides.
- Billing-disabled states must be handled gracefully in local or unconfigured environments.

### 7.15 Notifications And Email

Requirements:

- Users receive notifications for processing state, detected characters, readiness, and other important events.
- Users can list notifications, view unread counts, mark one read, and mark all read.
- Email delivery supports onboarding, password reset, processing complete, subscription confirmation, and character-related emails.
- Email delivery must be optional and failure-tolerant for local development.

## 8. Non-Functional Requirements

### 8.1 Security

- Auth cookies must be httpOnly and configured for the active environment.
- Session refresh must rotate refresh tokens and support revocation.
- API errors must be sanitized before reaching clients.
- Private manuscripts, exports, media, and covers must not expose raw storage paths.
- Rate limits must protect expensive AI, upload, and auth endpoints.
- Public content must be explicit opt-in and guarded by launch flags.
- Migration tooling must avoid accidental production database writes or destructive operations.

### 8.2 Privacy

- Manuscript content, world documents, notes, and collaborator feedback are private by default.
- Public and collaborator access must require explicit author action.
- Sensitive configuration belongs in environment files and must not be committed or modified by routine development work.

### 8.3 Reliability

- Long-running ingestion and intelligence tasks must run asynchronously.
- Worker progress must be persisted so frontend polling can recover after refresh.
- Redis-backed caching should reduce duplicate expensive work without returning stale private data across users or spoiler boundaries.
- Webhook processing must be idempotent.
- Processing tasks should handle malformed files, missing summaries, partial extraction, and retryable AI failures.

### 8.4 Performance

- Reader and workspace pages should avoid unnecessary repeated GET requests through frontend cache/deduplication.
- Semantic search and graph endpoints should cache common results by user/book/query/chapter boundary where safe.
- Large manuscripts should process incrementally with early chapter availability where possible.
- Upload and parsing should enforce file size and content validation limits.

### 8.5 Accessibility And UX

- Core workflows should remain usable from the authenticated dashboard without relying on marketing pages.
- Reader controls should support theme, font, font size, and reading mode preferences.
- Long-running states must communicate progress, pending work, and completion.
- Error states should explain user action without exposing internals.

### 8.6 Operations

- Local development and testing should use Docker Compose Local.
- Production should be treated as a VPS deployment unless explicitly changed.
- Deployments should use the repo deployment flow that includes backups, Alembic upgrade, and post-migration verification.
- Backend tests should run against the local Compose API service and test database.

## 9. Data Model Domains

Core domain areas represented in the backend include:

- Users, auth, sessions, subscriptions, and rate limit overrides.
- Books, chapters, chunks, reading progress, tags, covers, media, archive/hidden state, and writer workspace state.
- Characters, aliases, state snapshots, relationships, voice profiles, and character events.
- Summaries, plot threads, story events, reports, intelligence artifacts, and advisor chat state.
- World documents, world elements, wiki entries, canon identities, world notes, and world analysis.
- Notes, vault notes, note links, backlinks, quote entries, and export metadata.
- Series and series-book membership.
- Beta reading, collaboration, public content, moderation, notifications, and admin metrics.

## 10. Success Metrics

Product metrics:

- Time from upload to first usable chapter intelligence.
- Percentage of processed books with generated summaries, character profiles, and relationship graph data.
- Author retention after first manuscript upload.
- Number of active books or manuscripts per author.
- Frequency of advisor, search, report, export, and manuscript workspace usage.
- Percentage of users who return to a draft after receiving recall or continuity output.
- Export completion rate for manuscript, character card, bible, and continuity report outputs.

Quality metrics:

- Spoiler-boundary violations reported or detected.
- Character duplicate merge rate and false-positive character visibility rate.
- Grounded Q&A citation coverage.
- Processing failure rate by file type.
- Worker retry rate and median queue latency.
- Cache hit rate for expensive intelligence endpoints.

Business metrics:

- Free-to-paid conversion.
- Subscription renewal and cancellation rates.
- Tier-limit upgrade prompts accepted.
- Billing webhook success and reconciliation accuracy.

## 11. Key Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Spoiler leakage across reader boundaries | High trust loss | Enforce chapter gates in every reader intelligence endpoint and cache key. |
| Character false positives or missed characters | Poor intelligence quality | Keep visibility scoring evidence-based; avoid hard stopword gates. |
| Long processing times for large manuscripts | User abandonment | Show progress, process early chapters eagerly, and make jobs retryable. |
| Stale intelligence after manuscript edits | Incorrect advisor/report output | Purge derived data on restore or content mutation, then regenerate. |
| Accidental public exposure | Severe privacy issue | Keep public mode feature-flagged and tokenized; private by default. |
| Production migration mistakes | Data loss or downtime | Use explicit Alembic target URLs, destructive-operation checks, backups, and VPS-safe deploy flow. |
| AI cost spikes | Margin risk | Enforce tier limits, cache expensive calls, rate-limit endpoints, and queue work. |
| Billing webhook duplication or failure | Incorrect entitlement state | Verify signatures, deduplicate in Redis, and persist subscription updates. |

## 12. Roadmap Themes

Near-term priorities:

- Improve manuscript workspace stability and derived-intelligence regeneration after edits.
- Tighten vault note import/export and character bible workflows.
- Strengthen spoiler-safe reader intelligence tests and cache-boundary coverage.
- Improve upload diagnostics and failed-processing recovery.
- Expand focused frontend E2E smoke coverage for upload, manuscript, reader, export, and billing flows.

Medium-term priorities:

- Improve cross-book continuity workflows for series authors.
- Expand world-building conflict resolution and canon override UX.
- Add deeper collaborator and beta-reading workflows behind explicit author controls.
- Improve admin visibility into worker queues, cost drivers, and failed jobs.
- Refine subscription tiers and usage analytics.

Long-term priorities:

- Public reading and public writer surfaces once privacy, moderation, and launch controls are fully verified.
- More advanced manuscript planning workflows for scenes, corkboards, outlines, and screenplay modes.
- Higher-quality retrieval evaluation and automated regression suites for grounded answers.
- Richer export presets for publication and vault ecosystems.

## 13. Acceptance Criteria

The product is functioning as intended when:

- A new user can register, upload or import a manuscript, and see processing progress.
- The manuscript is parsed into chapters and searchable chunks.
- Summaries, character profiles, relationship graph data, and reader search become available after processing.
- Reader-facing views honor chapter progress and do not expose future content.
- Author-mode manuscript edits persist and can trigger refreshed intelligence.
- Advisor and Q&A responses are grounded in retrieved manuscript or series context.
- Notes, quotes, exports, and vault workflows preserve source metadata.
- Billing and tier limits are enforced when configured and degrade cleanly when disabled locally.
- Public access remains disabled unless explicitly enabled.
- Backend, frontend unit, and frontend E2E smoke tests cover critical flows and pass in local non-production environments.

## 14. Open Questions

- Which public reading and writer-profile features should be enabled first, and under what moderation requirements?
- Which subscription tiers should map to each heavy AI feature after real usage cost data is available?
- What precision target is acceptable for character extraction before exposing more automatic merge behavior?
- Which collaborator workflows are most important: beta feedback, line comments, chapter approvals, or guided review forms?
- Should world-building and manuscript intelligence share one unified canon graph, or remain separate with explicit cross-links?
- What minimum export quality bar is required for publication-facing PDF/EPUB outputs?

