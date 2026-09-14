# Public chapter asset delivery

LoreVia can serve published chapter text from a CDN or public object-storage origin without exposing private manuscript objects. The feature is opt-in and remains disabled until the origin contract below is configured.

## Origin contract

- Only objects below the `public-assets/` prefix may be publicly readable. The `books/`, `chapters/`, `exports/`, `manuscript-imports/`, and all other prefixes must remain private.
- `PUBLIC_ASSET_BASE_URL` must point to the public origin path that maps to the bucket root. Production startup rejects an enabled feature without an absolute HTTPS URL.
- Published chapter assets use immutable, versioned keys: `public-assets/{book_id}/{chapter_id}/v{content_version}.txt`.
- Asset responses are written with a short, revalidating cache lifetime controlled by `PUBLIC_ASSET_CACHE_MAX_AGE_SECONDS` (60 seconds by default). A CDN must honor origin deletion and revalidation; do not configure a longer edge override.
- Restricted shared works never receive a direct public URL. Existing authorization checks issue short-lived private URLs instead.

## Publication and revocation

Publishing or approving a book materializes its chapter assets. Chapter saves publish the new content version. Each chapter persists `public_asset_version`; the API issues a direct URL only when it matches `content_version`. A failed or not-yet-backfilled upload therefore falls back to backend content delivery instead of returning a broken direct URL. A bounded maintenance backfill covers books that were already public when the feature was enabled.

Unpublish, moderation hide/remove, public-share rejection, and account/book deletion enumerate and delete every object below the book's public prefix. These privacy transitions use strict revocation before committing the database change: if listing or deleting any public object fails, the transition fails and can be retried instead of reporting a private state while an origin object remains readable. The public chapter API checks current database visibility before returning an asset URL, so it stops issuing URLs immediately after a successful transition; an already cached edge response can live only until the configured revalidation interval.

## Rollout

1. Configure a dedicated CDN/origin rule that exposes only `public-assets/`.
2. Set `PUBLIC_ASSET_BASE_URL` and keep `DIRECT_PUBLIC_ASSETS_ENABLED=false` while validating origin isolation.
3. Confirm private-prefix requests return 403/404 and public-prefix test objects are readable. Use the read-only preflight with a known public object and a known-existing private object (an arbitrary missing private key is not sufficient evidence):

   ```powershell
   python .\backend\scripts\verify_public_asset_origin.py --base-url https://assets.example.com --public-key public-assets/<book-id>/<chapter-id>/v1.txt --private-key chapters/<known-existing-private-key>
   ```

   The preflight also rejects public prefix listing, redirects, non-text assets, and cache lifetimes above the revocation window.
4. Enable `DIRECT_PUBLIC_ASSETS_ENABLED`, then monitor the hourly `maintenance_tasks.backfill_public_assets` task until its cursor wraps.
5. Verify a publish creates a versioned text asset and an unpublish removes it at the origin and after the configured edge revalidation interval.
