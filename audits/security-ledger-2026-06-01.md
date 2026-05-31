# LoreVia Security Scan Ledger - 2026-06-01

Scan target: `C:\Users\madha\.vscode\prod\LoreVia2`

Commit inspected: `561cb09edf775a9616ab628eb89296cd1bf93680`

External artifact note: the intended `C:\tmp\codex-security-scans\LoreVia2\fc57bf7_20260601T025956` report write was blocked by the desktop approval/usage system. This workspace ledger is the safer sandboxed substitute.

## Coverage Receipts

| Area | Full-read or focused receipts | Outcome |
|---|---|---|
| Auth/session | `backend/app/api/deps/auth.py`, `backend/app/api/v1/routes/auth.py`, `backend/app/utils/auth_csrf.py`, `backend/app/utils/auth_cookies.py`, `backend/app/utils/admin_security.py` | Reported `AUTH-001`, `AUTH-002`; lower-priority races/timing/config rows retained below. |
| Upload/parser/collaborator access | `backend/app/api/v1/routes/books/imports.py`, `backend/app/api/v1/routes/manuscript.py`, `backend/app/utils/upload_security_utils.py`, `backend/app/core/storage.py`, `backend/app/utils/world_building_utils.py` | Reported collaborator boundary breaks and resource exhaustion paths. |
| Public/social/collaboration | `backend/app/api/v1/routes/public.py`, `social.py`, `collaboration.py`, `beta_reads.py`, `backend/app/utils/public_utils.py` | Reported moderation and takedown bypasses; social/collaboration/beta-read IDOR paths suppressed. |
| Billing/internal/webhooks | `backend/app/api/v1/routes/billing.py`, `webhooks.py`, `backend/app/services/paddle_service.py`, `paddle_webhook_service.py`, `backend/app/api/v1/routes/internal.py` | Reported placeholder secret, internal-job rate-limit, URL token issues. |
| Deployment/edge | `backend/app/main.py`, `backend/app/core/config.py`, `ops/nginx/nginx.conf`, `docker-compose.yml`, `deploy.sh` | Reported Docker secret-context and forged Cloudflare header paths. |
| Frontend security | `frontend/src/middleware.ts`, `frontend/src/lib/api/client.ts`, `frontend/src/lib/supabase.ts`, `frontend/src/components/editor/SharedRichTextEditor.tsx`, `frontend/public/sw.js` | Reported Supabase session persistence after logout. |
| UI/UX | `frontend/src/app/**/page.tsx`, layout components, public assets, nav and shell components | Source/static audit completed; rendered browser QA blocked. |

## Candidate Closure

| Candidate | Disposition | Receipt |
|---|---|---|
| `AUTH-001` | Reported | Supabase OAuth email fallback ignores existing subject mismatch before token mint. |
| `AUTH-002` | Reported | Bearer-looking `Authorization` header suppresses cookie CSRF while cookies remain usable. |
| `AUTH-003` | Needs follow-up | Supabase unverified/weak email auto-link depends on provider production settings. |
| `AUTH-004` | Needs follow-up | Transparent refresh fallback mints access cookie without rotating refresh session. |
| `AUTH-005` | Needs follow-up | Refresh check-then-revoke race can mint sibling sessions under concurrency. |
| `AUTH-006` | Needs follow-up | Password reset token consume race needs focused Redis/runtime test. |
| `AUTH-007` | Needs follow-up | Verification token consume race is lower impact but similar. |
| `AUTH-008` | Needs follow-up | Bearer-only admin step-up session id collapses to `access`; production bearer-admin use unknown. |
| `AUTH-009` | Reviewed not final | Login timing oracle; low severity due throttling and no direct compromise. |
| `AUTH-010` | Reviewed not final | Forgot-password timing oracle; low severity sibling of auth timing risk. |
| `AUTH-011` | Deferred | Parent-domain cookie overwrite depends on sibling subdomain control. |
| `FILE-001` | Reported | Workspace manuscript search omits collaborator chapter filter. |
| `FILE-002` | Reported | Workspace scene search omits collaborator chapter filter. |
| `FILE-003` | Reported | Scene update checks destination chapter but not current scene chapter. |
| `FILE-004` | Reported | Scene insert preview checks destination chapter but not source scene chapter. |
| `FILE-005` | Needs follow-up | Scene-version restore checks historical version chapter, not current scene chapter. |
| `FILE-006` | Needs follow-up | Workspace tree can return persisted structure tree verbatim. |
| `FILE-007` | Reported | DOCX/EPUB book upload validators do not enforce ZIP bomb safety. |
| `FILE-008` | Reported via `FILE-007` | Manuscript import reaches same DOCX validator/parser path. |
| `FILE-009` | Reported via `FILE-014` | World-building DOCX upload bypasses structural ZIP safety. |
| `FILE-010` | Reported via `FILE-007` | Book EPUB upload reaches EbookLib after shallow mimetype validation. |
| `FILE-011` | Reported via `FILE-007` | Manuscript EPUB import reaches same parser path. |
| `FILE-012` | Reported via `FILE-014` | World-building EPUB upload bypasses structural ZIP safety. |
| `FILE-013` | Reported | Manuscript import tracks aggregate file size but never enforces it. |
| `FILE-014` | Reported | World-building upload parses before entitlement checks. |
| `FILE-015` | Deferred | PDF parser resource stress needs controlled runtime fixture. |
| `FILE-016` | Deferred | Manuscript PDF import shares deferred PDF parser stress path. |
| `FILE-017` | Deferred | World-building PDF upload shares deferred PDF parser stress path. |
| `FILE-018` | Reported | Caller-controlled Python regex runs across manuscript/scene text without timeout. |
| `PUBLIC-001` | Reported | Owner publish route bypasses manual public-share moderation. |
| `PUBLIC-002` | Reported | Anonymous copyright report can hide arbitrary book by UUID. |
| `PUBLIC-003` | Reported | Hidden/removed books remain public forum eligible. |
| `PUBLIC-004` | Needs follow-up | Catalog cache stale after takedown/unpublish; secondary to `PUBLIC-003`. |
| `PUBLIC-005` | Needs follow-up | Forum caches stale after takedown; fix with `PUBLIC-003`. |
| `PUBLIC-006` | Needs follow-up | Writer-profile cache can retain hidden-book data. |
| `PUBLIC-007` | Reviewed not final | Anonymous analytics/ranking spoofing is lower severity integrity abuse. |
| `BILL-001` | Reported | Published Paddle webhook placeholder accepted as configured secret. |
| `BILL-002` | Needs follow-up | Published internal-job placeholder accepted; same placeholder-control family. |
| `BILL-003` | Reported | Internal-job rate limit keyed by attacker-supplied secret guess. |
| `BILL-004` | Reviewed not final | Invalid UTF-8 causes webhook 500; low-impact parser availability. |
| `BILL-005` | Deferred | Webhook tier trusts `custom_data.plan`; Paddle metadata mutability unknown. |
| `BILL-006` | Deferred | Product-label fallback can authorize tiers without price allowlist; catalog controls unknown. |
| `BILL-007` | Deferred | Subscription fallback to latest user row needs multi-subscription runtime proof. |
| `BILL-008` | Reported | Billing confirmation capability is propagated through URLs. |
| `BILL-009` | Deferred | Zero webhook replay tolerance disables freshness only if misconfigured. |
| `DEPLOY-001` | Reported | Backend image can bake local env secret files. |
| `DEPLOY-002` | Reported | Docker build context includes TLS private keys/unrelated secrets. |
| `DEPLOY-003` | Needs follow-up | Redis receives the full backend env file; blast radius hardening. |
| `DEPLOY-004` | Reported | Cloudflare tunnel enforcement accepts forged direct-origin header. |
| `DEPLOY-005` | Reported | Application rate limits trust forged `CF-Connecting-IP`. |
| `DEPLOY-006` | Needs follow-up | Deploy script sources `.env` as shell code. |
| `DEPLOY-007` | Needs follow-up | Systemd unit sources mutable `.env` as root shell code. |
| `DEPLOY-008` | Needs follow-up | `DEBUG=true` can expose reset URL in response. |
| `DEPLOY-009` | Needs follow-up | `DEBUG=true` grants Architect entitlements. |
| `DEPLOY-010` | Needs follow-up | Deploy auto-confirms remote Alembic execution. |
| `DEPLOY-011` | Needs follow-up | Destructive migration scanner misses several destructive operations. |
| `FRONTSEC-001` | Reported | Supabase OAuth refresh token remains in localStorage after LoreVia logout. |

## Blockers And Limits

- No Docker services were running.
- The local Next dev-server launch was blocked by the desktop approval/usage system.
- The in-app Browser sandbox failed before navigation, so rendered visual QA is not claimed.
- The external `C:\tmp` scan bundle write was blocked by the same approval/usage system; reports were written under `audits/` instead.
