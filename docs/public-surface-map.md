# LoreVia Public Surface Map

This map keeps the word "public" tied to explicit exposure models instead of using it as a catch-all.

## Marketing-public

- Routes: `/`, `/blog`, `/answers/*`, `/demo/*`, legal/status/pricing pages.
- Data source: static or curated marketing content.
- Auth: none.
- Kill switch: not controlled by `PUBLIC_MODE_ENABLED`.

## Library-public

- Routes: `/public`, `/public/{bookId}`, `/public/{bookId}/chapter/{chapterId}`.
- API: `/api/v1/public/books`, `/api/v1/public/books/{bookId}`, `/api/v1/public/books/{bookId}/chapter/{chapterNum}`.
- Backend rule: only `books.is_public = true` with no `hidden_at` or `archived_at`.
- Product role: optional author-facing showcase surface, not the core LoreVia workflow.
- Writer bridge: responses include `author_username` when available so visitors can open `/public/writers/{username}`.
- Kill switch: controlled by `PUBLIC_MODE_ENABLED`.

## Forum-public

- Routes: `/public/forum`, `/public/forum/{postId}`, `/public/writers/{username}`.
- API: `/api/v1/public/forum/*`, `/api/v1/public/users/{username}`.
- Backend rule: forum posts and profile counts only use open posts whose manuscripts are not public, hidden, or archived.
- Product role: optional trust and discovery layer around author collaboration, not a separate reader product.
- Profile bridge: `current_project.source` is either `forum` with `forum_post_id`, or `public_book` with `public_book_id`.
- Launch gate: controlled by `PUBLIC_FORUM_STATUS`.

### Public forum status values

- `disabled`: forum reads and writes are off.
- `internal`: reserved for internal-only work; public forum reads and writes stay off.
- `beta`: public reads stay on, but public posting/commenting/reactions stay off.
- `public`: public forum reads and writes are both on.

### Current launch decision

- Public forum posting, commenting, reactions, and interest requests are enabled when the forum is intentionally launched.
- Authenticated users can participate in those write flows when `PUBLIC_FORUM_STATUS=public`.
- Current intended production status is `public`.

## Token-shared Assets

- API: `/api/v1/books/{bookId}/cover`, `/api/v1/books/{bookId}/characters/{characterId}/card`, `/api/v1/reader/media/{mediaId}`.
- Auth: signed asset token, not a session cookie.
- Backend rule: token subject and resource must match the owning user and asset.
- Kill switch: controlled by `PUBLIC_MODE_ENABLED`.

## Not Product-wired Yet

- Manual public book creation and public chapter append remain backend endpoints only.
- `PUBLIC_FORUM_STATUS` remains the explicit launch gate for forum reads/writes, but the product path is now intentionally launched in `public` mode.
