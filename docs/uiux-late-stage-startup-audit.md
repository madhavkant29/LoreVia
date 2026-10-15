# LoreVia UI/UX Vulnerability Audit for Late-Stage Startup Readiness

> Historical audit. Active implementation and verification are tracked in
> [`frontend-professional-ui-redesign-tracker.md`](./frontend-professional-ui-redesign-tracker.md).

Date: 2026-06-29

Implementation status: Closed on 2026-09-30. The findings were resolved through the frontend professional UI redesign, and the final release evidence is recorded in the [redesign tracker](./frontend-professional-ui-redesign-tracker.md). The production verification covered every listed authenticated and public route at desktop, laptop, tablet, and 390px mobile widths, plus 1,121 unit tests and 112 end-to-end tests.

## Scope and Method

This audit reviews LoreVia's frontend experience as a late-stage startup product, with emphasis on user trust, information architecture, cognitive load, progressive disclosure, accessibility, onboarding, empty/error states, and enterprise polish. The goal is not to remove features. The goal is to make the product feel more controlled by hiding, grouping, personalizing, and revealing complexity at the right time.

The requested five-agent structure was attempted:

- Agent 1, Research: spawned, but returned a usage-limit error before producing output.
- Agent 2, Analysis A: spawned, but returned a usage-limit error before producing output.
- Agent 3, Compilation: spawned, but returned a usage-limit error before producing output.
- Agent 4, Reviewer A: spawned, but returned a usage-limit error before producing output.
- Agent 5, Reviewer B: spawned, but returned a usage-limit error before producing output.

Because the subagents did not produce usable findings, this document consolidates the same role split manually:

- Research criteria: late-stage SaaS/product-led UX expectations.
- Analysis: frontend code and route inspection.
- Compilation: severity model and roadmap.
- Review A: accessibility, state clarity, consistency.
- Review B: retention, discoverability, personalization, and supportability.

## Benchmark Criteria

The audit criteria are based on three practical standards:

- Progressive disclosure: reveal advanced functionality only when the user needs it, while keeping it reachable for expert users. Reference: Nielsen Norman Group, "Progressive Disclosure" (https://www.nngroup.com/articles/progressive-disclosure/).
- Accessibility and operability: interactive states, status messages, target sizes, focus visibility, and consistent semantics should align with WCAG 2.2 expectations. Reference: W3C WCAG 2.2 (https://www.w3.org/TR/WCAG22/).
- Enterprise product clarity: empty states should explain what happened, why it matters, and what to do next. Reference: Atlassian Design System empty-state guidance (https://atlassian.design/components/empty-state/usage/).

## Severity Model

- P0: Blocks core task completion, causes destructive action risk, or creates severe trust/accessibility failure.
- P1: Materially increases churn, support load, user error, or late-stage sales friction.
- P2: Reduces perceived polish, discoverability, or workflow speed for important but recoverable paths.
- P3: Minor consistency or preference gap.

## Executive Summary

LoreVia has strong feature depth and several good UX primitives already: dashboard shells, empty-state components, status toasts, processing panels, and a book workspace nav that already hides some advanced tools by default. The main late-stage risk is not feature absence. The risk is that the app exposes too much structure at once, with too few persistent user-level preferences for controlling that complexity.

The highest-impact work is to turn the existing local and route-specific hiding behavior into a coherent "workspace complexity" system:

- Persist advanced-tool visibility as a preference.
- Add role/task-based presets such as "Drafting", "Review", "Reader", "Publisher", and "Power user".
- Let users hide/unhide top-level dashboard items, book workspace sections, secondary cards, and side panels.
- Centralize empty/loading/error patterns so every surface feels equally mature.
- Add settings for "Navigation and workspace visibility" rather than scattering toggles inside individual routes.

## Findings

### P1: Advanced Tool Hiding Exists, But It Is Local and Non-Persistent

Evidence:

- `frontend/src/components/layout/AuthorToolsNav.tsx` defines advanced tools such as Foreshadowing, World Gaps, Series Wiki, Search Passages, Recaps, Analysis, and Author Lens as `advanced: true`.
- The same component stores `showAdvanced` in local React state only.
- `frontend/src/lib/stores/preferencesStore.ts` persists theme and timeline collapsed sections, but does not persist book workspace nav visibility.

Why this matters:

For a late-stage startup product, a user who customizes their workspace expects that simplification to survive route changes, refreshes, sessions, and ideally devices. The current toggle is a useful first step, but it behaves more like a temporary reveal than an intentional product preference.

User impact:

- Returning users repeatedly re-encounter the default IA rather than their chosen workspace.
- Advanced users cannot keep advanced tools open.
- Newer users may not understand why a tool they saw before disappeared after a refresh.

Recommended fix:

- Extend `preferencesStore` with a persisted `workspaceNavAdvancedVisibleByBook` or `workspaceComplexityMode`.
- Add global complexity modes: `focused`, `standard`, and `power`.
- Keep the current "Show advanced tools" button, but make it update persisted preferences.
- Add a "Reset workspace layout" action in Settings.

Do not remove:

- Keep all advanced features.
- Keep direct routes addressable.
- Keep active advanced routes visible even when advanced mode is hidden, as the current implementation already does.

### P1: There Is No Dedicated Visibility/Personalization Settings Area

Evidence:

- `frontend/src/app/(dashboard)/settings/page.tsx` includes Account, Public identity, Appearance, Reading behavior, Privacy, Emails, Writing goals, Session, and Danger Zone.
- The preferences store currently persists theme and timeline collapse state only.

Why this matters:

The product is feature-rich enough to require workspace-level personalization. Late-stage customers, especially teams and serious authors, need to make the interface fit their workflow without losing access to capability.

User impact:

- Users cannot hide dashboard sections they do not use.
- Users cannot choose a default workspace persona.
- Support cannot tell users "turn on focused mode" or "restore hidden tools" because there is no single control surface.

Recommended fix:

- Add a Settings section named "Workspace visibility".
- Include toggles for:
  - Show advanced author tools by default.
  - Show public/social tools in sidebar.
  - Show billing/pricing nav item in main sidebar.
  - Show secondary workspace cards on book overview.
  - Default book workspace mode: Reader, Author, Last used.
- Add a visible "Hidden tools" manager to unhide features.

Do not remove:

- Keep all nav items and features available through search/command palette/direct links.
- Treat hiding as a user preference, not authorization.

### P1: Book Workspace Navigation Is Dense Enough to Need Task-Based Presets

Evidence:

- `AuthorToolsNav` has four sections: Write, Story Bible, Analyze, and Share & Export.
- The book nav exposes more than twenty possible destinations before route-level content appears.
- Some advanced items are hidden by default, but primary sections still contain many specialized tools.

Why this matters:

Late-stage products usually support both first-time and expert users. LoreVia's current structure is closer to an expert console. That is useful for power users, but it raises cognitive load during onboarding, trial conversion, and user reactivation.

User impact:

- New authors may not know whether to open Story Advisor, Editorial Review, Analysis, Reports, Recaps, or Author Lens.
- Similar-sounding analysis routes compete with each other.
- Collaboration and beta-feedback tools are presented beside drafting and export tools without a clear "what job am I doing now?" model.

Recommended fix:

- Add task-based nav presets:
  - Draft: Overview, Manuscript, Chapters, Notes, Export.
  - Review: Story Advisor, Editorial Review, Voice, Reports.
  - Story Bible: Characters, Relationships, Timeline, Plot Threads.
  - Publish/Share: Collaborators, Beta Feedback, Public, Export.
  - Power: all visible.
- Use presets as filters over the existing nav model.
- Keep section headers but add a compact segmented control above the nav.

Do not remove:

- Do not delete routes or features.
- Hide non-selected preset groups and keep a "More tools" reveal affordance.

### P1: Dashboard Sidebar Mixes Core Work, Public Tools, Stats, Pricing, and Settings Without User Control

Evidence:

- `DashboardSidebar.tsx` hard-codes Library, Notes, Quotes, Series, Beta Reads, Public Uploads, Stats, Pricing, and Settings.
- There is one hard-coded primary/secondary split, but no user or role-based hiding.

Why this matters:

Late-stage startup UI should help users understand the primary path immediately. A sidebar is prime navigation real estate. Public Uploads, Stats, Pricing, and Settings are legitimate features, but not every user should see them with the same prominence every day.

User impact:

- Users focused on drafting see public/social and billing destinations in the same persistent nav.
- Users who never use quotes, beta reads, or public uploads cannot simplify the shell.
- Pricing in the core app nav may feel transactional once a user has already subscribed.

Recommended fix:

- Keep the hard-coded default as "standard".
- Add user-level sidebar visibility preferences.
- Add role-aware default ordering:
  - New/free user: Library, Upload/Create, Pricing, Settings.
  - Author user: Library, Notes, Series, Beta Reads, Stats, Settings.
  - Public/community user: Public Uploads, Public Analytics, Forum/Profile surfaces.
- Add an "Edit sidebar" command in Settings and command palette.

Do not remove:

- Keep Pricing visible for free/trial users.
- For paid users, allow Pricing to be hidden or moved under Account.

### P1: Settings Page Is Comprehensive but Not Scannable Enough for Enterprise Maturity

Evidence:

- `settings/page.tsx` is a large client component with nine section anchors and many unrelated account, identity, appearance, privacy, email, goal, session, and danger-zone actions.
- It injects a large page-specific style block and tracks active section by scroll position.

Why this matters:

Settings is where late-stage users expect trust, control, and administrative clarity. A long single-page settings surface can work, but it needs strong grouping, search, and a predictable information architecture.

User impact:

- Users may not find privacy, data export, billing, visibility, and email preferences quickly.
- Workspace visibility preferences have no natural home today.
- Team and enterprise buyers may expect workspace, account, privacy, billing, notifications, and data controls to be clearly separated.

Recommended fix:

- Split settings into stable categories:
  - Account and billing.
  - Identity and public profile.
  - Workspace visibility.
  - Reading and writing preferences.
  - Notifications and emails.
  - Privacy and data.
  - Security/session.
- Add settings search.
- Add "recently changed" inline confirmations that persist long enough to review.
- Keep the single-page version on mobile if route splitting is not worth it yet.

Do not remove:

- Keep the existing setting actions.
- Rehome them into clearer sections.

### P1: Universal Empty States Are Not Used Everywhere, Which Weakens Product Consistency

Evidence:

- `ActionableEmptyState.tsx` supports primary and secondary actions.
- `WorkspaceEmptyState` supports title/body only and no action slot.
- Several routes use custom empty/loading/error copy rather than a single mature empty-state pattern.

Why this matters:

Empty states are conversion moments. For LoreVia, empty states often happen when a user has not uploaded a manuscript, processing is incomplete, or analysis has not run yet. Those moments need confident guidance.

User impact:

- Some empty states explain what is missing but do not give the next action.
- Similar "no data yet" moments feel different across dashboard, reader, public, and analysis routes.
- Users may think a feature is broken when it is waiting for import, extraction, or plan access.

Recommended fix:

- Merge `WorkspaceEmptyState` and `ActionableEmptyState` into a single system-level primitive with:
  - Title.
  - Cause.
  - Next action.
  - Secondary action.
  - Optional "hide this card" affordance.
  - Optional plan/processing reason.
- Create standard variants: no-projects, processing, gated, no-results, failed-load, empty-collaboration, empty-public-profile.

Do not remove:

- Keep route-specific copy where domain nuance matters.
- Standardize structure and behavior, not every sentence.

### P2: Reader Toolbar Uses a Separate Navigation Pattern From the Book Workspace

Evidence:

- `ReaderToolbar.tsx` exposes Library, Settings, theme, Back to book, Summary, Graph, Ask with citations, and Search passages in a reading-specific toolbar.
- The book overview uses `AuthorToolsNav` with a different navigation model.

Why this matters:

Separate reader chrome can be appropriate, but the mental model should remain consistent. A reader moving from chapter view back to book overview should not feel like they entered a different product.

User impact:

- Users must learn two navigation systems for the same book.
- Tools such as Graph, Ask, Search, and Summary appear in different labels and placements depending on view.
- Mobile users get a menu of chips rather than the sectioned workspace model.

Recommended fix:

- Keep the reader toolbar for immersion.
- Add a compact "Book tools" menu that reuses the same nav item metadata as `AuthorToolsNav`.
- Let users hide individual reader toolbar actions.
- Persist reader toolbar density: minimal, standard, power.

Do not remove:

- Keep quick access to Summary, Ask, Search, and Graph.
- Make them configurable and metadata-driven.

### P2: Loading and Processing States Are Good, But They Need a Cross-Product State Taxonomy

Evidence:

- Upload progress distinguishes "Uploading file" from "Handing off for processing".
- Book overview shows `ProcessingStatusPanel`, project signals, skeletons, and retry logic.
- `ResponsivenessStatus.tsx` uses `role="status"` and `aria-live="polite"` for processing.

Why this matters:

LoreVia has long-running AI and parsing workflows. Late-stage startup users need confidence that the system is working, what stage it is in, what can be safely done while waiting, and what to do if it stalls.

User impact:

- Some surfaces explain state well, while others use local phrases like "Building your timeline" or generic loading placeholders.
- Users may not understand when analysis is unavailable because processing is incomplete versus because the plan is gated versus because the request failed.

Recommended fix:

- Define shared states:
  - Uploading.
  - Queued.
  - Parsing.
  - Extracting.
  - Indexing.
  - Ready.
  - Partial ready.
  - Failed recoverable.
  - Failed needs support.
- Use a common component for every long-running manuscript workflow.
- Add "notify me when ready" or "hide this while processing" controls for long-running panels.

Do not remove:

- Keep existing progress panels.
- Normalize copy and affordances across surfaces.

### P2: Component Styling Is Fragmented Across Tailwind, Global App Classes, and Page-Injected CSS

Evidence:

- `Button.tsx` defines global variants, but many pages and components still create custom buttons with local class strings.
- `settings/page.tsx` injects a large settings-specific style block.
- Reader toolbar and book nav each define separate tone maps.

Why this matters:

Late-stage startup polish depends on consistency. Fragmented styling increases the chance that focus states, target sizes, disabled states, hover states, and responsive behavior drift across surfaces.

User impact:

- Some controls feel like different design systems.
- Accessibility fixes must be made repeatedly in many places.
- Enterprise buyers notice inconsistency in high-trust areas such as Settings, Billing, Privacy, and Delete Account.

Recommended fix:

- Promote page-specific settings controls into reusable primitives.
- Add focus-visible, min-target-size, disabled, and aria patterns to the base Button where possible.
- Audit custom buttons and links into a small set of variants.
- Add a "dense operational surface" variant for dashboards and an "immersive reading" variant for reader mode, but keep shared semantics.

Do not remove:

- Keep visual differentiation for reader mode and manuscript tools.
- Consolidate primitives and semantics.

### P2: Hiding Exists for Project Removal/Archive, But Not as a General UI Simplification Pattern

Evidence:

- Library project actions include Archive, Remove, Restore, Pin, Publish, and Delete permanently.
- Project hiding is content-level, not UI-level.

Why this matters:

The user explicitly asked about hiding and unhiding features. LoreVia already has content visibility patterns, but needs feature visibility and panel visibility patterns too.

User impact:

- Users can hide projects, but not the tools or panels that create daily clutter.
- "Remove" and "Archive" are product-content concepts; they do not help users simplify the UI.

Recommended fix:

- Add "Hide from workspace" affordances to noncritical cards and panels.
- Add a central "Hidden items" control in Settings.
- Use reversible language:
  - Hide from sidebar.
  - Hide this card.
  - Restore hidden tools.
  - Reset layout.

Do not remove:

- Do not merge content hiding and feature hiding into one ambiguous action.
- Keep destructive actions separate and strongly confirmed.

### P2: There Is No Single "What Should I Do Next?" System Across the App

Evidence:

- Library has next-best-actions logic.
- Book overview has project signals and recent activity.
- Author dashboard has secondary tabs and quick links.

Why this matters:

For a late-stage product, the app should steer users without overwhelming them. LoreVia has many local "next step" patterns, but they are not yet a consistent guidance layer.

User impact:

- A new user may see many features but no dominant path.
- A returning user may need to infer whether they should continue drafting, run analysis, review flags, export, or invite collaborators.

Recommended fix:

- Create a shared "Next best action" service/model for frontend surfaces.
- Let users hide or snooze recommendations.
- Use priority rules:
  - Recover failed processing.
  - Continue active draft.
  - Resolve high-severity story issues.
  - Review fresh beta feedback.
  - Export/share when draft is ready.

Do not remove:

- Keep quick links and recent activity.
- Add a consistent priority layer above them.

### P3: Some Controls Use Text Where Icon-Only With Tooltip Would Reduce Density

Evidence:

- Dashboard nav and reader toolbar use several text actions.
- The app already has Tooltip, icon patterns, and compact nav affordances.

Why this matters:

For dense operational surfaces, icons with accessible labels and tooltips can reduce visual weight, especially for repeated or familiar actions such as theme, pin, menu, view mode, filters, and quick tools.

User impact:

- Dense toolbars feel busier than necessary.
- Labels compete with primary content on smaller screens.

Recommended fix:

- Convert repeated tool actions to icon buttons with accessible labels and tooltips.
- Keep text labels for primary workflow actions and destructive actions.
- Add a user preference for compact vs comfortable density.

Do not remove:

- Do not hide labels for unfamiliar, high-stakes, or destructive actions.

## Deep Scan Addendum

This second pass scanned the current frontend route/component tree for broader UX risk patterns. The current app has 78 `page.tsx` routes:

- 27 reader/book workspace routes.
- 12 dashboard routes.
- 8 public/community routes.
- 7 auth routes.
- 24 marketing, legal, checkout, demo, status, and system routes.

The largest frontend UX surfaces are also very large implementation surfaces:

- `frontend/src/app/(reader)/[bookId]/manuscript/page.tsx`: 4677 lines.
- `frontend/src/app/(reader)/[bookId]/characters/page.tsx`: 4261 lines.
- `frontend/src/app/(dashboard)/library/LibraryClient.tsx`: 1968 lines.
- `frontend/src/components/reader/VaultNotesEditor.tsx`: 1762 lines.
- `frontend/src/components/reader/WorldbuildingWorkspace.tsx`: 1710 lines.
- `frontend/src/app/(reader)/[bookId]/scenes/page.tsx`: 1451 lines.
- `frontend/src/components/intelligence/RelationshipGraph.tsx`: 1413 lines.
- `frontend/src/app/(dashboard)/settings/page.tsx`: 1340 lines.
- `frontend/src/app/(reader)/[bookId]/advisor/page.tsx`: 1197 lines.

These sizes are not only maintainability signals. They also explain why similar states, menus, focus behavior, and hide/show patterns drift between surfaces.

### P1: Command Palette Is Not Yet the Canonical Escape Hatch for Hidden or Advanced Tools

Evidence:

- `frontend/src/components/ui/CommandPalette.tsx` defines seven base actions: Library, Public Uploads, Public Forum, Writing Stats, Notifications, Settings, and Pricing.
- Per book, it adds only Overview, Manuscript, Ask, Characters, Graph, Advisor, and Search.
- It does not include many advanced or hidden-prone routes such as Editorial Review, Voice, Reports, Timeline, Plot Threads, Foreshadowing, World Gaps, Series Wiki, Collaboration, Beta Feedback, Export, Author Lens, Chapters, Scenes, Notes Workspace, or Recaps.
- `UxRuntimeProvider` mounts `CommandPalette` globally, so this component is already positioned to become the universal tool finder.

Why this matters:

If LoreVia adds stronger hide/unhide controls, users need a reliable way to recover hidden tools. A command palette is the right escape hatch, but only if it indexes the same tool registry as the sidebar, book nav, reader toolbar, and hidden-items manager.

User impact:

- Users may hide a tool, then not find it by search.
- Power users cannot rely on command search as a complete navigation layer.
- Support cannot tell users "press Ctrl/Cmd K and search for the tool" unless the palette is comprehensive.

Recommended fix:

- Create a shared `workspaceToolRegistry` that powers:
  - `AuthorToolsNav`.
  - `ReaderToolbar` book tools.
  - `CommandPalette`.
  - Settings hidden-items manager.
  - Mobile action sheets.
- Add hidden-state metadata to command results:
  - "Hidden from sidebar."
  - "Advanced tool."
  - "Locked by plan."
  - "Unavailable until processing completes."
- Add command actions for "Show hidden tools", "Edit sidebar", "Switch to focused mode", and "Reset workspace layout".

Do not remove:

- Keep the current command palette.
- Expand it into a complete recoverability layer before increasing default hiding.

### P1: Shared Dialogs Need a Stronger Accessibility and Modal Contract

Evidence:

- `ConfirmDialog` restores previous focus after close and uses `role="dialog"` plus `aria-modal="true"`, but there is no focus trap and no Escape handling in the dialog itself.
- `PromptDialog` focuses the input and supports Escape only from the input/textarea handlers, not from the whole modal shell.
- `CommandPalette` handles Escape globally and focuses the input, but also lacks a focus trap.
- Some feature pages define local modals separately, such as beta feedback requirement/success modals, rather than reusing the shared dialog primitives.

Why this matters:

Late-stage startup quality depends on predictable overlay behavior. If dialogs do not trap focus, keyboard and screen-reader users can tab into obscured page controls behind the overlay. If Escape behavior varies, users lose trust in high-stakes flows such as delete, publish, collaboration, and beta feedback.

User impact:

- Keyboard users can get disoriented in modal flows.
- Destructive confirmations may not behave consistently across surfaces.
- Local modal implementations increase the chance that one flow misses accessibility semantics or focus recovery.

Recommended fix:

- Add a shared modal primitive with:
  - Focus trap.
  - Escape handling.
  - Initial focus choice.
  - Focus restoration.
  - Overlay click policy.
  - `aria-describedby` support.
  - Scroll locking.
- Refactor `ConfirmDialog`, `PromptDialog`, `CommandPalette`, upload modal, beta feedback modals, and public/forum composer dialogs onto this primitive.
- Add unit tests for tab containment, Escape behavior, focus restoration, and screen-reader labels.

Do not remove:

- Keep current confirm/prompt APIs.
- Improve their internals so existing callers inherit better behavior.

### P1: Route-Level Mega Surfaces Are Creating Product Inconsistency Risk

Evidence:

- Manuscript, characters, library, notes vault, worldbuilding, scenes, relationship graph, settings, and advisor surfaces are all above or near 1000 lines.
- These route/components define many local controls, local loading states, local empty states, local tone maps, and local form styles.
- The original audit already found fragmented button, empty-state, and processing patterns; this deep scan shows the fragmentation is structurally reinforced by large route files.

Why this matters:

At late-stage startup scale, UX consistency is not only a design issue. It is a system issue. When every major surface owns its own interaction contract, teams cannot safely add hide/unhide controls, accessibility improvements, or onboarding guidance once and expect the product to improve everywhere.

User impact:

- Similar actions feel different depending on whether the user is in manuscript, characters, library, scenes, notes, or settings.
- Fixing one workflow may leave parallel workflows unchanged.
- Advanced users learn local quirks instead of product-wide patterns.

Recommended fix:

- Define product-level UX contracts for:
  - Page header.
  - Primary/secondary actions.
  - Empty/loading/error/gated states.
  - Destructive actions.
  - Filter/search panels.
  - Hide/unhide controls.
  - Mobile action bar.
  - Local panels and right rails.
- Split large route files around these contracts, starting with non-risky extractions:
  - View-state selectors.
  - Toolbar/action definitions.
  - Empty-state builders.
  - Dialog bodies.
  - Card renderers.
- Add a route-surface inventory test or lint report that flags new page files above an agreed threshold unless intentionally exempted.

Do not remove:

- Do not shrink functionality.
- Shrink local decision-making by moving repeated behavior into shared primitives.

### P1: Plan Gating Can Hide Capability Without Enough Context

Evidence:

- `AuthorFeatureComponent` returns `locked` for users without author access, and the default `locked` value is `null`.
- `AuthorToolsNav` wraps author-only sections with `AuthorFeatureComponent locked={null}` in some cases.
- `ContextualUpgradePrompt` exists and gives users a clear upgrade path, but gating and upgrade copy are still scattered across notes, quotes, stats, advisor, export, public forum, upload mode, and book overview.

Why this matters:

Hiding and gating are different product concepts. Hiding is user-controlled simplification. Gating is commercial or permission-based. If both result in disappearing UI, users may interpret plan limits as missing features or broken navigation.

User impact:

- Free users may not understand which tools exist, which are locked, and which are simply hidden.
- Users moving from trial to free can feel that the product changed shape unexpectedly.
- Sales/support loses a chance to explain value at the moment of intent.

Recommended fix:

- Create a shared gated-tool state:
  - Visible but compact by default.
  - Clear lock reason.
  - Upgrade or trial CTA.
  - "Hide locked tools" user preference.
  - "Show locked tools" recovery action.
- Treat plan-gated, permission-gated, processing-gated, and user-hidden states as separate metadata values in the shared tool registry.

Do not remove:

- Keep plan gates.
- Do not make gated tools noisy for paid users or users who choose to hide them.

### P2: First-Time Guidance Exists as Infrastructure But Is Not Productized

Evidence:

- `FirstTimeTooltip` exists, stores dismissal in `localStorage`, and renders a dismissible "Got it" card.
- Current non-test usage search found only the component definition, not product integration.
- `ShortcutHelp` is globally mounted, but opens only when the user presses `?`; there is no visible help affordance in the dashboard or workspace chrome.

Why this matters:

LoreVia's complexity is not self-explanatory. A late-stage product should guide users through high-value workflows without relying on docs, support, or accidental discovery of shortcuts.

User impact:

- First-time users may not learn command palette, advanced tools, quote mode, story bible, beta feedback, or revision workflows.
- Users who would benefit from "focused mode" or "show advanced tools" may never discover those controls.
- Shortcut help is useful only after a user knows the shortcut exists.

Recommended fix:

- Promote guidance into a first-class onboarding system:
  - Visible help button in dashboard and book workspace chrome.
  - Contextual first-run tips for Library, Book Overview, Manuscript, Story Advisor, Character Bible, and Export.
  - Dismissal state in `preferencesStore`, not scattered raw `localStorage`.
  - "Restart onboarding" in Settings.
- Keep tips tied to user intent, not page count. For example, show a "review tools" tour after processing completes.

Do not remove:

- Keep `FirstTimeTooltip` as a reusable primitive if it is improved.
- Do not add blocking tours; make guidance dismissible and recoverable.

### P2: Mobile Next-Best Actions Are Underused

Evidence:

- `MobileActionBar` is used in Library and ReaderView only.
- Library maps it to next-best-actions such as new project, check processing, or continue project.
- ReaderView maps it to Summary and Ask LoreVia.
- Other dense workflows such as manuscript, characters, advisor, collaboration, beta feedback, export, scenes, and notes do not currently use this shared mobile action layer.

Why this matters:

The desktop product has enough space for sidebars, panels, and rails. Mobile users need stronger prioritization. A late-stage app should not force mobile users to hunt through dense screens for the primary next action.

User impact:

- Mobile users get a good action bar in a few places but not consistently.
- Complex tools may be technically responsive but still operationally hard to use.
- Hide/unhide controls may be less discoverable on mobile unless the action system becomes product-wide.

Recommended fix:

- Define a route-level `primaryActions` contract.
- Use `MobileActionBar` or a successor on every major workspace surface.
- Add a persistent "More" action that opens hidden or advanced route actions.
- Let users hide or reorder mobile actions per workspace mode.

Do not remove:

- Keep route-specific action nuance.
- Normalize how the top one or two mobile actions are surfaced.

### P2: Interactive Project Cards Use Custom `role="button"` Semantics With Nested Controls

Evidence:

- Library grid and row project cards render `<article role="button" tabIndex={0}>`.
- They manually handle Enter/Space to open the project.
- They also contain nested buttons/links for project actions, add chapter, publish, archive, remove, and delete.
- The implementation explicitly guards nested clicks by checking whether the event target is inside `button,a`.

Why this matters:

Clickable cards with nested interactive controls can be made to work, but they are easy to get wrong for keyboard users, assistive tech, and future contributors. A late-stage startup should reduce fragile interaction patterns in core surfaces like the library.

User impact:

- Keyboard focus may be harder to predict.
- Screen-reader users may hear a generic button instead of a richer article/link structure.
- Future new actions inside the card could accidentally trigger navigation or require more guard logic.

Recommended fix:

- Prefer a card structure with:
  - A real primary link around the project title/cover/content area.
  - Separate explicit buttons for actions.
  - No outer `role="button"` wrapper.
- If the full-card click target is retained, add focused tests for nested controls, keyboard navigation, and screen-reader labels.

Do not remove:

- Keep fast click-to-open behavior.
- Implement it with safer semantics.

### P2: Public/Private Context Boundaries Need Stronger Visual Separation

Evidence:

- Dashboard navigation includes Public Uploads beside private writing tools.
- Library project menus include "Publish publicly" and "Unpublish public book".
- Public routes include public uploads, public analytics, forum, public writer profiles, public books, and public chapters.
- Collaboration and beta feedback routes also bridge private manuscript work with external readers.

Why this matters:

For serious authors and enterprise-grade trust, the product must make the boundary between private manuscript workspace, collaborator access, beta readers, and public publishing unmistakable.

User impact:

- Authors may hesitate to use public/community tools if they are unsure what becomes visible.
- Public publishing actions carry trust and rights implications.
- Users may not distinguish "shared with collaborator", "assigned to beta reader", "public upload", and "published public sample" quickly enough.

Recommended fix:

- Add a consistent visibility badge system:
  - Private.
  - Shared with collaborators.
  - Assigned to beta readers.
  - Public sample live.
  - Public forum/discussion.
- Add a "Visibility Center" for each project with all share/public states in one place.
- Allow users to hide public/community nav from the main dashboard while preserving access through the visibility center and command palette.

Do not remove:

- Keep public/community growth features.
- Separate them visually from private manuscript work until the user opts in.

### P3: Floating Create Actions Are Hover/Focus-Dependent and Need a Clear Expanded State

Evidence:

- `CreateFab` reveals Add Scene, Add Note, and Add Character through hover/focus-within classes.
- The visible control is a `+ Create` button, but it does not hold an explicit `aria-expanded` state or click-driven open state.

Why this matters:

Hover-dependent reveal patterns are fragile on touch devices and can be unclear for keyboard users unless the expanded state is explicit. This is a smaller risk than the nav and modal issues, but it affects the product's most important creation flow.

User impact:

- Users may not discover secondary create actions.
- Touch users may tap `+ Create` expecting a menu and get no durable state.
- Assistive tech users do not get an expanded/collapsed signal.

Recommended fix:

- Convert `CreateFab` to a true disclosure menu:
  - Click/tap toggles open state.
  - `aria-expanded` and `aria-controls`.
  - Escape closes.
  - Outside click closes.
  - Actions stay visible until dismissed.
- Add a hide/reorder option once workspace visibility preferences exist.

Do not remove:

- Keep the fast floating creation affordance.
- Make it explicit and mobile-safe.

## Recommended Roadmap

### Phase 1: Low-Risk UX Control Layer

- Persist advanced nav visibility.
- Add "Workspace visibility" settings.
- Add hide/unhide metadata to nav items and secondary cards.
- Add tests for preferences persistence and nav filtering.
- Expand command palette coverage to every route/tool that can be hidden, advanced, locked, or processing-gated.
- Add shared hidden-items metadata to the tool registry.

### Phase 2: Progressive Disclosure System

- Introduce workspace complexity modes: focused, standard, power.
- Add task presets to book workspace nav.
- Reuse nav metadata across book overview and reader toolbar.
- Add a hidden-items manager.
- Add a visible help/onboarding entry point and persist guidance dismissal in preferences.
- Add a route-level mobile primary-action contract.

### Phase 3: State and Trust Polish

- Standardize empty/loading/error states.
- Add cross-product processing taxonomy.
- Normalize focus, target size, and status message behavior.
- Move page-injected settings CSS toward reusable primitives.
- Add shared modal behavior for focus trap, Escape, scroll locking, and focus restoration.
- Replace fragile nested clickable-card patterns in core library surfaces.

### Phase 4: Enterprise Readiness

- Add settings search.
- Add account/team/admin-ready grouping.
- Add audit-friendly privacy/data controls.
- Add visible reset/export/import of workspace preferences.
- Add a project Visibility Center for private, shared, beta, and public states.
- Add route-surface inventory checks for unusually large page components.

## Proposed Product Model: Hide Without Removing

Use four layers:

1. Capability remains available.
   - Routes, APIs, permissions, and command palette entries stay intact.

2. Default visibility is persona-aware.
   - New authors see focused author flow.
   - Review-heavy users see analysis and reports.
   - Power users can keep all tools open.

3. User can hide and unhide.
   - Sidebar items.
   - Book nav sections.
   - Dashboard cards.
   - Reader toolbar actions.
   - Recommendation cards.

4. System can temporarily reveal contextually.
   - If a hidden tool has critical output, show a small "Hidden tool has new signal" notice.
   - If a user visits a hidden route directly, show it and offer "Keep visible".

## Candidate Preference Shape

This is not an implementation requirement, but it shows the product direction:

```ts
type WorkspaceComplexityMode = "focused" | "standard" | "power"

type WorkspaceVisibilityPreferences = {
  complexityMode: WorkspaceComplexityMode
  showAdvancedAuthorTools: boolean
  hiddenDashboardNavIds: string[]
  hiddenBookNavIdsByBook: Record<string, string[]>
  hiddenOverviewCardsByBook: Record<string, string[]>
  readerToolbarDensity: "minimal" | "standard" | "power"
  hiddenMobileActionIdsByRoute: Record<string, string[]>
  dismissedGuidanceIds: string[]
}
```

## Audit Evidence Index

- Dashboard shell: `frontend/src/app/(dashboard)/layout.tsx`
- Dashboard sidebar nav: `frontend/src/components/layout/DashboardSidebar.tsx`
- Book workspace nav: `frontend/src/components/layout/AuthorToolsNav.tsx`
- Preferences store: `frontend/src/lib/stores/preferencesStore.ts`
- Settings page: `frontend/src/app/(dashboard)/settings/page.tsx`
- Book overview page: `frontend/src/app/(reader)/[bookId]/page.tsx`
- Reader toolbar: `frontend/src/components/reader/ReaderToolbar.tsx`
- Upload modal: `frontend/src/components/modals/UploadModal.tsx`
- Advanced import settings: `frontend/src/components/modals/upload/AdvancedImportSettings.tsx`
- Empty-state primitives: `frontend/src/components/ui/ActionableEmptyState.tsx`, `frontend/src/components/ui/Workspace.tsx`
- Toast/status primitives: `frontend/src/components/ui/StatusToast.tsx`, `frontend/src/components/ui/ResponsivenessStatus.tsx`
- Global UX runtime: `frontend/src/components/app/UxRuntimeProvider.tsx`, `frontend/src/components/app/AppRuntime.tsx`
- Command palette and shortcuts: `frontend/src/components/ui/CommandPalette.tsx`, `frontend/src/components/ui/ShortcutHelp.tsx`, `frontend/src/lib/utils/shortcuts.ts`
- Shared dialogs: `frontend/src/components/ui/ConfirmDialog.tsx`, `frontend/src/components/ui/PromptDialog.tsx`
- Mobile actions: `frontend/src/components/ui/MobileActionBar.tsx`, `frontend/src/components/overview/CreateFab.tsx`
- First-time guidance: `frontend/src/components/tooltips/FirstTimeTooltip.tsx`
- Billing/gating surfaces: `frontend/src/components/billing/AuthorFeatureComponent.tsx`, `frontend/src/components/billing/ContextualUpgradePrompt.tsx`
- High-density surfaces requiring UX contracts: `frontend/src/app/(reader)/[bookId]/manuscript/page.tsx`, `frontend/src/app/(reader)/[bookId]/characters/page.tsx`, `frontend/src/app/(dashboard)/library/LibraryClient.tsx`, `frontend/src/components/reader/VaultNotesEditor.tsx`, `frontend/src/components/reader/WorldbuildingWorkspace.tsx`, `frontend/src/app/(reader)/[bookId]/scenes/page.tsx`, `frontend/src/components/intelligence/RelationshipGraph.tsx`

## Definition of Done for Follow-Up UX Work

- A user can hide and unhide advanced author tools permanently.
- A user can edit at least the dashboard sidebar and book workspace visibility.
- Hidden features remain reachable through command palette, direct URL, or "Hidden tools" settings.
- Empty, loading, processing, gated, and failed states use shared primitives.
- Focus visibility and status announcements are covered by component tests.
- Command palette indexes all book tools, public/private visibility states, locked states, and hidden states.
- Shared modal primitive traps focus, restores focus, handles Escape consistently, and is reused by major local modals.
- Mobile primary actions are defined for every major workspace surface.
- Public/private/collaborator/beta/public visibility states are shown consistently.
- Frontend E2E smoke tests cover at least:
  - first project upload or create flow,
  - showing/hiding advanced tools,
  - restoring a hidden nav item,
  - processing/gated/empty states.
  - opening hidden or advanced tools through command palette,
  - keyboard-safe modal close/focus behavior,
  - mobile primary action behavior on library, reader, and one dense author workspace.
