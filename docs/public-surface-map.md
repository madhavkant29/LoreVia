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
- Writer bridge: responses include `author_username` when available so readers can open `/public/writers/{username}`.
- Kill switch: controlled by `PUBLIC_MODE_ENABLED`.

## Forum-public

- Routes: `/public/forum`, `/public/forum/{postId}`, `/public/writers/{username}`.
- API: `/api/v1/public/forum/*`, `/api/v1/public/users/{username}`.
- Backend rule: forum posts and profile counts only use open posts whose manuscripts are not public, hidden, or archived.
- Profile bridge: `current_project.source` is either `forum` with `forum_post_id`, or `public_book` with `public_book_id`.
- Kill switch: controlled by `PUBLIC_MODE_ENABLED`.

## Token-shared Assets

- API: `/api/v1/books/{bookId}/cover`, `/api/v1/books/{bookId}/characters/{characterId}/card`, `/api/v1/reader/media/{mediaId}`.
- Auth: signed asset token, not a session cookie.
- Backend rule: token subject and resource must match the owning user and asset.
- Kill switch: controlled by `PUBLIC_MODE_ENABLED`.

## Not Product-wired Yet

- Manual public book creation and public chapter append remain backend endpoints only.
- Forum creation/editing, reader-interest creation, and author-side interest listing also remain backend-only product surfaces for now.
- Do not add frontend client methods or UI for these write flows until the product path is ready.
