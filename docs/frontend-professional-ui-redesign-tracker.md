# LoreVia Professional UI Redesign Tracker

Status: Complete  
Started: 2026-09-14  
Completed: 2026-09-30  
Scope: `frontend/`  
Objective: remove repetitive AI-generated UI patterns, establish a restrained professional product language, reduce cognitive load, and preserve or improve runtime performance.

This document is the authoritative checklist for the current redesign. A checked item means the source change is complete and covered by an appropriate automated or visual verification. A route is not complete merely because shared CSS changed beneath it.

## Non-negotiable design rules

- The manuscript, story data, or user task is the dominant surface; product chrome stays subordinate.
- Use one primary navigation system per context. Account navigation and book navigation must not compete.
- Book navigation is organized into four jobs: Draft, Story Bible, Review, and Share.
- Sidebars are reserved for local objects such as chapters, notes, characters, or inspectors. They are not global book navigation.
- Do not place a bordered card directly inside another bordered card unless the inner surface is a real subdocument or transient overlay.
- Pills are reserved for statuses, tags, and compact filters. Metadata and ordinary actions use text, rows, or menus.
- Uppercase, widely tracked microcopy is reserved for rare marketing eyebrows. Product labels use sentence case.
- Serif typography is reserved for editorial reading, book titles, and selected marketing headings. Operational UI uses the product sans.
- Empty states explain the cause and one useful next action. Empty adjacent panels are not rendered.
- Motion communicates state or location. No decorative hover lift, glow, or long crossfade.
- Existing LoreVia logo assets remain the source of truth. No generated or substitute branding.

## Performance and latency guardrails

- [x] No new runtime dependency is added for the redesign.
- [x] Book navigation reuses the existing tool registry and preferences; it does not duplicate API calls.
- [x] Route shells do not fetch data already available in query cache.
- [x] Hidden or collapsed panels do not eagerly mount expensive graphs, editors, or analytics.
- [x] Navigation prefetch remains intent-based rather than prefetching every book route.
- [x] Marketing images use responsive sizing and modern formats where source quality permits.
- [x] Decorative animation respects reduced motion and does not keep content hidden when JavaScript or IntersectionObserver is unavailable.
- [x] Production build, surface-size check, type check, unit tests, and E2E smoke tests pass.
- [x] Key routes are visually checked at desktop, laptop, tablet, and 390px mobile widths.

## Baseline indicators

These values are diagnostic rather than hard release gates. Counts should fall because the interface becomes simpler, not through meaningless class substitutions.

| Indicator | Baseline |
|---|---:|
| App routes | 82 |
| Production TSX files scanned | 373 |
| `rounded-full` uses | 457 |
| `uppercase` uses | 639 |
| Inline SVG elements | 254 |
| Unique hard-coded hex colors | 385 |
| Hard-coded hex references | 1,585 |

## Phase 1 — Product language and shared primitives

- [x] Reduce the Tailwind radius scale to restrained control, panel, dialog, and feature-surface values.
- [x] Flatten `app-panel`; remove default gradient and ornamental shadow.
- [x] Convert `app-eyebrow` and stat labels to compact sentence-case labels.
- [x] Restrict `app-chip` to semantic status/filter use and remove oversized padding.
- [x] Remove hover lift from shared buttons and tabs.
- [x] Replace the dashed, oversized default empty state with a compact action-oriented state.
- [x] Standardize shared surface, toolbar, list-row, page-header, status, and divider primitives.
- [x] Replace `transition-all` in shared controls with property-specific transitions.
- [x] Verify focus, disabled, reduced-motion, light theme, and dark theme behavior.

## Phase 2 — Book information architecture

- [x] Replace hover-expanding global book rail with a stable book bar.
- [x] Provide four desktop hubs: Draft, Story Bible, Review, Share.
- [x] Provide a responsive hub selector and mobile More menu.
- [x] Keep active, permission-allowed, plan-allowed, and processing-allowed tool resolution from the existing registry.
- [x] Keep task presets and hidden-tool preferences without showing five small mode buttons permanently.
- [x] Move Search Passages into the book-bar utility area.
- [x] Treat Recaps as contextual reader/chapter content.
- [x] Treat Author Lens as a launched workflow rather than primary navigation.
- [x] Move Compliance out of ordinary book navigation unless the current book has an actionable compliance condition.
- [x] Replace overlapping `WorkspaceFamilyHeader` navigation with local subnavigation only where the selected hub needs it.
- [x] Ensure book navigation is consistent on routes that previously omitted `AuthorToolsNav`.

## Phase 3 — Book routes

### Draft

- [x] `/{bookId}` — reduce overview to continue writing, progress, urgent finding, and recent activity.
- [x] `/{bookId}/chapter/{chapterId}` — keep reading immersive; make recap, notes, search, and Ask contextual.
- [x] `/{bookId}/chapters` — use a compact manuscript outline rather than card-per-chapter presentation.
- [x] `/{bookId}/manuscript` — one toolbar, collapsible local chapter rail, and one contextual inspector at a time.
- [x] `/{bookId}/scenes` — share the manuscript focus model: editor first, with the scene outline and metadata inspector mounted only on demand. A separate permanent board was intentionally superseded because folder/list organization already lives inside the outline.
- [x] `/{bookId}/notes` — reduce to note tree plus editor; properties become an on-demand inspector.

### Story Bible

- [x] `/{bookId}/characters` — compact roster, profile canvas, on-demand inspector; reduce metrics and attribute pills.
- [x] `/{bookId}/graph` — make the graph the canvas and move controls to one toolbar.
- [x] `/{bookId}/relationship-evolution` — merge into Relationships as a local view; preserve the legacy URL as a redirect.
- [x] `/{bookId}/timeline` — use chronological lanes or a dense event list with one filter bar.
- [x] `/{bookId}/plot-threads` — prioritize Open, Weak, and Resolved working lists.
- [x] `/{bookId}/foreshadowing` — rename to Setup & Payoff and use a setup-to-outcome evidence ledger with Linked and Unresolved views. Echo/payoff stage tabs were intentionally not fabricated because the current API exposes setup text and intended outcome, not observed echo/payoff events.
- [x] `/{bookId}/world-gap` — use an evidence-backed review queue by default; separate Canon Sources and Canon Tools into intent-loaded local views.
- [x] `/{bookId}/cross-book-wiki` — use a reference-oriented list/detail workspace.

### Review

- [x] `/{bookId}/advisor` — combine recommended checks and grounded questions in one advisor workspace.
- [x] `/{bookId}/ask` — author-mode requests now resolve into Story Advisor's question mode instead of competing in book navigation; reader mode remains a spoiler-scoped Q&A workspace with a flat prompt, answer, and source layout.
- [x] `/{bookId}/analysis` — became an evidence-led Findings overview with live continuity triage and flat links to focused reviews.
- [x] `/{bookId}/reports` — now redirects into a filterable Chapter reports view within Findings; empty evidence categories are suppressed.
- [x] `/{bookId}/editorial-review` — run history plus document/findings workspace; remove setup/result card stacking.
- [x] `/{bookId}/ai-beta-reader` — explicit Configure, Run, Review sequence.
- [x] `/{bookId}/voice` — present as a character/chapter review type.
- [x] `/{bookId}/search` — accessible from global book search without remaining a primary destination.
- [x] `/{bookId}/summaries` — surface chapter recaps contextually and manuscript recap on overview.
- [x] `/{bookId}/author-loop` — present as a resumable guided flow launched from Overview or Findings.

### Share

- [x] `/{bookId}/collaboration` — conventional people table with invitations and permissions.
- [x] `/{bookId}/beta-feedback` — assignments first, then responses; suppress empty secondary categories.
- [x] `/{bookId}/export` — rename presentation to Files & Export and use a task-oriented flow.
- [x] `/{bookId}/visibility` — one clear visibility model with advanced recovery under disclosure.
- [x] `/{bookId}/compliance` — move to global/legal context or show only when actionable.

## Phase 4 — Account dashboard

- [x] Dashboard shell — one account-level navigation system; no duplicate top navigation.
- [x] `/library` — projects dominate; one flat search/filter toolbar; safer primary project links.
- [x] `/library/add-chapter` — make contextual to the selected book.
- [x] `/notes` — compact searchable list.
- [x] `/quotes` — compact searchable list.
- [x] `/stats` — one useful trend chart, one progress summary, and compact breakdowns.
- [x] `/series` — master/detail series management.
- [x] `/series/{seriesId}/ask` — keep Ask contextual to the selected series.
- [x] `/beta-reads` — Assigned, In progress, Completed list states.
- [x] `/chats` — conventional two-pane conversation layout.
- [x] `/notifications` — chronological rows with unread emphasis.
- [x] `/settings` — scannable categories, flat form sections, and workspace visibility controls.
- [x] `/upgrade` — share the public pricing presentation and remove app-shell noise.
- [x] `/admin` — table-first operational presentation with detail drawers.

## Phase 5 — Public, marketing, auth, and system routes

- [x] `/` — preserve editorial identity; reduce showcase from seven long chapters to three focused proof stories.
- [x] `/pricing` — use marketing navigation and one meaningful badge per plan.
- [x] `/compare` and `/compare/{slug}` — evidence-led comparison, not stacked promotional cards.
- [x] `/demo` and `/demo/{slug}` — editorial catalog with consistent preview hierarchy.
- [x] `/demo/workspace` — task-first demo with contextual drawers instead of empty companion cards.
- [x] `/blog` and `/blog/{slug}` — preserve editorial reading quality; normalize artwork and index density.
- [x] `/answers` and `/answers/{slug}` — share the editorial content shell.
- [x] `/public` — useful first-run/catalog state instead of a large empty container.
- [x] `/public/{bookId}` and public chapters — prioritize cover, authorship, description, and reading.
- [x] `/public/forum` and posts — topic/reply rows rather than card-per-message.
- [x] `/public/writers/{username}` — profile masthead plus content feeds.
- [x] `/public/uploads` and `/public/analytics` — clear provenance, privacy boundary, and operational hierarchy.
- [x] Auth routes — flat, consistent form shell with compact branding.
- [x] Checkout and success — focused transaction state with no competing product navigation.
- [x] Legal, contact, copyright, font notice, refund, terms, privacy, EULA — restrained prose shell.
- [x] Status, offline, unsubscribe, callback, and error states — compact system treatment with one next action.

## Phase 6 — Assets

### Brand and platform

- [x] Verify favicon readability at 16px and 32px.
- [x] Consolidate duplicate `icon.png` and `icon-512.png` sources without breaking metadata.
- [x] Export icon-only light/dark marks on matched square canvases.
- [x] Export true horizontal light/dark logo lockups rather than resizing the square 762×727 images into horizontal slots.
- [x] Stop using CSS inversion on logo PNGs.
- [x] Replace the square `og-image.png` with a restrained 1200×630 editorial social card.

### Product screenshots

- [x] `manuscript-analysis.png` — crop to manuscript plus one meaningful continuity cue.
- [x] `manuscript-analysis-with-advisor.png` — emphasize grounded answer and cited passage.
- [x] `character-continuity.png` — one selected character, issue, and evidence passage.
- [x] `timeline-logic.png` — tighter chronology with differentiated events.
- [x] `relationship-graph.png` — graph plus one selected relationship inspector.
- [x] `editorial-review.png` — compact setup or remove from primary showcase.
- [x] `editorial-review-2.png` — show one evidence-to-decision workflow.
- [x] `notes-workspace.png` — note tree plus editor, without four permanent columns.
- [x] `export-workflow.png` — format, options, export action.
- [x] Convert oversized screenshots to responsive WebP/AVIF outputs where quality remains acceptable.

### Editorial artwork

- [x] Define one human-directed blog art system with consistent crop, palette, and subject-specific composition.
- [x] Replace or re-art-direct character/voice desk-still-life heroes.
- [x] Replace or re-art-direct continuity/timeline/canon heroes.
- [x] Replace or re-art-direct scene/structure heroes.
- [x] Replace or re-art-direct revision-process heroes.
- [x] Replace product/comparison heroes with evidence-led product or diagram imagery.
- [x] Verify all 30 current blog hero mappings and all Answers-page reuse.

## Verification log

| Date | Area | Evidence | Result |
|---|---|---|---|
| 2026-09-14 | Baseline | Static route/component/asset scan and desktop/mobile review | Audit complete; implementation started |
| 2026-09-14 | Shared product language | Focused Vitest suite (22 assertions), TypeScript, targeted ESLint | Passed |
| 2026-09-14 | Book navigation and overview | Playwright desktop-to-mobile smoke; no global overflow; visual screenshots | Passed |
| 2026-09-15 | Draft outline and notes | Focused Vitest, TypeScript, targeted ESLint, Playwright desktop/mobile smoke; deferred inspector requests and no global overflow | Passed |
| 2026-09-19 | Manuscript and scenes | Focused Vitest, TypeScript, targeted ESLint, Playwright desktop/mobile smoke; on-demand outline/inspector mounting and visual screenshot review | Passed |
| 2026-09-19 | Character Bible | Focused Vitest, TypeScript, targeted ESLint, eight Playwright character flows, desktop/mobile drawer checks, no horizontal overflow, and visual screenshot review | Passed |
| 2026-09-19 | Relationship graph | Focused Vitest, TypeScript, targeted ESLint, Playwright node/edge interaction, desktop/mobile inspector checks, no horizontal overflow, and visual screenshot review | Passed |
| 2026-09-20 | Relationship evolution | Legacy-route redirect test, local-view unit coverage, Playwright desktop/mobile smoke, no horizontal overflow, and visual screenshot review | Passed |
| 2026-09-20 | Arc timeline | Focused Vitest, TypeScript, targeted ESLint, Playwright desktop/mobile smoke, lane-filter interaction, no global horizontal overflow, and visual screenshot review | Passed |
| 2026-09-20 | Plot threads | Focused Vitest, targeted ESLint, Playwright desktop/mobile queue and details interaction, clean browser console, no global horizontal overflow, and visual screenshot review | Passed; repository-wide TypeScript currently has an unrelated `charactersPage.layoutActions.ts` contract error |
| 2026-09-20 | Setup & Payoff | Focused Vitest, targeted ESLint, Playwright desktop/mobile evidence-ledger filtering, clean browser console, no global horizontal overflow, and visual screenshot review | Passed; UI stays within the available setup/outcome evidence contract |
| 2026-09-20 | World gaps | Focused Vitest (12 checks), targeted ESLint, Playwright desktop/mobile evidence interaction, deferred canon-document body request, clean browser console, no global horizontal overflow, and visual screenshot review | Passed |
| 2026-09-20 | Series wiki | Focused Vitest, targeted ESLint, Playwright desktop/mobile list-detail filtering, route-ID normalization coverage, clean browser console, no global horizontal overflow, and visual screenshot review | Passed |
| 2026-09-20 | Story advisor | Focused Vitest, targeted ESLint, Playwright desktop/mobile Ask and Recommended checks views, deferred evidence rail, no global horizontal overflow, and visual screenshot review | Passed; removed auto-switching, decorative motion, dashboard metrics, and empty evidence chrome |
| 2026-09-20 | Ask | Focused Vitest (38 checks across route, workspace, navigation, and registry contracts), targeted ESLint, author-route redirect E2E, reader desktop/mobile question-and-cited-answer E2E, no global horizontal overflow, and visual screenshot review | Passed; author navigation no longer exposes a competing Ask destination |
| 2026-09-20 | Findings overview | Focused Vitest (30 checks across route, navigation, and registry contracts), targeted ESLint, Playwright desktop/mobile live-finding review, no global horizontal overflow, visual screenshot review, and request observation | Passed; only the book and continuity-finding data load on entry, while focused review tools remain intent-loaded |
| 2026-09-20 | Chapter reports | Focused Vitest (36 checks across local view, legacy redirect, navigation, and registry contracts), targeted ESLint, Playwright desktop/mobile chapter filtering, legacy-route redirect, no global horizontal overflow, visual screenshot review, and request observation | Passed; chapter-report data loads only in the selected local view and continuity findings are not fetched there |
| 2026-09-20 | Editorial review | Focused Vitest (4 checks), targeted ESLint, Playwright desktop/mobile document-and-findings flow, on-demand review request, session run history, no global horizontal overflow, and visual screenshot review | Passed; manuscript import was removed from this surface and result cards were flattened into evidence sections |
| 2026-09-21 | AI Beta Reader | Focused Vitest (7 checks), targeted ESLint, Playwright Configure/Run/Review flow, desktop/mobile overflow checks, clean browser runtime, request observation, and visual review of configuration, progress, and report states | Passed; configuration data is intent-loaded and nested scope/check/result cards were replaced with flat form and evidence sections |
| 2026-09-21 | Voice consistency | Focused Vitest (4 checks), targeted ESLint, selected-character Playwright flow, desktop/mobile overflow checks, clean browser runtime, request observation, and visual screenshot review | Passed; the page is now a chapter/passage review with one source pane and one evidence pane, and workspace-tree data loads only when saving a scene snapshot |
| 2026-09-21 | Book search | Focused Vitest (30 checks across route, navigation, registry, and resolver contracts), targeted ESLint, global-entry Playwright flow, semantic/thematic request observation, desktop/mobile overflow checks, clean browser runtime, and visual screenshot review | Passed; search remains in the persistent book-search control and command palette, no longer appears as a primary/More tool destination, and fires no retrieval request before submission |
| 2026-09-21 | Recaps | Focused Vitest (41 checks across recap utility, chapter list, overview, legacy route, navigation, and registry contracts), targeted ESLint, intent-load request observation, legacy redirect, desktop chapter/mobile overview overflow checks, clean browser runtime, and visual screenshot review | Passed; chapter recaps now expand beside chapter rows, the manuscript recap is compiled on Overview, and the standalone route/navigation destination was retired |
| 2026-09-22 | Revision workflow | Focused Vitest (24 checks across workflow utilities, page behavior, navigation, and deferred-query contracts), TypeScript, targeted ESLint, Playwright desktop/mobile step navigation, persistence and request observation, clean browser runtime, no global horizontal overflow, and visual screenshot review | Passed; Author Lens was renamed and removed from book navigation, Overview and Findings launch a six-step resumable flow, only the active step mounts its data work, and incomplete legacy feedback records no longer crash triage |
| 2026-09-22 | Collaboration | Focused Vitest (2 route checks), targeted ESLint, Playwright desktop/mobile invitation and activity flow, deferred activity-request observation, clean browser runtime, no global horizontal overflow, and visual screenshot review | Passed; the page is now a conventional collaborator ledger, invitations open on intent, advanced permissions stay disclosed until needed, and activity data loads only for the selected person |
| 2026-09-22 | Beta feedback | Focused Vitest (2 route checks), targeted ESLint, Playwright desktop/mobile assignment and response flow, author/reader query and detail-request observation, clean browser runtime, no global horizontal overflow, and visual screenshot review | Passed; authors now land on assignments, creation is intentional, response evidence appears only after selecting an assignment, empty secondary categories are suppressed, and the reader queue is not requested in the author view |
| 2026-09-22 | Files & Export | Focused Vitest (17 checks across file workflows, states, and navigation), targeted ESLint, Playwright publishing-settings and download flow, writer-workspace request observation, desktop/mobile overflow checks, clean browser runtime, and visual screenshot review | Passed; Import & Export is now Files & Export, one task is visible at a time, publishing metadata is disclosed only when needed, the cover remains a mobile thumbnail, and the writer workspace request waits until the reader-edition task is selected |
| 2026-09-22 | Access & Visibility | Focused Vitest route coverage, targeted ESLint, Playwright desktop/mobile access and recovery flow, no global horizontal overflow, clean browser runtime, and visual screenshot review | Passed; seven competing cards were replaced by one access model, collaborator/beta/public states read as rows, rights and moderation are secondary, and workspace-navigation controls are explicitly separated under Advanced |
| 2026-09-22 | Compliance context | Focused Vitest redirect coverage, targeted ESLint, and Playwright redirect verification | Passed; the duplicate book-scoped notice now redirects to the maintained global Security & Compliance page instead of appearing as a book workspace |
| 2026-09-22 | Dashboard shell and Library | Focused Vitest (15 checks across shell, project controls, project links, route behavior, and upload state), targeted ESLint, Playwright desktop/mobile project and upload flow, no global horizontal overflow, clean browser runtime, and visual screenshot review | Passed; the account shell uses its sidebar as the sole navigation, no longer prefetches chat or notification panels at idle, Library removes dashboard filler in favor of projects, filters form one plain toolbar, title links replace full-card overlays, empty pinned/all sections are suppressed, and chapter import requires a selected project |
| 2026-09-22 | Account notes and quotes | Focused Vitest route coverage, targeted ESLint, Playwright cross-book search, desktop/mobile overflow checks, clean browser runtime after auth-hydration gating, and visual screenshot review | Passed; both routes are compact searchable indexes with flat rows, contextual metadata, and one primary destination instead of metric strips and two-column card dashboards |
| 2026-09-22 | Writing stats | Focused Vitest populated/loading/error coverage, targeted ESLint, Playwright desktop/mobile hierarchy checks, clean browser runtime, no global horizontal overflow, and visual screenshot review | Passed; the dashboard now contains one writing-activity heatmap, one target summary, and a compact two/four-column breakdown instead of a hero plus multiple competing card groups |
| 2026-09-22 | Series management and Ask | Focused Vitest (3 checks across management and Ask routes), TypeScript, targeted ESLint, Playwright desktop/mobile master-detail and conversation flow, deferred analysis-request observation, no global horizontal overflow, and visual screenshot review | Passed; Series now renders one selected collection and row-based project ledger, creation and project assignment open on intent, world/bible analysis remains request-deferred, and Ask lives only in a series-scoped conversation instead of a duplicate modal or generic AI landing page |
| 2026-09-22 | Beta Reads | Focused Vitest, TypeScript, targeted ESLint, Playwright Assigned/In progress/Completed flow, detail-request observation, desktop/mobile overflow checks, and visual screenshot review | Passed; four backend buckets are presented as three reader-facing work states, active work is a compact row ledger, missed work is kept in completed history with a clear outcome, and assignment details no longer create an eager N+1 request fan-out |
| 2026-09-22 | Messages | Focused Vitest (7 checks across the shared panel and launcher), TypeScript, targeted ESLint, Playwright deferred-load/send flow, desktop two-pane and mobile list/thread checks, no global horizontal overflow, and visual screenshot review | Passed; conversations and people search are flat ledgers, the page reserves a dedicated thread pane, mobile navigation drills into one thread with a clear back action, and message history waits for explicit conversation selection |
| 2026-09-22 | Notifications | Focused Vitest (9 checks across the notification ledger and bell), TypeScript, targeted ESLint, Playwright chronological/unread/detail flow, desktop/mobile overflow checks, and visual screenshot review | Passed; notifications now form one chronological divided ledger, unread state is a restrained rail and tint, redundant badges and duplicate destinations were removed, and revision intelligence remains deferred until the user opens details |
| 2026-09-22 | Settings | Focused Vitest (13 account and preference checks), targeted ESLint, Playwright section tracking and desktop/mobile hierarchy checks, no global horizontal overflow, and fresh-load visual screenshot review | Passed; the summary-card dashboard and decorative goal ring were removed, categories remain scannable, all controls now share one divided form surface, option groups read as compact rows, and workspace tool visibility remains explicit without card-per-tool styling; repository-wide TypeScript currently has unrelated route typing and test DOM errors |
| 2026-09-22 | Upgrade | Focused Vitest (19 checks across pricing, shell, support, and route presentation), targeted ESLint, Playwright monthly/annual checkout flow and focused-shell assertions, and desktop/mobile visual screenshot review | Passed; Upgrade now shares the public pricing introduction and plan renderer, replaces the full dashboard sidebar/chat/notification chrome with a logo and one workspace return path, and suppresses the floating support launcher while preserving authenticated billing behavior |
| 2026-09-27 | Admin operations | Focused Vitest (3 owner, scoped-role, step-up, and unavailable-state workflows), targeted ESLint, Playwright role-area navigation and request observation, desktop moderation/overview and mobile access visual review, and horizontal-overflow checks | Passed; the console now fetches only the active operational domain, scoped admins land on their first permitted area, moderation/refund/access/audit queues use tables, record decisions open in one detail pane, and infrequent enforcement/configuration forms stay collapsed until requested; repository-wide TypeScript remains blocked by unrelated route-typing and test-DOM errors |
| 2026-09-27 | Homepage | Focused Vitest (5 showcase behavior and asset checks plus shared runtime coverage), targeted ESLint, Playwright desktop/mobile hierarchy and overflow checks, and full-page visual review | Passed; seven long showcase chapters and nine below-fold assets became three evidence stories and three lazy visuals, thumbnail-swap motion was removed, proof cards became divided lists, and workflow, comparison, FAQ, format, and closing-CTA surfaces were flattened without losing the editorial identity |
| 2026-09-27 | Public pricing | Focused Vitest (shared billing and route coverage), targeted ESLint, Playwright public monthly/annual and authenticated upgrade flows, desktop/mobile overflow checks, and full-page visual review | Passed; public pricing now uses the marketing header, plan columns share one bordered comparison surface, each plan has at most one meaningful marker, repeated uppercase plan labels were removed, and feature rows are divided rather than stacked inside oversized cards |
| 2026-09-27 | Comparison routes | Focused Vitest (17 public-route and comparison checks), targeted ESLint, Playwright index-to-detail navigation, desktop/mobile overflow checks, and full-page visual review | Passed; the comparison catalog is now one editorial ledger, detail pages lead with a neutral methodology note and a single evidence matrix, verdicts and recommendations use divided sections, and repeated card labels, nested explainer cards, and pill navigation were removed |
| 2026-09-27 | Demo library and case studies | Focused Vitest (22 public-route, slug, and workspace checks), targeted ESLint, Playwright catalog-to-case-study navigation, desktop/mobile overflow checks, no API requests, and full-page visual review | Passed; customer-facing copy now demonstrates source evidence instead of discussing SEO strategy, the catalog is a source/workflow ledger, case studies use one reading column with a pull quote and divided supporting links, and promotional explainer/stat cards were removed |
| 2026-09-27 | Interactive demo workspace | Focused workspace behavior coverage, targeted ESLint, Playwright decision/reset flow, zero API calls, desktop/mobile overflow checks, and visual review before and after a decision | Passed; the full marketing footer was removed from the task, the brand mark is compact, empty chapter/plan cards stay absent, progress and instructions share one quiet context rail, and chapter or revision context appears only after the corresponding action |
| 2026-09-27 | Blog and Answers | Focused Vitest (21 index, slug, metadata, and presentation checks), targeted ESLint, Playwright search/copy/theme/navigation flows, desktop/mobile overflow checks, and full-page visual review | Passed; Blog retains its editorial feature and four recent images but removes duplicate artwork from a complete text archive, articles preserve the long-form reading shell, Answers shares that shell with a direct short-answer lead, and answer pages no longer load decorative hero or related-card images that add latency without aiding the task |
| 2026-09-27 | Public reading and community | Focused Vitest (public catalog, book, footer, forum, writer, upload, and analytics coverage), targeted ESLint, Playwright catalog-to-book-to-chapter and forum-to-thread-to-profile flows, desktop/mobile overflow checks, and full-page visual review | Passed; public books and ranked uploads are cover-led ledgers, book pages disclose analytics instead of leading with them, chapter reading suppresses the marketing footer, forum topics/comments and writer activity use divided feeds, profile metrics are compact, and public analytics clearly excludes private workspace traffic without becoming a card dashboard |
| 2026-09-27 | Authentication | Focused Vitest (25 auth runtime, billing-auth, and Google OAuth checks), targeted ESLint, Playwright invalid-login, registration, and recovery-route checks, desktop/mobile overflow checks, and visual review | Passed; login, registration, verification, recovery, reset, and username completion now share one flat form shell, use the real compact icon asset, remove the floating header and form cards, replace uppercase field labels with sentence case, and keep status treatment limited to actionable feedback |
| 2026-09-27 | Checkout and confirmation | Focused Vitest (24 billing runtime and Paddle contract checks), targeted ESLint, Playwright checkout and missing-reference confirmation states, desktop/mobile overflow checks, and visual review | Passed; checkout no longer inherits the marketing footer, the shell contains only compact brand/pricing escape paths, status is a single restrained callout, confirmation details share one divided record, and transaction actions have a clear primary/secondary hierarchy |
| 2026-09-27 | Legal and contact documents | Focused Vitest (19 static-route checks), targeted ESLint, Playwright Contact and Privacy desktop/mobile checks, horizontal-overflow checks, and full-page visual review | Passed; the shared document shell preserves numbered sections and contents navigation while flattening notices, contact information, and policy rail facts into bordered prose structures; self-referential design copy was removed from Contact and Privacy |
| 2026-09-27 | System and recovery states | Focused Vitest (37 static, unsubscribe, callback, auth-runtime, and global-error checks), targeted ESLint, Playwright Status, Offline, and missing-token Unsubscribe checks, desktop/mobile overflow checks, and visual review | Passed; the placeholder status essay became an honest compact incident surface, Offline and Unsubscribe use the compact real mark and one recovery action, the OAuth callback has a branded progress state, and the global error page offers one retry action with support as inline fallback |
| 2026-09-28 | Brand, product captures, and editorial artwork | Visual review of 16px/32px favicons, square icon marks, horizontal lockups, social card, nine live-product captures, six editorial masters, all 50 Blog/Answers mappings, and desktop/mobile marketing routes; focused Vitest (94 checks), targeted ESLint, and Playwright product-capture plus homepage/editorial flows | Passed; duplicate and CSS-inverted branding was removed, the 1200×630 social card uses the real lockup, legacy full-page product PNGs became focused lossless WebP evidence views, and thirty repetitive desk-still-life heroes became a six-category human-directed editorial system with accurate shared alt text and substantially lower transfer weight |
| 2026-09-30 | Four-viewport route audit | Production Playwright sweep of every listed authenticated and public route at 1440×900, 1280×800, 768×1024, and 390×844; checked document overflow, clipped controls, duplicate active IDs, unnamed fields, and fixed-control collisions | Passed; the final tablet defects in the manuscript formatting panel and revision-workflow step strip were corrected and rechecked |
| 2026-09-30 | Full production behavior and accessibility | Production standalone build with mocked network boundary; Playwright accessibility, keyboard/focus, route, and user-flow suites | Passed: 112 of 112 tests |
| 2026-09-30 | Final static and unit gates | Surface-size guard, TypeScript, ESLint, Vitest, and normal production build | Passed: 241 test files and 1,121 unit tests; 107 routes built. Static generation used the designed fallback when the local API on port 8000 was unavailable |

## Closure

The completion gate below is satisfied. The redesign now uses restrained shared primitives, job-based book navigation, local inspectors instead of global workspace sidebars, intent-loaded expensive tools, contextual reader actions, editorially directed assets, and explicit empty/error/processing states. The final production audit found no route-level clipping, global horizontal overflow, duplicate active IDs, unnamed form fields, or fixed-control collisions at the four release viewports. No new runtime dependency was introduced.

## Completion gate

The redesign is complete only when:

1. Every checklist item above is completed, intentionally superseded with a documented reason, or proven not applicable.
2. The primary public, dashboard, reader, and author workflows have been visually reviewed with realistic data and empty/error/processing states.
3. The application no longer relies on repeated cards, pills, uppercase microcopy, decorative motion, or redundant navigation to create hierarchy.
4. Performance verification shows no material regression in navigation, first content render, editor interaction, graph initialization, or marketing image loading.
5. Automated unit, type, build, surface-size, accessibility, and E2E checks pass.
