# LoreVia Feature Inventory

Generated on 2026-05-03 from a first-pass code inventory and a second-pass coverage check across backend routes, models, schemas, utilities, engines, workers, parsers, tests, frontend pages, frontend components, API clients, stores, and hooks.

## Scope And Method

This document catalogs frontend and backend features found in the repository. It is organized by product capability rather than by file tree so that each feature can be understood from the user's point of view and from the implementation design.

The first pass inspected:

- Backend app entry points, API routers, route handlers, dependencies, models, schemas, services, utilities, engines, parsers, workers, tasks, migrations, and tests.
- Frontend Next.js routes, page modules, shared components, API clients, hooks, stores, constants, types, PWA files, and layouts.
- Existing docs, Docker/runtime files, and package manifests to identify architecture and operational features.

The second pass compared this inventory against:

- Every backend route module mounted by `backend/app/api/v1/router.py`.
- Every backend support layer under `backend/app/models`, `backend/app/schemas`, `backend/app/services`, `backend/app/utils`, `backend/app/engine`, `backend/app/parsers`, and `backend/app/workers`.
- Every frontend route under `frontend/src/app`, plus shared components under `frontend/src/components` and API clients under `frontend/src/lib/api`.
- Tests under `backend/tests` to confirm intended feature boundaries and critical behavior.

## High-Level Architecture

LoreVia is a manuscript intelligence platform for fiction authors. The core product is an author workspace for drafting, revision, continuity, world-building, export, and invited collaborator review when authors need outside feedback.

### Frontend Architecture

The frontend is a Next.js 15 and React 19 application. Routes are grouped into authentication, dashboard, reader/book workspace, and public chapter views. It uses Tailwind for styling, Zustand for local auth/preferences/book-mode state, axios for API transport, lightweight in-memory GET caching for selected calls, Cytoscape for graph visualization, PostHog for analytics, and Supabase for OAuth.

Design-wise, the frontend is organized around workspaces rather than marketing pages. The main product surfaces are:

- Library and series dashboards.
- Per-book collaborator reading and review workspace.
- Per-book author manuscript workspace.
- Character, graph, timeline, search, summary, foreshadowing, plot, world, export, notes, and advisor tool pages.
- Shared interactive components for reading, rich text editing, graph exploration, notes, exports, notifications, and upload/import workflows.

The axios client automatically attaches credentials, avoids incorrect JSON headers for `FormData`, refreshes expired sessions through `/auth/refresh`, clears stale auth state on unrecoverable 401s, and routes users back to login.

### Backend Architecture

The backend is a FastAPI service using SQLAlchemy 2.x async sessions, PostgreSQL with pgvector, Redis, Celery workers, OpenAI/Gemini LLM calls, Paddle billing, Supabase OAuth verification, object storage via S3/R2 or local filesystem storage, Sentry, and structured JSON logging.

The backend API is mounted under `/api/v1` and is split by domain:

- Auth and account.
- Books, library, uploads, manuscript import/export, series, notes, character cards, and author utilities.
- Reader intelligence.
- Character state.
- Story advisor and writing intelligence.
- World-building intelligence.
- Billing and webhooks.
- Notifications.
- Admin controls.
- Public reading endpoints, with public forum writes intentionally gated by launch status.

Core business logic lives outside route files in services, utilities, engines, parsers, and workers. Route modules primarily validate access, call helpers/services, and return API schemas.

### Data And Processing Flow

1. A user uploads or imports a book/manuscript through the frontend.
2. The backend validates format, size, content type, access tier, cover data, metadata, and optional series/manual settings.
3. Source files are stored in S3/R2 or local storage.
4. Celery extraction workers parse the source, create chapters/scenes, chunk text, embed chunks, extract characters and relationships, create state snapshots, compute voice profiles, store media markers, and update processing progress.
5. Analysis workers generate detailed, short, and key-point summaries; extract plot threads; link events to characters; and ingest world-building elements.
6. Reader and author endpoints expose spoiler-gated search, summaries, graphs, timelines, context, advisor answers, manuscript reports, exports, and world-building analysis.
7. Redis caches expensive answers, graph/search results, grounded QA, public content, refresh sessions, password reset tokens, webhook idempotency, and token versions.

### Security, Reliability, And Operations

The backend includes httpOnly auth cookies, access and refresh tokens with token versioning, refresh session revocation, password reset token storage in Redis, CORS/host controls, secure response headers, sanitized error responses, request IDs, JSON logs, optional Sentry, Redis-backed rate limits, subscription-aware feature gates, webhook idempotency, storage key isolation, and migration safety utilities.

The migration layer includes explicit Alembic safety utilities that detect non-local database targets and destructive migration operations. The repository instructions also require explicit database URL confirmation for remote migrations.

## Feature Catalog

### 1. Account, Authentication, And Identity

**What it does:** Users can register, log in, authenticate with Supabase OAuth, refresh sessions, log out, reset passwords, retrieve their account profile, choose a reading mode, and set a one-time username.

**What makes it unique:** Registration enforces legal acceptance metadata, strong password rules, username uniqueness, onboarding email, and cookie-based session issuance. Supabase OAuth can create users when terms are accepted, while normal email/password auth and OAuth share the same backend user model.

**How it is designed:** Backend route handlers in `auth.py` call security helpers, Redis token/session helpers, email services, and SQLAlchemy user models. Frontend auth pages and stores manage login/register/callback/username completion and persist lightweight client auth state.

### 2. Session Security And Password Reset

**What it does:** Refresh tokens are rotated and backed by Redis session IDs. Logout bumps the user's token version and clears cookies. Forgot/reset password creates Redis-backed reset tokens and sends reset email.

**What makes it unique:** Token versioning gives the backend a central kill switch for all outstanding access/refresh tokens for a user. Password reset delivery can expose a local reset URL only in local mode when email delivery fails.

**How it is designed:** `core/security.py` creates and decodes JWTs, `core/redis.py` stores refresh sessions and password reset tokens, and `utils/auth_cookies.py` sets/clears secure cookies.

### 3. Legal, Compliance, And Static Product Pages

**What it does:** The frontend includes terms, privacy, EULA, refund, contact, status, and global error pages. Registration links to legal terms and compliance context.

**What makes it unique:** Legal acceptance is not just presentation; the backend records the terms version, privacy version, age confirmation, and acceptance IP/user agent.

**How it is designed:** Static pages live under `frontend/src/app`. Legal fields are part of auth schemas and the user model.

### 4. Library Dashboard

**What it does:** Users can view their books, processing state, covers, stats, archive/hidden status, and upload/import entry points.

**What makes it unique:** The library polls processing books and treats uploaded reader books, author manuscripts, screenplay works, series books, and hidden/archive states as one shelf system.

**How it is designed:** The frontend library page calls `booksApi.list`, `booksApi.stats`, upload flows, archive/hide endpoints, and cover URL endpoints. The backend serializes each book through `book_out`, including progress, cover URLs, mode, work type, and series metadata.

### 5. Upload And Import Studio

**What it does:** Users can upload supported files, paste manuscript text, add chapters to an existing book, choose reader or author mode, set genre/tags, attach a book to a series, preserve source chapter numbers, select manual/automatic cover handling, and monitor progress.

**What makes it unique:** The import flow supports both reader ingestion and author drafting. It handles normal prose, markdown/text/html-like manuscript imports, PDFs, EPUBs, DOCX/DOC, and screenplay/Fountain-style files.

**How it is designed:** `UploadModal.tsx` manages client-side wizard state and progress. Backend upload/import endpoints validate file size, magic bytes, cover format, text safety, work type, book mode, tags, series access, and tier limits. Ingestion helpers create processing plans and dispatch Celery tasks.

### 6. Book Parsing And Chapter Detection

**What it does:** Uploaded books are parsed into chapters, source text, media references, and optional screenplay scenes.

**What makes it unique:** PDF parsing includes heading detection, repeated header/footer removal, page artifact scrubbing, permissive fallback heading detection, source chapter number extraction from digits, words, ordinals, roman numerals, and letters, parse diagnostics, image marker preservation, and first-page cover extraction.

**How it is designed:** Parser modules handle EPUB, PDF, chunking, and screenplay parsing. `book_utils.py` normalizes imported chapters, splits long documents, detects screenplay files, and serializes manuscript text/html content.

### 7. Cover Processing And Asset URLs

**What it does:** Books can have uploaded covers, extracted PDF covers, processed covers, tokenized public cover URLs, and forced cover reprocessing.

**What makes it unique:** Cover processing uses strict content validation and can serve short-lived asset URLs without exposing storage internals.

**How it is designed:** `cover_processor.py`, `book_utils.py`, storage helpers, and asset token helpers create, process, store, and authorize cover access. Frontend cover cards use smart fallback rendering when cover assets are missing.

### 8. Copyright And ISBN Compliance

**What it does:** Upload flows and compliance pages can check ISBN/copyright metadata and show whether public distribution should be allowed.

**What makes it unique:** Public PDF handling includes ISBN/copyright checks before public availability, and the frontend has a per-book compliance page.

**How it is designed:** ISBN extraction and lookup helpers live under `utils/external` and `utils/compliance`. The book model stores ISBN, copyright status, copyright metadata, and public flags.

### 9. Background Processing Pipeline

**What it does:** Celery workers process uploaded books, analyze chapters, generate embeddings, run intelligence tasks, update progress, and send notifications/emails.

**What makes it unique:** Processing is chapter-aware and cancellation-aware. It updates writer workspace progress with ETA and queue timing, eagerly processes early chapters, defers the rest, and consolidates characters as more evidence arrives.

**How it is designed:** `workers/celery_app.py` defines queues, rate limits, request ID propagation, retries, and task time limits. Extraction and analysis consumers coordinate parsing, embeddings, summaries, character extraction, relationships, world ingestion, and notifications.

### 10. Character Extraction

**What it does:** The platform extracts characters, aliases, roles, trait states, motivations, fears, archetypes, arcs, growth events, evidence, relationships, and chapter-specific state snapshots.

**What makes it unique:** Character visibility is scored rather than hard-gated by stopwords. NER, profile evidence, mention support, name shape, and story evidence can override soft penalties. The system also computes subtype scores such as stoic, mentor, cynical, loner, charismatic, intelligent, naive, and others.

**How it is designed:** `engine/character/extractor.py` calls LLM extraction and augments with named mention detection. `entity_filters.py` computes visibility/subtype scores. `profile_builder.py` merges traits. `deduplicator.py` resolves aliases and similar names using normalized keys and embeddings.

### 11. Character Profiles And Cards

**What it does:** Users can view rich character profiles, edit author-mode character data, delete characters, merge duplicates, share tokenized character pages, and export character cards.

**What makes it unique:** Profiles combine physical traits, personality, motivations, fears, relationships, growth events, subtype scores, voice data, evidence, and spoiler-aware first/last seen metadata.

**How it is designed:** Backend character endpoints and book utility helpers build card payloads. `CharacterCard.tsx` renders compact and full editable cards. Export helpers generate Markdown, PDF, DOCX, and Obsidian-friendly character artifacts.

### 12. Character State And Spoiler Control

**What it does:** Reader endpoints return character states as of a selected chapter rather than always exposing the latest author/full-book knowledge.

**What makes it unique:** The same character can have evolving spoiler-safe snapshots, allowing the reader UI to explain a character only to the user's current reading position.

**How it is designed:** `CharacterState` rows store chapter-specific snapshots. Reader and character routes query the latest state at or before the requested chapter.

### 13. Relationship Extraction And Graphs

**What it does:** The backend extracts relationships between characters, stores descriptions, status, confidence, evidence, and chapter ranges, and exposes relationship graphs.

**What makes it unique:** Graph generation is spoiler-gated, alias-aware, and collapses duplicate character nodes. Edges are aggregated and enriched with the latest safe state.

**How it is designed:** `CharacterRelationship` rows store timeline-aware relationships. Reader relationship endpoints cache graph payloads in Redis. `RelationshipGraph.tsx` and Cytoscape render interactive graph exploration.

### 14. Relationship Evolution

**What it does:** Users can see how relationships change across chapters.

**What makes it unique:** Relationship history is grouped into evolution tracks rather than only a static graph, which makes interpersonal arcs visible over time.

**How it is designed:** Reader endpoints group relationship records up to the requested chapter. The frontend relationship-evolution page calls the reader API and displays chapter-wise changes.

### 15. Reader Chapter Experience

**What it does:** Users read chapters with theme/font controls, progress tracking, smart tap context, quote mode, inline media, summary access, and chapter navigation.

**What makes it unique:** Reading is tied directly to intelligence gating. Current chapter and read status determine what summaries, graph nodes, timeline entries, context answers, and search results can reveal.

**How it is designed:** `ReaderView`, `ReaderToolbar`, `ChapterText`, `ContextPanel`, and `SummaryPanel` coordinate frontend reading state. Backend reader routes return chapter text/html/media and update progress.

### 16. Smart Tap Context

**What it does:** Tapping or selecting a phrase in a chapter returns either a spoiler-safe character card or relevant context from earlier text.

**What makes it unique:** Character matches are checked first, then semantic search falls back to spoiler-gated chunks, and lexical fallback covers cases where embeddings do not return enough context.

**How it is designed:** `reader.py` context endpoints call character lookups and `engine/search/semantic.py`. Frontend `ChapterText` segments mentions and sends selected phrases to `ContextPanel`.

### 17. Spoiler-Safe Semantic Search

**What it does:** Users search within a book using semantic embeddings, lexical fallback, and chapter gates.

**What makes it unique:** Search results honor the reader's current progress and cache by book, query, and chapter.

**How it is designed:** `BookChunk` stores embeddings. `semantic_search` performs pgvector similarity queries and excerpt building. Frontend search pages provide reader/author prompts and result display.

### 18. Summaries

**What it does:** The platform produces detailed, short, and key-point chapter summaries, plus summary collections.

**What makes it unique:** Detailed summaries include events, character changes, clues, and themes; short/key-point summaries can be derived from detailed results. Missing summaries can be generated on demand or queued.

**How it is designed:** `engine/analysis/summariser.py`, `summary_service.py`, analysis workers, and reader endpoints manage generation, caching, and spoiler gates. The summaries page and summary panel consume these APIs.

### 19. Timeline

**What it does:** Users can view events, character appearances, plot threads, and relationship markers across chapters.

**What makes it unique:** Timeline data is built from multiple intelligence layers and remains reader-progress-aware.

**How it is designed:** Reader utilities normalize event and timeline data. The timeline page renders chapter headers, tracks, markers, metric cards, and modal details.

### 20. Foreshadowing And Clues

**What it does:** The system surfaces clues and foreshadowing from detailed summaries.

**What makes it unique:** It can trigger summary generation if needed while keeping results limited to reader-safe chapters.

**How it is designed:** Reader foreshadowing routes collect `clues` from summary payloads. The frontend foreshadowing page presents clue lists and chapter context.

### 21. Plot Threads

**What it does:** Plot threads are extracted, tracked by status, connected to characters and chapters, and editable with user notes.

**What makes it unique:** Plot threads include type, importance, status, character links, notes, and chapter-level context. Author and reader pages can inspect open or resolved threads.

**How it is designed:** `plot_tracker.py` extracts threads. `PlotThread` stores thread state. Reader routes expose and update notes. `PlotTracker.tsx` and the plot-thread page display grouped thread status.

### 22. Memory Recall

**What it does:** Returning readers can get a "previously on" recap based on progress, recent summaries, active characters, and open threads.

**What makes it unique:** Recall is personalized to the user's last read position and cached per user/book.

**How it is designed:** `engine/analysis/recall.py` builds a grounded recap prompt. Reader recall hooks and `RecallCard` show the result.

### 23. Quote Capture

**What it does:** Users can save quotes with chapter number, character association, and notes.

**What makes it unique:** Quotes are connected to reading context and appear in library-level quote collections.

**How it is designed:** Reader quote endpoints store `QuoteEntry` rows. Library/dashboard API clients expose quote listing, and reader components provide quote mode.

### 24. Book Notes

**What it does:** Users can save and delete notes at book or chapter scope and browse notes globally or per book.

**What makes it unique:** Notes live alongside manuscript, reader, and Obsidian-style notes, giving both simple note-taking and graph-based note workflows.

**How it is designed:** `BookNote` rows back basic notes. Dashboard and book notes pages call `booksApi.notes`, `booksApi.saveBookNote`, and delete APIs.

### 25. Obsidian-Style Notes

**What it does:** Users can create, edit, delete, import ZIPs, export ZIPs, view a folder tree, inspect graph relations, and maintain Obsidian-like note vaults per book.

**What makes it unique:** The app stores note links, backlinks, tags, source metadata, generated/user note distinction, and series links. It supports both user-authored vault notes and generated character-bible vault notes.

**How it is designed:** `ObsidianVaultNote`, `NoteLink`, `NoteBacklink`, `NoteTag`, and `NoteSeriesLink` model the graph. `book_utils.py` imports/exports ZIPs and builds note graphs. Frontend `ObsidianNotesEditor`, `FolderTree`, `GraphViewer`, and `ObsidianVaultPreview` render the workflow.

### 26. Character Bible

**What it does:** Users can export a whole-book or series character bible in Markdown, PDF, DOCX, or Obsidian folder format, preview generated vault files, save overrides, and list generated notes.

**What makes it unique:** The bible links characters, relationships, events, plot threads, and story units into a reusable reference system, including Obsidian manifest support.

**How it is designed:** Export utilities build Markdown/PDF/DOCX/ZIP outputs and Obsidian manifests. Book and series endpoints assemble bible payloads from characters, relationships, summaries, and plot threads.

### 27. Series Management

**What it does:** Users can create series, attach/detach books, set book order and status, view series lists, and ask series-level questions.

**What makes it unique:** Series features are not just grouping. They power cross-book intelligence, series bible generation, series advisor chat, and continuity checks across volumes.

**How it is designed:** `Series` and `SeriesBook` model membership and position. Series endpoints in books and advisor routes expose CRUD, bible, advisor, and continuity operations. Frontend series pages manage membership and ask flows.

### 28. Cross-Book Intelligence

**What it does:** Users can compare characters and wiki entries across books in a series to find likely continuity matches.

**What makes it unique:** The matching uses embedding similarity across different books and groups results by character/wiki modes.

**How it is designed:** Intelligence routes query character and wiki embeddings and compare with cosine thresholds. The cross-book wiki frontend page filters matches by all, characters, or wiki.

### 29. Grounded Book Q&A

**What it does:** Users ask questions about a book and receive grounded answers with citations.

**What makes it unique:** The answer context blends chapter summaries, semantic passages, and prior-volume context where available, while obeying chapter/spoiler boundaries.

**How it is designed:** `intelligence.py` calls `build_grounded_qa_context`, caches by book/chapter/question, and returns citations. The ask page includes quick prompts and chat history.

### 31. Character Chat

**What it does:** Users can chat with a character using that character's profile and book context.

**What makes it unique:** Responses are shaped by the extracted profile and grounded with relevant context rather than being a generic persona prompt.

**How it is designed:** `character_chat.py` builds a prompt from character traits and semantic context. The intelligence route validates access and sends chat requests to the engine.

### 32. Author Manuscript Workspace

**What it does:** Authors can edit manuscript chapters, full-book drafts, standalone scenes, notes, front matter, chapter metadata, and workspace settings.

**What makes it unique:** The editor is connected to intelligence features: chapter reports, continuity flags, advisor suggestions, voice checks, prose tightening, synopsis, emotional arc, pre-writing checks, Obsidian notes, and character side panels.

**How it is designed:** The large manuscript page manages rich editor state, chapter/book modes, right-pane insights/notes/character panels, versions, scenes, workspace tree, formatting toolbar, import/export controls, compile settings, and review actions. Backend manuscript and book routes persist scenes, snapshots, chapters, and workspace JSON.

### 33. Rich Text And Manuscript Serialization

**What it does:** Manuscript content can be edited as rich HTML while preserving text form for analysis and export.

**What makes it unique:** The frontend sanitizes supported rich text operations, and the backend serializes/deserializes text plus HTML to keep both editor fidelity and analysis-friendly plaintext.

**How it is designed:** Frontend `richText.ts`, editor toolbar, and `RichTextEditor` constrain formatting. Backend `book_utils.py` handles Markdown/HTML conversion, sanitization, and serialized manuscript content.

### 34. Chapter Versions And Restore

**What it does:** The system snapshots chapter versions, lists versions, returns version content, and restores older versions.

**What makes it unique:** Restoring a version purges derived intelligence so summaries, scenes, reports, and related computed data can be regenerated for the restored text.

**How it is designed:** `ChapterVersion` rows store snapshots. Manuscript/book utility endpoints snapshot, retrieve, purge derived content, restore, and list versions.

### 35. Novel Scenes And Corkboard

**What it does:** Authors can create, update, delete, list, and insert standalone novel scenes into chapters.

**What makes it unique:** Imported prose can be split into scene candidates and organized into virtual paths, enabling corkboard-style manuscript planning without forcing every scene into a chapter immediately.

**How it is designed:** `NovelScene` stores scene metadata and content. `book_utils.py` extracts scene candidates, builds scene paths, and inserts scenes. The manuscript page includes scene/corkboard workflows.

### 36. Screenplay Support

**What it does:** The platform parses screenplay/Fountain-style manuscripts into scenes, dialogue, action, transitions, shots, parentheticals, and statistics.

**What makes it unique:** Screenplay work type is first-class, with scene headings, dialogue models, stats display, and author import behavior tailored to scripts.

**How it is designed:** `screenplay_parser.py` identifies scene headings, character cues, dialogue blocks, transitions, and shots. `Scene` and `Dialogue` models store script structure. `ScreenplayStats.tsx` renders stats.

### 37. Chapter Reports And Continuity Flags

**What it does:** Authors can generate chapter consistency reports and view continuity issues.

**What makes it unique:** Reports combine chapter text, character data, plot threads, and extracted story events to flag issues useful for revision.

**How it is designed:** `build_chapter_consistency_report`, `detect_chapter_continuity_flags`, advisor endpoints, and reports pages create and display review output.

### 38. Story Advisor Chat

**What it does:** Authors can chat with an AI advisor about a book or series, including craft, continuity, structure, and story planning questions.

**What makes it unique:** Advisor answers are RAG-backed, cache-aware, intent-classified, and context-sensitive to author mode. Series advisor uses multiple books as context.

**How it is designed:** Advisor routes classify intent, build story context, perform semantic retrieval, include recent chat history, call the LLM, classify response type, and return retrieved passages. Frontend advisor pages render rich messages, panels, suggestions, and stats.

### 39. Advisor Suggestions

**What it does:** The backend produces proactive suggestions such as trait contradictions, dropped threads, long-absent characters, high-importance arcs, future direction, underused minor characters, and unresolved clues.

**What makes it unique:** Suggestions are generated from database evidence without needing a fresh LLM call and are sorted by severity.

**How it is designed:** `advisor_utils.py` and advisor routes inspect characters, plot threads, summaries, and events. The frontend groups suggestions by severity/type.

### 40. Editorial Review

**What it does:** Authors can request continuity, insertion, and grammar review for selected manuscript text.

**What makes it unique:** Review is grounded in semantic retrieval and story context, so comments can reference the existing manuscript rather than only local grammar.

**How it is designed:** Advisor endpoints combine semantic passages, story context, cache keys, and structured LLM output. The manuscript and advisor UIs trigger review actions.

### 41. Prose Tightening

**What it does:** Authors can submit selected text for concise rewrite suggestions.

**What makes it unique:** It is integrated directly into the manuscript workspace, so revision assistance sits next to the draft instead of being a separate chat-only feature.

**How it is designed:** Advisor prose endpoints return JSON rewrite output. Manuscript UI stores selected text and applies or displays suggestions.

### 42. Inline Continuity Review

**What it does:** Authors can run inline continuity checks against selected manuscript context.

**What makes it unique:** The response includes issue snippets and a memory bank, combining local chapter flags with broader editorial review.

**How it is designed:** Advisor inline continuity wraps editorial review and chapter continuity helper output.

### 43. Synopsis Generation

**What it does:** Authors can generate a synopsis from early chapter snippets and story context.

**What makes it unique:** It supports minimal/none spoiler levels to shape how much story information the synopsis includes.

**How it is designed:** Advisor synopsis endpoints build context from the first chapters and story metadata. Manuscript/advisor UI exposes the action.

### 44. Voice Consistency Review

**What it does:** Authors can check whether a selected passage matches a character's established voice.

**What makes it unique:** The platform computes dialogue voice profiles and compares selected passages against baseline markers and other characters.

**How it is designed:** Extraction workers collect dialogue metrics and merge `CharacterVoiceProfile` rows. Advisor voice endpoints use semantic passages, character detection, and LLM evaluation.

### 45. Continuity Report Export

**What it does:** Authors can export continuity reports in Markdown or PDF.

**What makes it unique:** The report joins editorial review, advisor suggestions, and unresolved plot threads into a portable artifact.

**How it is designed:** Advisor routes call report builders and PDF renderers. Frontend export/advisor pages expose report generation.

### 46. World-Building Documents

**What it does:** Authors can upload, replace, read, update, and delete world-building documents for a book.

**What makes it unique:** World documents are parsed into structured elements and cross-checked against manuscript usage.

**How it is designed:** World-building routes enforce a 20 MB limit and call utility functions for CRUD, parsing, element sync, and analysis. `WorldbuildingWorkspace.tsx` provides document browsing and upload/replace controls.

### 47. World Element Extraction

**What it does:** The system extracts places, organizations, objects, events, concepts, eras, characters, and other world elements from world docs and story chapters.

**What makes it unique:** Element extraction includes type inference, provenance, claims, confidence, narrative-mode hints, non-entity filtering, optional POS checks, and canonical identity merging.

**How it is designed:** `engine/world/extractor.py` does lightweight extraction and filtering. `world_building_utils.py` resolves aliases, canonical identities, story presence, scores, and conflicts.

### 48. World Gap Analysis

**What it does:** The platform detects world-building gaps such as missing categories, story/world mismatches, character gaps, timeline gaps, conflicts, and missing-in-story elements.

**What makes it unique:** It compares both directions: what the world bible defines but story ignores, and what the story uses but the world docs do not define.

**How it is designed:** `gap_detector.py` and world-building utilities produce gap payloads, save analyses, and allow suggestions to become notes.

### 49. World Integration Mapping

**What it does:** The platform suggests ways to integrate underused world elements into the manuscript.

**What makes it unique:** It looks for low-usage or missing story presence instead of only reporting factual conflicts.

**How it is designed:** `integration_mapper.py` and `world_building_utils.py` score elements and generate integration opportunities. Frontend tiles display status and actions.

### 50. World Logic Simulator

**What it does:** Authors can ask "what if" or logic questions about the world and receive cited responses.

**What makes it unique:** Responses include citations, suggestions, and simulation steps derived from world documents and story elements.

**How it is designed:** World query endpoints classify intent and call `build_world_logic_response`. The world workspace exposes a query panel.

### 51. World Wiki

**What it does:** Users can list and generate wiki entries from manuscript/world material.

**What makes it unique:** Wiki entries can participate in cross-book embedding comparison for series continuity.

**How it is designed:** `WikiEntry` stores title, type, content, metadata, chapter range, and embedding. World-building routes generate/list wiki data.

### 52. Canon Overrides

**What it does:** Authors can define canonical identity overrides and aliases for world elements.

**What makes it unique:** Manual canon overrides guide automatic merging and conflict detection, letting author judgment correct extraction ambiguity.

**How it is designed:** `WorldCanonicalIdentity` stores names, aliases, descriptions, confidence, and source. World-building endpoints list/create overrides.

### 53. World Notes

**What it does:** Authors can create, update, delete, filter, and save world notes, including notes derived from gaps or integrations.

**What makes it unique:** Notes can be tied to element IDs, chapters, statuses, and source analysis.

**How it is designed:** `WorldNote` stores note text, status, element/chapter links, and metadata. World note routes and the world workspace coordinate lifecycle.

### 54. Series World Analysis

**What it does:** Series-level world analysis can compare world-building across books in a series.

**What makes it unique:** It gives long-form authors a continuity lens that spans volumes rather than a single manuscript.

**How it is designed:** World-building series routes assemble series books and world element data for analysis.

### 55. Manuscript Export Studio

**What it does:** Authors can export manuscripts as PDF, DOCX, EPUB, or Obsidian vaults, with presets and front matter.

**What makes it unique:** Export supports compiled chapter/scene structures and publishing-style presets such as standard manuscript, trade, and KDP-like layouts.

**How it is designed:** `export_utils.py` renders DOCX, PDF, EPUB, compiled PDF/EPUB, and Obsidian vault ZIPs. The frontend export page manages format and preset selection.

### 56. Character And Bible Export Studio

**What it does:** Users can export individual character cards and whole character bibles.

**What makes it unique:** The export layer produces human-readable docs and graph-friendly Obsidian vaults with backlinks and manifests.

**How it is designed:** Export endpoints call `character_card_*`, `character_bible_*`, and Obsidian preview/folder builders. Frontend export and character pages expose the actions.

### 57. Public Asset And Public Reading Support

**What it does:** The backend includes public book list/detail/chapter/manual creation and append endpoints, plus tokenized media/cover/character-card asset routes.

**What makes it unique:** Public reading exists behind a hard feature flag and currently returns disabled responses unless enabled, reducing accidental publication risk.

**How it is designed:** `public.py` implements public endpoints with Redis caching and an internal `PUBLIC_MODE_ENABLED = False` guard. Asset routes use signed tokens for covers, media, and character cards.

### 58. Billing And Subscription Gates

**What it does:** Users can create Paddle checkout links, open billing portals, and receive subscription updates through webhooks.

**What makes it unique:** Billing gracefully reports disabled state when Paddle is not configured, and local/debug mode can effectively grant pro limits.

**How it is designed:** `paddle_service.py` wraps Paddle customer/checkout/portal/webhook calls. Billing routes update `Subscription` rows. Webhooks verify signatures, deduplicate in Redis, and update user tiers.

### 59. Tier Limits And Rate Limits

**What it does:** The platform enforces tier-aware limits for books, uploads, summaries, questions, advisor messages, exports, world documents, and other actions.

**What makes it unique:** Admins can set per-user rate limit overrides, and effective tier logic can differ in local/debug mode.

**How it is designed:** Config settings define tier limits. API dependencies enforce subscription and Redis-backed rate limits. Admin routes upsert overrides.

### 60. Notifications

**What it does:** Users receive notifications for processing, detected characters, readiness, and other events. They can list notifications, see unread counts, mark one read, or mark all read.

**What makes it unique:** Notifications connect long-running worker progress to the UI and can trigger frontend refreshes through a custom event hook.

**How it is designed:** `Notification` rows and notification utilities create messages. `NotificationsPanel`, `NotificationBell`, and `useNotifications` render and refresh state.

### 61. Email Notifications

**What it does:** The backend can send onboarding, password reset, processing complete, subscription confirmation, and new-character emails.

**What makes it unique:** Email delivery is optional and failure-tolerant for local development.

**How it is designed:** `email_service.py` wraps Resend payloads and exposes async email helpers.

### 62. Admin Console APIs

**What it does:** Admin endpoints expose metrics, queue depth, and per-user rate-limit override management.

**What makes it unique:** Admin controls target operational visibility and user-specific exception handling rather than general content management.

**How it is designed:** `admin.py` depends on admin auth and calls Redis, database, and override helpers.

### 63. Observability And Error Sanitization

**What it does:** The backend logs structured JSON, attaches request IDs, sanitizes validation and server errors, and can report production errors to Sentry.

**What makes it unique:** Client-facing errors avoid leaking internal implementation details while logs keep request context for debugging.

**How it is designed:** `main.py`, `logging/logger.py`, `logging/errors.py`, request context utilities, and middleware implement the behavior.

### 64. Storage Abstraction

**What it does:** Files, covers, media, exports, and text assets can be stored locally or in S3/R2-compatible storage.

**What makes it unique:** Local storage includes ownership/permission handling for containerized development, while remote storage uses presigned URLs and content types.

**How it is designed:** `core/storage.py` abstracts upload/download/presign logic and protects storage keys.

### 65. Migration Safety

**What it does:** Migration helpers detect local vs remote database URLs, redact targets, and identify destructive Alembic operations.

**What makes it unique:** The repository bakes production-database caution into tooling and instructions rather than leaving it to memory.

**How it is designed:** `migration_utils.py`, Alembic env configuration, migration docs, and repo instructions enforce explicit target handling and destructive-operation review.

### 66. API Client Caching And Refresh

**What it does:** The frontend API layer deduplicates selected GET requests, caches results briefly, invalidates by prefix, and refreshes expired auth sessions.

**What makes it unique:** It reduces duplicate network work while keeping auth recovery centralized.

**How it is designed:** `requestCache.ts` manages in-memory cache/in-flight maps. `client.ts` wraps axios interceptors.

### 67. Preferences, Themes, And Reading Modes

**What it does:** Users can switch app theme, reader theme, font, font size, and reading mode.

**What makes it unique:** Reading mode is stored server-side on the user, while UI preferences are local for immediate frontend ergonomics.

**How it is designed:** Zustand preference/book-mode stores, settings page controls, and auth reading-mode endpoints coordinate state.

### 68. PWA And Manifest Support

**What it does:** The frontend includes a web app manifest, service worker registration, and public images.

**What makes it unique:** LoreVia can behave more like an installable app while still using the Next.js route system.

**How it is designed:** `manifest.ts`, `PWARegister.tsx`, `frontend/public/sw.js`, and public image assets implement the PWA layer.

### 69. Landing Page And Marketing Surface

**What it does:** The public landing page presents product positioning, comparison content, pricing links, FAQs, and author-focused calls to action.

**What makes it unique:** The landing page routes authenticated users toward the library while giving unauthenticated users login/register paths.

**How it is designed:** `frontend/src/app/page.tsx` contains reveal sections, comparison blocks, CTA logic, and theme-aware visuals.

### 70. Dashboard Stats

**What it does:** Users can view high-level reading and manuscript statistics.

**What makes it unique:** Stats combine library totals, reading progress, and book metadata into a dashboard view.

**How it is designed:** The stats page consumes book stats and user/library data from frontend API clients.

### 71. Status Page

**What it does:** The frontend includes a status page with status navigation.

**What makes it unique:** It keeps operational status separate from authenticated product workflows.

**How it is designed:** `status/page.tsx` and `StatusNavigation.tsx` render the page.

### 72. Public Chapter Page

**What it does:** A route exists for public book chapters.

**What makes it unique:** It is separated from authenticated reader routes and aligns with disabled public backend APIs.

**How it is designed:** `frontend/src/app/public/[bookId]/chapter/[chapterId]/page.tsx` calls public book/chapter APIs.

### 73. Readability Metrics

**What it does:** Authors can request readability and manuscript-quality metrics for selected manuscript text.

**What makes it unique:** Readability sits inside the author workspace and can be used during drafting rather than only after export or publication.

**How it is designed:** Book routes expose manuscript readability analysis, schemas define the metrics response, and manuscript UI actions call the endpoint from the author workspace.

### 74. Emotional Arc

**What it does:** Authors can inspect emotional arc data derived from character growth and story events.

**What makes it unique:** The arc is generated from extracted character development rather than requiring the author to manually tag every emotional beat.

**How it is designed:** `build_emotional_arc_payload` aggregates character growth events and related metadata. Book routes expose the payload, and the manuscript workspace can surface it alongside drafting tools.

### 75. Pre-Writing Check

**What it does:** Authors can run a pre-writing readiness check for a manuscript/book workspace.

**What makes it unique:** It is designed as an author planning feature that checks whether enough story foundation exists before deeper drafting or analysis.

**How it is designed:** Book utility helpers build the check from book, character, plot, and manuscript metadata. Book routes expose it and frontend import/manuscript flows can show the result.

### 76. Thematic Search

**What it does:** Users can search for themes, motifs, clues, and story concepts across summaries, events, clues, and raw chapter text.

**What makes it unique:** It searches intelligence artifacts first, then falls back to chapter text, so conceptual search can find meaning-rich derived data as well as literal prose.

**How it is designed:** Reader thematic-search routes gather matching summary/event/clue material and raw text results under spoiler gates. The frontend search workspace exposes thematic prompts.

### 77. Writer Workspace State

**What it does:** The backend stores and returns persistent author workspace state such as processing progress, editor settings, and manuscript workspace metadata.

**What makes it unique:** Workspace state links long-running ingestion and author UI continuity, so the manuscript workspace can reopen with meaningful context after background jobs complete.

**How it is designed:** The `Book.writer_workspace` JSON field stores workspace state. Ingestion helpers update processing status and ETA. Book routes provide GET/PUT access.

### 78. Archive And Hide Controls

**What it does:** Users can archive or hide books without deleting them.

**What makes it unique:** Hide status is also respected by background processing cancellation logic, so user intent can stop work that is no longer wanted.

**How it is designed:** Book rows include archived/hidden timestamps. Book routes update them, library UI exposes the actions, and ingestion workers check cancellation state.

### 79. Chapter Navigation And Read State

**What it does:** Users can see chapter availability, read/current state, intelligence availability, mark chapters read/unread, and mark a whole book read.

**What makes it unique:** Chapter state is not only a UI marker; it controls spoiler-safe intelligence boundaries across summaries, graphs, timelines, recall, and search.

**How it is designed:** `ReadingProgress` and chapter reader endpoints store progress and read maps. Frontend chapter list and reader pages update and consume that state.

## Frontend Route Inventory

### Public And Global Routes

- `/`: Landing/product page with CTA logic, comparison sections, pricing/FAQ content, and reveal animations.
- `/terms`: Terms page.
- `/privacy`: Privacy page.
- `/eula`: EULA page.
- `/refund`: Refund page.
- `/contact`: Contact/support page.
- `/status`: Status page.
- Global layout: navbar, footer, analytics provider, PWA registration, auth bootstrap, global styles.
- Global error page: fallback error UI.

### Auth Routes

- `/login`: Email/password login and Google OAuth entry.
- `/register`: Email/password registration, Google OAuth, legal acceptance, username/account setup flow.
- `/complete-username`: One-time username completion after OAuth or incomplete account setup.
- `/auth/callback`: Supabase OAuth callback processing.

### Dashboard Routes

- `/library`: Shelf/library, upload modal, book processing state, archive/hide actions, covers, stats, mode-aware navigation.
- `/library/add-chapter`: Focused add-chapter import path into an existing book.
- `/notes`: Cross-book notes dashboard.
- `/notifications`: Notification center.
- `/pricing`: Billing plan selection and checkout.
- `/series`: Series manager, series bible summary, series book cards, add-book controls, status/order actions.
- `/series/[seriesId]/ask`: Series advisor chat.
- `/settings`: Theme, reading mode, account, billing, and preference controls.
- `/stats`: Reading/library statistics.

### Book Workspace Routes

- `/:bookId`: Book overview with cover, metadata, progress, metrics, and navigation into tools.
- `/:bookId/chapter/:chapterId`: Reader chapter view.
- `/:bookId/chapters`: Chapter list with read/current/intelligence status.
- `/:bookId/characters`: Character directory, filters, tabs, edit/merge/delete/share/export actions.
- `/:bookId/graph`: Relationship graph.
- `/:bookId/search`: Semantic/thematic search workspace.
- `/:bookId/analysis`: Analysis hub that links major intelligence tools.
- `/:bookId/summaries`: Summary collection.
- `/:bookId/foreshadowing`: Clue and foreshadowing view.
- `/:bookId/timeline`: Multi-track event/character/plot/relationship timeline.
- `/:bookId/relationship-evolution`: Relationship changes over chapters.
- `/:bookId/plot-threads`: Plot thread board and notes.
- `/:bookId/reports`: Chapter report listing.
- `/:bookId/ask`: Grounded Q&A.
- `/:bookId/advisor`: Story advisor, suggestions, editorial/voice/prose/review tools.
- `/:bookId/manuscript`: Author manuscript editor and workspace.
- `/:bookId/notes`: Book-specific notes and Obsidian notes tools.
- `/:bookId/export`: Character, bible, manuscript, and import/export studio.
- `/:bookId/cross-book-wiki`: Cross-book character/wiki continuity matches.
- `/:bookId/compliance`: Copyright/ISBN compliance surface.
- `/:bookId/world-gap`: World-building gap and workspace surface.

### Public Reading Routes

- `/public/[bookId]/chapter/[chapterId]`: Public chapter reader route for the read-only public demo/library surface.

## Backend Route Inventory

### Auth Routes

- `POST /auth/register`
- `POST /auth/login`
- `POST /api/v1/auth/oauth/supabase`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me/reading-mode`
- `GET /auth/tier-limits`
- `PATCH /auth/me/username`

### Book, Library, Character, Export, Notes, Series, And Manuscript Routes

- Upload, mode switching, book list/detail/stats/quotes/notes.
- Reader-safe and author/full-book event APIs.
- Manuscript import/export.
- Series CRUD, membership, status, and series bible.
- Book notes and Obsidian vault notes CRUD/import/export/graph/relations.
- Pre-writing check, chapter reports, chapter versions, writer workspace, readability, emotional arc.
- Cover/public asset URLs and cover processing.
- Archive/hide.
- Character list, edit, merge, delete, relationship update, share URL, card export, bible export, bible preview, bible note save/list, public character card.

### Reader Routes

- Tokenized media access.
- Chapter content.
- Smart tap context.
- Summary and summary collection.
- Reader-safe events.
- Relationship graph.
- Semantic search.
- Chapter list.
- Foreshadowing.
- Timeline.
- Thematic search.
- Relationship evolution.
- Quote save.
- Plot thread list/note update.
- Memory recall.
- Reading progress, mark book read, and chapter read status.

### Intelligence And Advisor Routes

- Grounded Q&A.
- Character chat.
- Cross-book intelligence.
- Book advisor message.
- Advisor greeting.
- Advisor suggestions.
- Editorial review.
- Prose tightening.
- Inline continuity.
- Synopsis.
- Voice consistency.
- Continuity report export.
- Series advisor message.
- Series continuity check.

### World-Building Routes

- World document list/upload/read/update/delete.
- World analysis.
- Gap analysis.
- Integration opportunities.
- Wiki list/generate.
- Logic query.
- Series world analysis.
- Accept suggestion.
- Canon override list/create.
- World notes list/create/delete/update/by chapter.

### Billing, Webhook, Notification, Admin, Public, And Character Routes

- Paddle checkout and portal.
- Paddle webhook with idempotency.
- Notification list/count/read/read-all.
- Admin metrics, queue depth, and rate limit overrides.
- Character detail and spoiler-free state.
- Public books/detail/chapter endpoints remain available through public mode, while public forum writes are launch-gated behind `PUBLIC_FORUM_STATUS`.

## Data Model Inventory

- `User`: account identity, username, legal acceptance, tier, reading mode, token version, billing references.
- `Subscription`: Paddle and Stripe subscription/customer/plan/status metadata.
- `UserRateLimitOverride`: per-user action limits.
- `Book`: manuscript/book metadata, storage keys, mode, work type, source kind, cover fields, ISBN/copyright/public fields, token/chapter counts, series fields, writer workspace, hidden/archive status, and relationships to all book intelligence.
- `Chapter`: chapter number/title/text/html/storage/token/word counts, media, versions, summaries, scenes.
- `ChapterVersion`: manuscript snapshots and restore lineage.
- `BookNote`: scoped book/chapter notes.
- `ObsidianVaultNote`, `NoteLink`, `NoteBacklink`, `NoteTag`, `NoteSeriesLink`: note graph and vault model.
- `ChapterMedia`: inline images/media markers.
- `Series`, `SeriesBook`: series metadata, position, and completion/status.
- `Scene`, `Dialogue`: screenplay scene/dialogue model.
- `NovelScene`: author-mode standalone/corkboard scenes.
- `Character`: profile, aliases, trait state, physical fields, motivations, archetype, growth, classification, embeddings, relations, and voice profile.
- `CharacterState`: spoiler-safe chapter snapshots.
- `CharacterVoiceProfile`: dialogue metrics, markers, and signature phrases.
- `BookChunk`: embedded chunk text for semantic search/RAG.
- `CharacterRelationship`: timeline-aware relationship edges.
- `PlotThread`: plot thread tracking and notes.
- `ChapterSummary`: detailed/short/key-point summaries with events, changes, clues, and themes.
- `WikiEntry`: wiki/canon entries with embeddings.
- `QuoteEntry`: saved quotes.
- `Notification`: user notifications.
- `WorldBuildingDocument`, `WorldElement`, `WorldCanonicalIdentity`, `WorldGapAnalysis`, `WorldNote`: world-building source docs, extracted canon, identity overrides, gap results, and notes.
- `ReadingProgress`, `ReadingSession`: reading progress and session tracking.

## Supporting Engine And Utility Inventory

- Character engine: extraction, deduplication, entity visibility scoring, subtype scoring, profile building, consolidation.
- Analysis engine: summaries, plot tracking, recall.
- Search engine: pgvector semantic search and tap context.
- Intelligence engine: character chat.
- World engine: element extraction, gap detection, integration mapping, dependency graph.
- Embedding engine: OpenAI embeddings for chunks and characters.
- Parser layer: PDF, EPUB, chunking, screenplay/Fountain parsing.
- Book utilities: book serialization, series bible, cover URLs, import parsing, manuscript HTML/text conversion, Obsidian notes, scenes, versions, emotional arc, pre-writing checks, chapter reports.
- Character utilities: display, relationship text, status, and cleaning helpers.
- Reader utilities: graph/timeline/search/summary serialization and normalization.
- Advisor utilities: prompts, intent classification, story context, response/report builders.
- Intelligence utilities: grounded citation and QA context construction.
- World-building utilities: document CRUD, identity/canon merging, gaps, integrations, wiki, logic responses, notes.
- Export utilities: character cards, character bibles, manuscript DOCX/PDF/EPUB/Obsidian exports.
- Ingestion utilities: dispatch plans, persistent chapter payloads, progress/ETA, retries, cancellation, grouping.
- Notification utilities: create and format notifications.
- Screenplay utilities: screenplay-specific output support.
- Compliance utilities: ISBN/copyright checks.
- Storage/security/Redis/config/logging utilities: platform infrastructure.
- Migration utilities: local/remote target and destructive operation safety.

## Test Coverage Inventory

Tests cover access control, admin APIs, auth, book cover and merge flows, upload work type, sanitized errors, events API, ingestion pipeline, Obsidian export preview, reader APIs, reader timeline, series bible, world-building API, extraction pipeline, advisor utilities, auth cookies/deps/logging, book utilities, character dedup/extractor/profile builder, chunking, config, cover processing, event linking, export utilities, ingestion helpers, intelligence utilities, logging, migration utilities, Obsidian notes/vault export, PDF parsing, rate limiting, reader utilities, Redis utilities, screenplay parsing, semantic search, storage permissions, and world-building utilities.

## Second-Pass Coverage Checklist

- Backend router mount points checked against this document: auth, books, public, billing, webhooks, characters, reader, notifications, intelligence, advisor, world-building, admin, manuscript.
- Backend data models checked against this document: user, book, character, intelligence, progress.
- Backend support layers checked against this document: services, utils, core, engines, parsers, workers, tasks.
- Frontend route tree checked against this document: public, auth, dashboard, reader/book workspace, public chapter.
- Frontend shared components checked against this document: upload modal, reader components, character card, relationship graph, notes graph/editor, world-building workspace, notifications, navbar/footer, author nav, UI primitives, PWA/analytics.
- Frontend API clients checked against this document: auth, books, reader, intelligence, world-building, billing, notifications, request cache, axios client.
- Tests checked for corroborating feature areas and edge cases.
