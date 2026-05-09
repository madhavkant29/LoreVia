# Frontend Feature Coverage Audit

Generated on 2026-05-03 as a follow-up check against `docs/feature-inventory.md`.

## Verdict

All non-public-mode frontend gaps from the audit have now been implemented or intentionally removed. Public mode remains intentionally excluded per the implementation request.

## Confirmed Frontend Coverage

These feature families are present as actual frontend routes/components/workflows:

- Auth login, register, OAuth callback, username completion, logout, auth bootstrap, session refresh.
- Library dashboard, upload/import modal, add-chapter flow, archive/hide actions, book stats, cover display, tier-limit display.
- Reader chapter view, reader toolbar, chapter text, smart tap context, summaries, recall, quote save, progress fetch/update, chapter list display.
- Characters page, character cards, character edit, delete, merge, share, card export.
- Relationship graph and relationship edit.
- Relationship evolution page.
- Search page using semantic search.
- Summary collection page.
- Foreshadowing page.
- Timeline page.
- Plot thread page and plot-thread note editing.
- Grounded Q&A page.
- Advisor page with advisor chat, greeting, suggestions, editorial review, prose tightening, inline continuity, voice consistency, synopsis, and continuity report export.
- Manuscript workspace with rich editor, chapter/full-book mode, snapshots, restore, scenes, corkboard, notes, readability, emotional arc, pre-writing check, workspace state, exports, and compile dialog.
- Screenplay work-type support through upload/import metadata, screenplay types, scene wording, and screenplay stats component.
- Obsidian notes editor, folder tree, graph viewer, note import/export, relations, and markdown preview.
- Character bible export, Obsidian bible preview, and save generated bible notes.
- Series manager, series bible, series advisor, series continuity check, membership/status/order controls.
- Cross-book wiki/intelligence page.
- World-building workspace with document upload/create/update/delete, gap analysis, wiki generation/listing, logic query, gap-to-note, and note status updates.
- Export studio for character bible, manuscript, notes ZIP, manuscript import, and world document import.
- Billing checkout and billing portal UI.
- Notifications bell, panel, list, mark read, and mark all read.
- Settings page for reading mode, theme/account/billing flow.
- Pricing, stats, status, landing, legal/static pages, PWA registration, analytics provider, navbar/footer.

## Implementation Checklist

| Feature area | Current frontend state | Gap |
| --- | --- | --- |
| [x] Password reset | Added `/forgot-password` and `/reset-password` pages. | Completed. |
| [x] Compliance page | Added global `/compliance` route for existing footer/register links. | Completed. |
| [ ] Public reading | Public chapter route exists, but public library/detail/create/append remain intentionally excluded. | Skipped by request. |
| [x] Character chat | Characters page now exposes in-character chat. Backend prompt feeds manuscript-derived personality, motivations, fears, relationships, growth evidence, traits, and spoiler-gated semantic context into each character. | Completed. |
| [x] Prediction endpoint | Removed backend `/intelligence/{book_id}/predict` route and README/docs references to the endpoint. | Completed by removal. |
| [x] Thematic search | Search page now supports a themes mode that calls `readerApi.thematicSearch`. | Completed. |
| [x] Book event endpoints | Timeline/event-derived views remain the frontend surface for event intelligence; no separate duplicate UI needed. | Covered by existing timeline/events UX. |
| [x] Force cover processing | Book overview now exposes `Refresh cover`, backed by `booksApi.processCover`. | Completed. |
| [x] World integration analysis | World-building workspace now exposes integration analysis. | Completed. |
| [x] World accept suggestion | World-building workspace can mark element suggestions implemented. | Completed. |
| [x] Canon overrides | World-building workspace now lists and saves canon overrides. | Completed. |
| [x] Series world analysis | Series page now exposes series world analysis. | Completed. |
| [x] World note delete | World notes can now be deleted from open and addressed lists. | Completed. |
| [x] Read state toggles | Chapter list now has mark chapter read/unread and mark book read controls. | Completed. |
| [x] Chapter version detail | Manuscript version history can now preview snapshot text. | Completed. |
| [x] Server scene insertion | Manuscript scene insertion now calls the server insertion endpoint before inserting into the draft. | Completed. |
| [x] Character bible note listing | Export studio now loads and displays saved character-bible Obsidian note overrides. | Completed. |

## Backend-Only Or Ops-Only Features

These are documented features but are not expected to have normal user-facing frontend screens:

- Webhooks.
- Celery worker internals.
- Parser internals.
- Embedding internals.
- Storage abstraction.
- Redis cache key/session internals.
- Migration safety utilities.
- Sentry/logging/error sanitization internals.
- Email delivery internals, except where user flows trigger email.
- Admin metrics, queue depth, and rate-limit override APIs, unless an admin console is desired.

## Practical Priority

Remaining intentional exclusion:

1. Public mode routes beyond the existing public chapter page were not implemented.
