# Security Review: LoreVia2

## Scope

- Target: `C:\Users\madha\.vscode\prod\LoreVia2`
- Commit inspected: `561cb09edf775a9616ab628eb89296cd1bf93680`
- Mode: repository-wide Codex Security scan, plus the requested UI/UX source audit.
- In scope: backend, frontend, public sharing, billing/webhooks/internal jobs, uploads/parsers, collaborator manuscript access, deployment/edge files, static assets, and page inventory.
- Runtime status: Docker was not running. Local frontend launch and external report writes were blocked by the desktop approval/usage system. Browser automation failed before navigation.
- Validation mode: static source-to-sink tracing, existing test references, subagent local probes, and deployment configuration evidence.

### Scan Summary

| Field | Value |
|---|---|
| Reportable findings | 18 |
| Severity mix | high: 10, medium: 8 |
| Confidence mix | high: 14, medium: 4 |
| Raw candidate IDs retained | 57 in `audits/security-ledger-2026-06-01.md` |
| Rendered UI QA | Blocked; source/static audit completed in `audits/uiux-audit-2026-06-01.md` |

## Threat Model

The repository-provided `AGENTS.md` was used as scan guidance and project threat model.

- Backend is FastAPI plus SQLAlchemy; routes are endpoint handlers and security-relevant logic should live in utilities/services.
- Frontend is React/Next.js.
- Treat Render as the default deployment target, but repository Nginx, Docker Compose, systemd, and deploy scripts are also real deployment surfaces.
- Do not edit secrets or `.env` files; this audit did not read secret values.
- Public surfaces include auth/session, public sharing/moderation, billing/webhooks/internal jobs, public analytics/forum, uploads/parsers, collaborator-scoped manuscript access, frontend token storage, and edge proxy handling.
- Supabase Data API exposure is opt-in; database and migration operations are security-sensitive.

## Findings

| Finding | Severity | Confidence | Category | Candidate |
|---|---|---|---|---|
| [Owner publish route bypasses manual public-share moderation](#1-owner-publish-route-bypasses-manual-public-share-moderation) | high | high | Workflow authorization bypass | `PUBLIC-001` |
| [Anonymous copyright report can hide any book by UUID](#2-anonymous-copyright-report-can-hide-any-book-by-uuid) | high | high | Authorization bypass / cross-tenant availability | `PUBLIC-002` |
| [Hidden or removed books remain eligible in the public forum](#3-hidden-or-removed-books-remain-eligible-in-the-public-forum) | high | high | Moderation bypass / data exposure | `PUBLIC-003` |
| [Restricted collaborators can search out-of-scope manuscript chapters](#4-restricted-collaborators-can-search-out-of-scope-manuscript-chapters) | high | high | Authorization bypass / IDOR | `FILE-001` |
| [Restricted collaborators can search out-of-scope scenes](#5-restricted-collaborators-can-search-out-of-scope-scenes) | high | high | Authorization bypass / IDOR | `FILE-002` |
| [Restricted collaborators can move and rewrite out-of-scope scenes](#6-restricted-collaborators-can-move-and-rewrite-out-of-scope-scenes) | high | high | Authorization bypass / object-level write | `FILE-003` |
| [Restricted collaborators can preview out-of-scope scene content](#7-restricted-collaborators-can-preview-out-of-scope-scene-content) | high | high | Authorization bypass / data exposure | `FILE-004` |
| [Supabase OAuth email fallback ignores existing subject mismatch](#8-supabase-oauth-email-fallback-ignores-existing-subject-mismatch) | high | medium | Authentication binding flaw | `AUTH-001` |
| [Backend Docker images can bake local env secret files into layers](#9-backend-docker-images-can-bake-local-env-secret-files-into-layers) | high | high | Secret exposure in build artifacts | `DEPLOY-001` |
| [Docker build context includes TLS private keys and unrelated secrets](#10-docker-build-context-includes-tls-private-keys-and-unrelated-secrets) | high | high | Secret exposure in build context | `DEPLOY-002` |
| [Supabase OAuth refresh token remains in localStorage after LoreVia logout](#11-supabase-oauth-refresh-token-remains-in-localstorage-after-lorevia-logout) | medium | high | Client credential lifetime / logout failure | `FRONTSEC-001` |
| [Cloudflare tunnel enforcement accepts forged direct-origin headers](#12-cloudflare-tunnel-enforcement-accepts-forged-direct-origin-headers) | medium | high | Trusted header bypass | `DEPLOY-004` |
| [Application rate limits trust forged CF-Connecting-IP from Nginx](#13-application-rate-limits-trust-forged-cf-connecting-ip-from-nginx) | medium | high | Rate-limit bypass via trusted header | `DEPLOY-005` |
| [Bearer-looking Authorization header suppresses cookie CSRF checks](#14-bearer-looking-authorization-header-suppresses-cookie-csrf-checks) | medium | medium | CSRF control confusion | `AUTH-002` |
| [DOCX and EPUB uploads do not use existing ZIP bomb safety checks](#15-docx-and-epub-uploads-do-not-use-existing-zip-bomb-safety-checks) | medium | high | Archive bomb / resource exhaustion | `FILE-007` |
| [Manuscript batch import tracks aggregate file size but never enforces it](#16-manuscript-batch-import-tracks-aggregate-file-size-but-never-enforces-it) | medium | high | Resource exhaustion | `FILE-013` |
| [World-building upload parses files before entitlement checks](#17-world-building-upload-parses-files-before-entitlement-checks) | medium | high | Resource exhaustion / entitlement-order flaw | `FILE-014` |
| [Internal-job rate limit is keyed by each attacker-supplied secret guess](#18-internal-job-rate-limit-is-keyed-by-each-attacker-supplied-secret-guess) | medium | high | Rate-limit bypass / resource abuse | `BILL-003` |

### Confidence Scale

| Label | Meaning |
|---|---|
| high | Direct source, configuration, or runtime-probe evidence supports the finding, with no material unresolved reachability blocker. |
| medium | Source evidence supports a plausible issue, but runtime behavior, deployment configuration, provider configuration, or exploit reliability still needs proof. |
| low | Weak or incomplete evidence; low-confidence rows were retained in the ledger instead of final findings. |

### [1] Owner publish route bypasses manual public-share moderation

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Static route trace shows the owner publish endpoint sets public, clean, and approved state directly. |
| Category | Workflow authorization bypass |
| CWE | CWE-841 Improper Enforcement of Behavioral Workflow |
| Affected lines | `backend/app/api/v1/routes/books/publish.py:96-106`; `backend/app/api/v1/routes/public.py:655-663` |

#### Summary
The deployed owner publish endpoint directly marks a book public, clean, and approved. That bypasses the separate manual approval flow used by the public-share request path.

#### Validation
Static source-to-sink trace. The route checks ownership and email verification, but then sets `public_status`, `moderation_status`, `is_public`, and `public_share_status` to approved in one request.

#### Dataflow
`POST /books/{book_id}/publish` -> ownership check -> rights flag and slug -> `Book.public_status=published`, `moderation_status=clean`, `is_public=True`, `public_share_status=approved` -> commit.

#### Reachability
Any verified owner of a book that is not already under review/hidden/removed can publish without admin review. This is reachable from authenticated product APIs and the library client.

#### Severity
High because it breaks the product moderation boundary and can expose user-submitted manuscripts publicly without the intended review gate. Severity would drop if this endpoint is intentionally restricted behind a feature flag not visible in this repository.

#### Remediation
Route all creator public sharing through the pending-share path, require admin approval before `is_public=True`, and add integration tests proving owner publish cannot set approved status.

### [2] Anonymous copyright report can hide any book by UUID

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Static route trace shows optional auth, arbitrary book UUID load, and immediate hide state for copyright reports. |
| Category | Authorization bypass / cross-tenant availability |
| CWE | CWE-862 Missing Authorization; CWE-639 Authorization Bypass Through User-Controlled Key |
| Affected lines | `backend/app/api/v1/routes/reports.py:30-47`; `backend/app/api/v1/routes/reports.py:80-84`; `backend/app/api/v1/routes/reports.py:120` |

#### Summary
The reports endpoint is anonymous, loads any supplied book UUID, and hides the book immediately for copyright reports if a non-empty reporter email is supplied.

#### Validation
Static route trace. Optional authentication is used, no public visibility or owner relationship is required, and the hide state is committed in the same request.

#### Dataflow
`POST /reports/content` -> `body.book_id` -> `db.get(Book, book_id)` -> report type `copyright` -> `Book.moderation_status=hidden`, `public_status=hidden`, `is_public=False` -> commit.

#### Reachability
An unauthenticated caller who knows or guesses a book UUID can hide another user book. Public book UUIDs are exposed in multiple public payloads, so the precondition is realistic for public samples.

#### Severity
High because it is anonymous cross-tenant state change with direct public availability impact. Severity would drop if product policy intentionally treats every copyright report as an immediate takedown regardless of authentication and visibility.

#### Remediation
Only allow reports against publicly visible books, validate reported URL/book relationship, require stronger reporter verification or admin review before hiding, and add abuse tests for arbitrary private and public UUIDs.

### [3] Hidden or removed books remain eligible in the public forum

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Predicate and route trace show non-public books are considered forum eligible. |
| Category | Moderation bypass / data exposure |
| CWE | CWE-284 Improper Access Control; CWE-200 Exposure of Sensitive Information |
| Affected lines | `backend/app/utils/public_utils.py:1644-1652`; `backend/app/utils/public_utils.py:1717-1719`; `backend/app/api/v1/routes/public.py:127-152`; `backend/app/api/v1/routes/public.py:165-180` |

#### Summary
The forum eligibility predicate returns true for every non-public book. When moderation or reports set `is_public=false`, forum posts for that book can remain visible and interactive.

#### Validation
Static predicate and route trace. Moderation hides books by setting `is_public=false`; the forum predicate treats that value as eligible instead of checking approved public-share or demo status.

#### Dataflow
Admin/report hide -> `Book.is_public=False` -> `_book_is_forum_eligible` returns true -> anonymous forum list/detail/comments return post payloads from cache or DB.

#### Reachability
Anonymous readers can list or open forum posts; authenticated users can continue comments/reactions through the same predicate. This undermines takedown and public moderation decisions.

#### Severity
High because it preserves public exposure after a takedown decision. Severity would drop if forum records are guaranteed deleted before hide, but no such invariant appears in the inspected routes.

#### Remediation
Make forum eligibility require `can_view_public_book` and an approved share/demo state, invalidate forum caches on takedown/unpublish, and test hidden/removed books across list, detail, comments, comments create, and reactions.

### [4] Restricted collaborators can search out-of-scope manuscript chapters

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Static trace shows the route authorizes an edit collaborator and the helper selects all chapters without collaborator filtering. |
| Category | Authorization bypass / IDOR |
| CWE | CWE-639 Authorization Bypass Through User-Controlled Key; CWE-200 Exposure of Sensitive Information |
| Affected lines | `backend/app/api/v1/routes/manuscript.py:80-102`; `backend/app/utils/book_utils.py:5339-5350`; `backend/app/utils/book_utils.py:5445-5470` |

#### Summary
Workspace search accepts a collaborator but does not pass collaborator context into the search helper, so manuscript search reads every chapter for the book.

#### Validation
Static source-to-sink trace. The route only checks that the collaborator can edit somewhere; the helper selects chapter rows by `book_id` and optional chapter filter, with no `collaboration_allows_chapter` filter.

#### Dataflow
`POST /{book_id}/workspace/search` -> collaboration access -> `search_author_workspace` without collaborator -> select all `Chapter` rows -> download and deserialize text -> return excerpts.

#### Reachability
A restricted collaborator with edit access to selected chapters can submit an empty or broad search and receive excerpts from chapters outside their permitted range.

#### Severity
High because it crosses the collaborator access boundary and exposes manuscript text. Severity would drop only if restricted chapter collaborations are not used in production.

#### Remediation
Add collaborator to `search_author_workspace`, filter chapters and chapter filters through `collaboration_allows_chapter`, and add integration tests with allowed and denied chapter ranges.

### [5] Restricted collaborators can search out-of-scope scenes

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | The scene search branch omits the collaborator-aware filter that exists elsewhere in the utility layer. |
| Category | Authorization bypass / IDOR |
| CWE | CWE-639 Authorization Bypass Through User-Controlled Key; CWE-200 Exposure of Sensitive Information |
| Affected lines | `backend/app/api/v1/routes/manuscript.py:80-102`; `backend/app/utils/book_utils.py:5386-5420`; `backend/app/utils/book_utils.py:4788-4794` |

#### Summary
Scene search calls `list_novel_scenes` without collaborator context even though that helper family has a collaborator-aware filter.

#### Validation
Static trace. The route permits edit-capable collaborators and the search helper returns scene IDs, chapter numbers, titles, and excerpts for all matching scenes in the book.

#### Dataflow
`POST workspace/search` with scope `scenes` -> `list_novel_scenes(book, chapter_number, query=None)` -> no collaborator filter -> return scene id and excerpt.

#### Reachability
A restricted collaborator can harvest out-of-scope scene UUIDs and excerpts. Those UUIDs also enable other scene endpoints affected by this boundary error.

#### Severity
High because it exposes private scene content and identifiers across a restricted collaboration boundary.

#### Remediation
Pass collaborator to scene search, apply the existing `collaboration_allows_chapter` filtering, and add tests that search does not leak scene IDs outside assigned chapters.

### [6] Restricted collaborators can move and rewrite out-of-scope scenes

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Static route/service trace shows only the requested destination chapter is checked before mutation. |
| Category | Authorization bypass / object-level write |
| CWE | CWE-639 Authorization Bypass Through User-Controlled Key; CWE-862 Missing Authorization |
| Affected lines | `backend/app/api/v1/routes/manuscript.py:271-281`; `backend/app/utils/book_utils.py:4927-4937`; `backend/app/utils/book_utils.py:4967-5015` |

#### Summary
Scene update validates only the destination chapter for collaborators. It does not check that the scene currently belongs to an allowed chapter before mutating it.

#### Validation
Static route and service trace. A collaborator can provide an out-of-scope scene UUID and an allowed destination chapter; the service then updates body, metadata, chapter, and structure order.

#### Dataflow
Patch scene -> fetch `NovelScene` by `book_id` and `scene_id` -> check requested destination chapter only -> save scene -> rewrite scene content and synchronize old/new chapter order.

#### Reachability
A restricted collaborator who obtains an out-of-scope scene UUID through search/tree leakage or prior access can alter another chapter by moving the scene into an allowed chapter.

#### Severity
High because it is a cross-scope integrity break against manuscript content, not just metadata exposure.

#### Remediation
For collaborators, require both current scene chapter and destination chapter to be allowed. Add tests for updating, moving, and editing scenes outside allowed chapters.

### [7] Restricted collaborators can preview out-of-scope scene content

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Static route trace shows the endpoint checks target chapter but not source scene chapter. |
| Category | Authorization bypass / data exposure |
| CWE | CWE-639 Authorization Bypass Through User-Controlled Key; CWE-200 Exposure of Sensitive Information |
| Affected lines | `backend/app/api/v1/routes/manuscript.py:625-667` |

#### Summary
The insert preview endpoint checks the target chapter but reads the source scene by book and UUID without checking the source scene chapter.

#### Validation
Static route trace. The response includes formatted body and `html_body` derived from the fetched scene.

#### Dataflow
`POST /scenes/{scene_id}/insert` -> validate target chapter allowed -> select scene by `book_id/id` -> build import text from scene body -> return body/html.

#### Reachability
A restricted collaborator can use a leaked scene UUID and an allowed target chapter to read full out-of-scope scene content.

#### Severity
High because it reveals full manuscript scene content across a collaboration boundary.

#### Remediation
Validate the source scene chapter for collaborators before building the preview, and test denied preview for out-of-scope source scenes even when the destination is allowed.

### [8] Supabase OAuth email fallback ignores existing subject mismatch

| Field | Value |
|---|---|
| Severity | high |
| Confidence | medium |
| Confidence rationale | Code supports the account-binding flaw, but provider-side email assurance and production Supabase settings still need confirmation. |
| Category | Authentication binding flaw |
| CWE | CWE-287 Improper Authentication |
| Affected lines | `backend/app/api/v1/routes/auth.py:320-333`; `backend/app/api/v1/routes/auth.py:369-388` |

#### Summary
The Supabase OAuth bridge first looks up by `supabase_auth_id`, then falls back to email. If it finds an account already bound to a different Supabase subject, it does not reject the mismatch before minting LoreVia cookies.

#### Validation
Static source trace. Runtime proof was blocked by missing services, so confidence is medium. The vulnerable branch is explicit: mismatch is not rejected unless `supabase_auth_id is None`, and token minting follows.

#### Dataflow
Supabase verified token -> `sb_user.id` and email -> no row for id -> row by lower(email) -> existing `supabase_auth_id` not null and different -> no reject -> `_mint_token_pair(existing)`.

#### Reachability
An attacker needs a Supabase token whose email matches a target LoreVia account while the Supabase subject differs. The issue is severe if provider configuration allows unverified or rebinding-prone email assertions.

#### Severity
High with medium confidence because successful exploitation is account takeover, but provider-side email assurance and uniqueness need production confirmation.

#### Remediation
Reject email fallback when existing `supabase_auth_id` is set to a different value, require verified email metadata from Supabase before linking, and add tests for subject mismatch and unverified provider email.

### [9] Backend Docker images can bake local env secret files into layers

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Build context and Dockerfile copy rules directly support image-layer exposure. Secret values were not read. |
| Category | Secret exposure in build artifacts |
| CWE | CWE-200 Exposure of Sensitive Information; CWE-312 Cleartext Storage of Sensitive Information |
| Affected lines | `backend/Dockerfile.api:28`; `backend/Dockerfile.worker:20`; `docker-compose.yml:27-32` |

#### Summary
The Docker build context is the repository root and the API image copies `backend/` wholesale. With no root `.dockerignore` excluding `backend/.env*`, local secret files can be copied into the image filesystem.

#### Validation
Static deployment trace. The audit did not read secret values, but file presence and copy rules are enough to establish image-layer exposure risk.

#### Dataflow
`docker compose build` context `.` -> Dockerfile `COPY backend/ .` -> `backend/.env` and `.env.local` copied into `/app` -> app config also loads `.env` files from that location.

#### Reachability
Anyone with access to the built image, image cache, registry, or a compromised container can read baked env files. This can expose database, JWT, storage, AI, email, and payment secrets.

#### Severity
High because container image access becomes credential disclosure. Severity would drop if production builds are guaranteed from a clean context without secret files, but the repo lacks an enforcing `.dockerignore`.

#### Remediation
Add root `.dockerignore` excluding all `.env*` and cert/private-key material, copy only required backend files, use runtime env injection, and add a build audit test that fails if secret-named files exist in image layers.

### [10] Docker build context includes TLS private keys and unrelated secrets

| Field | Value |
|---|---|
| Severity | high |
| Confidence | high |
| Confidence rationale | Compose sets root context for multiple images and the cert directory is inside that context. |
| Category | Secret exposure in build context |
| CWE | CWE-200 Exposure of Sensitive Information; CWE-312 Cleartext Storage of Sensitive Information |
| Affected lines | `docker-compose.yml:27-30`; `docker-compose.yml:195-201` |

#### Summary
Both API and ops images build with context set to the repository root. The Nginx certificate directory is present under `ops/nginx/certs` and is context-visible to all builders.

#### Validation
Static deployment trace. Build context exposure exists even if the Dockerfile does not copy the file; remote builders and layer cache tooling can receive the context.

#### Dataflow
`docker compose build` -> context `.` -> builder receives `ops/nginx/certs` and any unignored local files -> unrelated images are built from the same context.

#### Reachability
A remote or compromised builder, CI worker, or build cache can receive private keys and local secrets that are not needed for the image.

#### Severity
High because TLS private keys and secrets should never enter broad build contexts. Severity depends on whether builds ever run on remote infrastructure.

#### Remediation
Add `.dockerignore` for `ops/nginx/certs`, `.env*`, local storage, dumps, and keys; move secrets outside the repo; narrow image contexts where practical.

### [11] Supabase OAuth refresh token remains in localStorage after LoreVia logout

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Static trace and SDK default behavior show session persistence; logout does not call Supabase sign-out. |
| Category | Client credential lifetime / logout failure |
| CWE | CWE-922 Insecure Storage of Sensitive Information; CWE-613 Insufficient Session Expiration |
| Affected lines | `frontend/src/lib/supabase.ts:7-12`; `frontend/src/app/auth/callback/page.tsx:59-87`; `frontend/src/lib/api/auth.ts:60` |

#### Summary
The Supabase client uses browser persistence defaults. OAuth callback exchanges a code for a Supabase session and then bridges the access token into LoreVia cookies, but LoreVia logout only posts to the backend and does not sign out Supabase.

#### Validation
Static trace plus SDK behavior cited by the sidecar. The token persists after LoreVia cookies are cleared unless `supabase.auth.signOut` or `persistSession: false` is used.

#### Dataflow
OAuth callback -> `supabase.auth.exchangeCodeForSession` -> SDK persists session in localStorage -> `authApi.loginWithSupabaseToken` -> LoreVia cookies -> `authApi.logout` clears LoreVia cookies only -> Supabase refresh token remains.

#### Reachability
Same-origin JavaScript after logout can read the lingering Supabase refresh token, obtain a new Supabase access token, and call `/auth/oauth/supabase` to mint new LoreVia cookies.

#### Severity
Medium because it needs same-origin script execution or local browser compromise, but it defeats logout and extends credential theft impact.

#### Remediation
Create the Supabase client with `persistSession: false` for bridge-only OAuth, or call `supabase.auth.signOut` and remove Supabase storage keys during logout. Add a frontend test for OAuth login then logout storage cleanup.

### [12] Cloudflare tunnel enforcement accepts forged direct-origin headers

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Deployment trace shows public Nginx forwards attacker-supplied `CF-Connecting-IP`, while middleware checks only presence. |
| Category | Trusted header bypass |
| CWE | CWE-346 Origin Validation Error; CWE-284 Improper Access Control |
| Affected lines | `docker-compose.yml:8-10`; `ops/nginx/nginx.conf:119-124`; `backend/app/utils/tunnel/cloudflare.py:35-44`; `backend/start.sh:8-12` |

#### Summary
The middleware rejects requests only when `CF-Connecting-IP` is absent. Public Nginx forwards the client-supplied `CF-Connecting-IP` header, and the `cloudflared` startup block is disabled.

#### Validation
Static deployment trace. The public compose path exposes Nginx on 80/443 and forwards the header without proving the peer is Cloudflare.

#### Dataflow
Direct client -> public Nginx -> `proxy_set_header CF-Connecting-IP $http_cf_connecting_ip` -> backend middleware sees header present -> request allowed.

#### Reachability
If this compose/Nginx deployment is reachable directly, any internet client can add `CF-Connecting-IP` and bypass the intended tunnel-origin gate. The repo note still says Render, so exact production ingress should be confirmed.

#### Severity
Medium because it weakens origin perimeter controls and supports abuse chains, but the final impact depends on actual ingress/firewall deployment.

#### Remediation
Do not trust `CF-Connecting-IP` for direct-origin enforcement. Restrict origin ingress to Cloudflare ranges at the firewall/Nginx layer, strip inbound CF headers from non-Cloudflare peers, or require a signed tunnel/origin secret.

### [13] Application rate limits trust forged CF-Connecting-IP from Nginx

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Static trace shows Nginx forwards the header and the backend prioritizes it for trusted private peers. |
| Category | Rate-limit bypass via trusted header |
| CWE | CWE-346 Origin Validation Error; CWE-307 Improper Restriction of Excessive Authentication Attempts |
| Affected lines | `ops/nginx/nginx.conf:119-124`; `backend/app/api/deps/rate_limit.py:171-201`; `backend/app/api/deps/rate_limit.py:204-229` |

#### Summary
The API trusts `CF-Connecting-IP` whenever the direct peer is a private proxy. Public Nginx forwards the client-supplied header, so attackers can rotate identities for auth and public buckets.

#### Validation
Static trace. Nginx edge rate limits still cap raw request rate, so this is an application identity throttling bypass rather than unlimited throughput.

#### Dataflow
Client supplies `CF-Connecting-IP` -> Nginx forwards it -> backend direct IP is trusted private Nginx -> `_client_identifier` returns forged header -> rate-limit keys use attacker-chosen IP.

#### Reachability
Direct-origin clients can evade per-IP auth and public route windows by changing a header. This affects login/register/password/public API and asset buckets.

#### Severity
Medium because it assists brute force and public abuse while Nginx still imposes a coarse per-real-IP cap.

#### Remediation
Only trust `CF-Connecting-IP` if the upstream peer is Cloudflare or Nginx has overwritten it from verified `real_ip` state. Otherwise use `X-Real-IP` set from `$remote_addr` and strip inbound forwarding headers.

### [14] Bearer-looking Authorization header suppresses cookie CSRF checks

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | medium |
| Confidence rationale | Static source trace shows the control mismatch; ordinary hostile origins are constrained by CORS/preflight and SameSite. |
| Category | CSRF control confusion |
| CWE | CWE-352 Cross-Site Request Forgery; CWE-441 Unintended Proxy or Intermediary |
| Affected lines | `backend/app/utils/auth_csrf.py:66-75`; `backend/app/utils/auth_cookies.py:70-84`; `backend/app/api/deps/auth.py:272-276` |

#### Summary
Unsafe requests skip CSRF when an `Authorization` header starts with `Bearer`, but cookie token extraction still prefers cookies when bearer token validation fails or is absent in the actual auth dependency.

#### Validation
Static source trace. Exploitation from arbitrary origins is limited by browser CORS/preflight and `SameSite=Lax`, so confidence is medium for a standalone web attack.

#### Dataflow
Unsafe request with cookies and `Authorization: Bearer junk` -> `cookie_authenticated_request_requires_csrf` returns false -> cookie credentials can still be consumed -> state-changing route executes.

#### Reachability
A same-origin script primitive, overly trusted origin, browser extension, or subdomain situation can use the header to bypass CSRF token/origin checks for cookie-authenticated mutations.

#### Severity
Medium because it is a real control mismatch, but ordinary hostile websites cannot send the custom header through simple forms.

#### Remediation
Make auth mode explicit. If bearer verification fails, do not fall back to cookies for that request; or require CSRF whenever auth cookies are present regardless of `Authorization`. Add a composed regression test.

### [15] DOCX and EPUB uploads do not use existing ZIP bomb safety checks

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Static trace and bounded ZIP probe show shallow DOCX/EPUB validation despite an existing archive safety helper. |
| Category | Archive bomb / resource exhaustion |
| CWE | CWE-409 Improper Handling of Highly Compressed Data |
| Affected lines | `backend/app/api/v1/routes/books/imports.py:111-115`; `backend/app/api/v1/routes/books/imports.py:246-267`; `backend/app/utils/upload_security_utils.py:80-137`; `backend/app/parsers/epub_parser.py:14-24` |

#### Summary
The code has a ZIP safety helper for archives, but DOCX/EPUB validation checks only required members or mimetype before parser libraries decompress archive contents.

#### Validation
Static trace plus bounded local ZIP probe from the sidecar. A tiny highly compressed archive with required members passed structural checks while exceeding safe expansion ratios.

#### Dataflow
Upload DOCX/EPUB -> read bounded compressed bytes -> `validate_document_upload_bytes` structural check -> parser library opens members and decompresses expanded content.

#### Reachability
Authenticated authors can upload book files and manuscript import files. Worker or API-parser resources can be consumed disproportionally by compressed input.

#### Severity
Medium because it is authenticated denial of service against parsing workers/API paths, with no code execution or data exposure shown.

#### Remediation
Call `validate_zip_archive_safety` for DOCX and EPUB before parsing, enforce expanded-byte/member/ratio limits, and add regression fixtures for book upload and manuscript import paths.

### [16] Manuscript batch import tracks aggregate file size but never enforces it

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Route trace shows aggregate size is incremented but not checked before parsing. |
| Category | Resource exhaustion |
| CWE | CWE-770 Allocation of Resources Without Limits or Throttling |
| Affected lines | `backend/app/api/v1/routes/books/imports.py:173-190`; `backend/app/api/v1/routes/books/imports.py:208-267` |

#### Summary
The batch import route accepts a list of files, caps each file individually, increments `total_file_size`, but never rejects excessive total size or file count.

#### Validation
Static route trace. Reverse proxies may cap a single HTTP body, but the application does not enforce product-level aggregate limits before parsing every file.

#### Dataflow
`POST manuscript import files[]` -> for each upload read per-file max bytes -> `total_file_size += len(raw)` -> validate/parse each file -> no aggregate or count guard.

#### Reachability
Authenticated authors can submit many individually valid files in one request and consume memory/CPU before normal import limits are considered.

#### Severity
Medium because it can create avoidable authenticated resource exhaustion and cost pressure.

#### Remediation
Enforce max file count and total compressed/uncompressed bytes before parsing, fail early, and add tests for too many files and excessive aggregate size.

### [17] World-building upload parses files before entitlement checks

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Route trace shows file preparation/parsing happens before upload entitlement checks. |
| Category | Resource exhaustion / entitlement-order flaw |
| CWE | CWE-770 Allocation of Resources Without Limits or Throttling |
| Affected lines | `backend/app/api/v1/routes/world_building.py:141-175`; `backend/app/utils/world_building_utils.py:464-479` |

#### Summary
World-building documents are read and prepared before subscription upload limits are checked, so an authenticated user can force parsing work even when the upload should later be rejected.

#### Validation
Static route trace. The route accumulates raw files, calls `prepare_world_building_uploads`, and only then calculates and checks upload cost.

#### Dataflow
`POST world-building documents` -> read files -> `prepare_world_building_uploads` parses documents -> compute upload cost -> `check_upload_limit`.

#### Reachability
Authenticated users below entitlement limits, or intentionally over limit, can still trigger parsing and decompression work before rejection.

#### Severity
Medium because it is authenticated resource exhaustion and cost abuse, not direct data compromise.

#### Remediation
Calculate requested count/cost and enforce upload limits before parsing, add aggregate/file-count caps, and reuse DOCX/EPUB ZIP safety checks.

### [18] Internal-job rate limit is keyed by each attacker-supplied secret guess

| Field | Value |
|---|---|
| Severity | medium |
| Confidence | high |
| Confidence rationale | Static trace shows the supplied guess is hashed into the limiter key before authorization. |
| Category | Rate-limit bypass / resource abuse |
| CWE | CWE-307 Improper Restriction of Excessive Authentication Attempts; CWE-400 Uncontrolled Resource Consumption |
| Affected lines | `backend/app/api/deps/rate_limit.py:352-365` |

#### Summary
The internal job limiter hashes the supplied `X-Internal-Job-Secret` and uses it as the rate-limit identity before authorization, giving each wrong guess a fresh bucket.

#### Validation
Static trace and deterministic hash-bucket check from the sidecar.

#### Dataflow
POST internal job with guessed header -> `rate_limit_internal_job` hashes guess -> Redis key `internal_job:{hash}:job` -> authorization then rejects or accepts later.

#### Reachability
An unauthenticated caller can rotate guessed header values to bypass the 10/minute limit and create Redis key churn. The secret still protects successful job execution unless it is weak/default.

#### Severity
Medium because it weakens brute-force and availability controls for privileged internal endpoints, but does not bypass the secret by itself.

#### Remediation
Key failed internal attempts by trusted client IP, not by the guess. Apply the secret check before any guess-dependent bucket and add Redis key churn tests.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
|---|---|---|---|
| Auth/session | OAuth bridge, CSRF, refresh, reset, verification, admin step-up | Reported and needs follow-up | Reported Supabase subject mismatch and CSRF mode confusion. Reset/verification races and timing oracles remain lower-priority hardening rows. |
| Upload/parser | DOCX, EPUB, PDF, manuscript import, world-building import | Reported and needs follow-up | Reported ZIP safety, aggregate import, and world-building entitlement-order issues. PDF parser runtime stress tests are deferred. |
| Collaborator manuscript workspace | Search, scene preview, scene update, tree, restore | Reported | Multiple restricted-collaborator boundary breaks survived static validation. |
| Public sharing/moderation | Publish, reports, forum, caches, analytics | Reported | Manual moderation bypass, anonymous hide, and hidden forum exposure are final findings. Cache and analytics spoofing are secondary hardening rows. |
| Billing/webhooks/internal jobs | Paddle HMAC, webhook tiering, confirmation, internal secret jobs | Reported and needs follow-up | Placeholder secret and billing URL-token rows remain in the ledger; the final detailed report includes the internal-job rate-limit issue. |
| Deployment/edge | Docker context, Nginx, Cloudflare headers, Redis env, deploy scripts | Reported and needs follow-up | Secret build-context and forged Cloudflare header paths reported. Shell/env deployment footguns require VPS ownership/mode confirmation. |
| Frontend browser security | CSP, rich text, service worker, Supabase bridge | Reported and rejected | Supabase logout/storage issue reported. Rich-text SSR fail-open suppressed by backend Bleach sanitization on persisted manuscript paths. |

## Open Questions And Follow Up

- Confirm whether production ingress is Render-only, Nginx/VPS, Cloudflare-proxied, or mixed. This changes severity for `DEPLOY-004` and `DEPLOY-005`.
- Run focused backend integration tests for collaborator-scoped manuscript access: workspace search, scene update, scene insert preview, scene restore, and workspace tree.
- Add parser regression fixtures for DOCX/EPUB archive bombs and a timing harness for workspace regex ReDoS.
- Confirm Paddle/Supabase production settings: placeholder secret rejection, Paddle metadata mutability, Supabase email verification guarantees, and OAuth logout storage cleanup.
- Complete rendered UI QA once the local dev server and Browser sandbox are available.
