# LoreVia Admin Operations Guide

This guide is the operational source of truth for LoreVia admins. Admin access is never created by registration, payment, email address, subscription tier, or frontend state. A user becomes an admin only when an active row exists in `admin_principals`.

## Becoming an Admin

First owner bootstrap is a trusted database operation on an existing verified user account.

Checklist:
- Confirm the target user exists in `users` and has the expected email and username.
- Confirm the user is the intended owner.
- Insert one `admin_principals` row with `status='active'`, `is_owner=true`, and all required scopes.
- Record a clear `grant_reason`.
- Do not expose bootstrap through an API, frontend form, support script, or public route.

Example bootstrap SQL:

```sql
insert into admin_principals (
  id,
  user_id,
  status,
  is_owner,
  scopes,
  grant_reason,
  created_at,
  updated_at
) values (
  gen_random_uuid(),
  '<verified-user-id>',
  'active',
  true,
  array['moderation_admin', 'billing_admin', 'super_admin'],
  'Initial owner bootstrap approved by LoreVia owner.',
  now(),
  now()
);
```

After bootstrap, owner admins grant or revoke access from `/admin`. Admin access must not be granted by changing `users.tier`.

## Permission Scopes

- `moderation_admin`: public-share review, content reports, book hide/remove/restore actions, creator strikes, and public demo book management.
- `billing_admin`: billing visibility, refund review workflows, and subscription metrics.
- `super_admin`: product tier changes, operational system views (platform metrics, queue depth), and rate limit management.
- Owner admin: grant and revoke admin access and view admin audit history.

Owner status is separate from scopes. Use owner access only for people trusted to manage admin privileges.

## Admin Session Rules

Checklist:
- Use your own account only.
- Do not share admin accounts or session cookies.
- Complete step-up verification before refunds, privilege changes, user tier changes, takedowns, removals, restores, or strikes.
- If an admin device or account is suspected compromised, revoke the admin principal immediately.

The admin frontend receives capabilities only from `GET /api/v1/admin/session`. Normal `/auth/me` responses are not admin authority.

## Public Book Review

Checklist:
- Open `/admin`.
- Review pending public-share submissions.
- Confirm the book appears to be user-owned or properly authorized.
- Approve only if it satisfies LoreVia policy.
- Reject with a clear reason when rights, safety, or quality concerns require rejection.
- Confirm the audit log records the decision.

Reason text should include the policy basis and the visible evidence, for example: `Rejected because the description indicates a third-party franchise work without rights confirmation.`

## Hide, Remove, and Restore Books

Use hide for temporary visibility removal. Use remove for stronger policy enforcement. Use restore only when the issue is resolved.

Checklist:
- Confirm the book ID and current public status.
- Check reports and previous audit events.
- Enter a specific reason.
- Complete step-up verification.
- Run hide, remove, or restore from `/admin`.
- Verify the public page no longer shows removed/hidden content, or shows restored content when applicable.
- Confirm the audit log entry exists.

Do not remove or restore a book without a concrete policy or support reason.

## Content Reports and Strikes

Checklist:
- Review the report details and reported book.
- Compare the report to the visible content and LoreVia policy.
- If the report is valid, take the least severe action that addresses the issue.
- Add a creator strike only when the violation warrants account-level history.
- Include the report ID, book ID, violation type, and evidence in the reason.
- Confirm the moderation action and admin audit event were recorded.

## Refund Reviews

Automated refunds are intentionally narrow. Most ambiguous cases should remain manual.

Checklist:
- Confirm the Paddle transaction ID, user, plan, interval, charge time, usage snapshot, and previous refund count.
- Approve only when the refund is policy-eligible and low risk.
- Deny with a specific policy reason when the request is outside the refund policy.
- Use provider-follow-up-only when the local subscription linkage is not safe enough for direct approval.
- Confirm Paddle adjustment status through webhooks or provider follow-up.
- Confirm entitlements change only through Paddle subscription lifecycle webhooks.

Reject examples:
- `Denied because the request was outside the 24-hour automated window and post-charge usage was detected.`
- `Denied because this account has reached the automated refund history limit and no billing error was found.`

Provider follow-up examples:
- `Provider follow-up required because the transaction could not be linked to an active local subscription for immediate cancellation.`

## User Tier Changes

User tier changes affect product access only. They do not grant admin permissions.

Checklist:
- Confirm the target user ID.
- Confirm the requested product tier is `free`, `author`, or `architect`.
- Complete step-up verification.
- Change the tier from `/admin`.
- Confirm the audit event.

Never set `users.tier` to `admin`. Admin access belongs only in `admin_principals`.

## Platform Monitoring (super_admin)

These read-only views show aggregate platform health.

### Platform Metrics

Access: `GET /admin/metrics` (super_admin)

Available at `/admin` under the **Platform Overview** card. Displays:
- Total users, books, characters
- Indexed chunks and cached summaries count
- Redis memory usage in MB

### Queue Depth

Access: `GET /admin/queue-depth` (super_admin)

Available at `/admin` under the **Worker Queues** card. Shows relative depth of extraction, analysis, embedding, and intelligence queues as bar charts. Useful for spotting worker backlogs.

### Subscription Metrics

Access: `GET /admin/subscription-metrics` (billing_admin)

Available at `/admin` under the **Subscription Metrics** card. Requires a date range and optional reactivation-window parameter. Displays:
- Cohort start/end dates
- Trial starts, trial-to-paid conversions and rate
- Cancellations (resolved, unresolved, total)
- Reactivated and churned post-cancellation counts with churn rate

## Rate Limit Management (super_admin)

Access:
- `GET /admin/rate-limits/{user_id}` (super_admin)
- `PUT /admin/rate-limits/{user_id}` (super_admin + CSRF)

Available at `/admin` under the **Rate Limits** card. Enter a user UUID to look up their current limits and default baselines. Override fields (leave blank to keep platform default):
- Search per hour
- Summary per hour
- Chat per day
- API per minute

Override values persist until cleared. Lookup shows the user email for confirmation. Save requires CSRF validation (Bearer token bypasses this; cookie-based sessions need the `x-admin-csrf-token` header).

## Creator Strikes (moderation_admin + step-up)

Access: `POST /admin/users/{id}/strikes` (moderation_admin + CSRF + step-up)

Available at `/admin` under the **Creator Strikes** card. Requires step-up verification before the form is visible.

Fields:
- User ID (required) — target user UUID
- Severity (dropdown) — low, medium, high, critical
- Strike type (required) — e.g. `copyright`, `plagiarism`, `harassment`
- Book ID (optional) — related book UUID
- Report ID (optional) — related content report UUID
- Reason (required) — detailed justification

Click **Apply strike** to record. The strike is logged in the audit trail. Step-up must be completed within the same session (10-minute Redis TTL).

## Public Demo Book Management (moderation_admin + step-up)

Access:
- `POST /admin/public-books/manual` (moderation_admin + CSRF + step-up)
- `POST /admin/public-books/{id}/chapters` (moderation_admin + CSRF + step-up)

Available at `/admin` under the **Public Demo Books** card. Requires step-up verification before the form is visible.

### Create a Demo Book

Fields:
- Title (required)
- Author (optional)
- Genre (optional)
- Description (optional)
- Chapters — add one or more with title (required), text (required), and description (optional)

Click **Create public demo book** to publish.

### Append a Chapter

Fields:
- Book ID (required) — existing demo book UUID
- Chapter title (required)
- Chapter text (required)
- Description (optional)

Click **Append chapter** to add. Both endpoints require CSRF and step-up.

## Granting and Revoking Admin Access

Grant checklist:
- Confirm the target user identity.
- Confirm owner approval.
- Choose the smallest scope set needed.
- Avoid owner access unless the person must manage admins.
- Enter a reason that names who approved access and why.
- Confirm the audit log.

Revoke checklist:
- Confirm the principal being revoked.
- Enter the revocation reason.
- Revoke from `/admin`.
- Confirm the user token version changed and existing admin sessions are invalidated.
- Confirm the audit log.

## Audit Review

Checklist:
- Use `/admin` audit history for recent events.
- Verify actor, target, action, result, reason, and timestamp.
- Investigate denied attempts, repeated failures, unexpected privilege changes, refund spikes, and unusual moderation volume.
- Escalate any unexplained admin activity to the owner immediately.

## Prohibited Admin Behavior

- Do not share accounts.
- Do not grant admin access without owner approval.
- Do not use `users.tier` for admin access.
- Do not approve refunds outside policy without a documented reason.
- Do not remove or restore public books without evidence and a reason.
- Do not export or expose secrets, tokens, password hashes, reset artifacts, or raw provider payloads unless a secure troubleshooting workflow explicitly requires it.
