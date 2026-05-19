# LoreVia Public Book Admin Moderation Guide

Last updated: 2026-05-19

This is the internal admin runbook for handling copyrighted, infringing, or otherwise policy-violating public books on LoreVia.

It is written against the moderation behavior currently implemented in the repo. It explains:

- how a public book gets flagged
- how to hide or remove a public book
- how to add strikes to repeat infringers
- how public publishing is disabled for repeat offenders
- what gaps still exist in the current admin tooling

## Scope

This guide covers moderation of LoreVia public books only.

It does not cover:

- private manuscript review
- a formal DMCA registered-agent workflow
- legal advice
- a full account-suspension system, because that is not yet fully implemented in the backend

## Core moderation model

LoreVia currently moderates public books at two levels:

1. Book-level moderation
   - hide a public book immediately
   - remove a public book after confirmation
   - restore a book if the report was mistaken

2. User-level enforcement
   - add strikes to users who upload infringing or abusive content
   - automatically block future public publishing once serious-strike thresholds are reached

Important distinction:

- A book can be taken down immediately without banning the user.
- A user can be effectively blocked from future public publishing through strikes.
- A full account-wide ban or suspension endpoint is not yet implemented in the backend admin API.



## How admin access works


Short answer: you can give yourself admin access, but not through normal self-service signup. And based on the code I checked, a regular user should not be able to just claim admin access through the app.

How admin access is created now:
- New users are created with `tier = "free"` by default in [backend/app/models/user.py](C:/Users/madha/.vscode/prod/LoreVia2/backend/app/models/user.py).
- Normal register and OAuth signup flows in [backend/app/api/v1/routes/auth.py](C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/auth.py) do not let the client choose `tier`.
- Admin routes are protected by `get_admin` in [backend/app/api/deps/auth.py](C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/deps/auth.py), which only allows requests when `current_user.tier == "admin"`.

So for the first admin account, the realistic path is:
1. Create a normal account.
2. Verify the email.
3. Update that user’s `tier` in the database to `admin`.
4. Sign in normally with that account.

The DB change is the bootstrap step. Example shape:

```sql
update users
set tier = 'admin'
where email = 'you@example.com';
```

After that, you log in like any normal user. There is no separate “admin login” flow. Your session becomes admin-capable because your stored user record says `tier = 'admin'`.

Once you already have one admin account, that admin can promote another user through:
- `PUT /api/v1/admin/users/{user_id}/tier`


## LoreVia does not use a separate special admin login page in the backend code reviewed here.

Admin access works through the normal authentication flow plus an admin-tier account.

Current rule:

- you sign in the same way as any other user
- your account must have `tier = "admin"`
- admin endpoints are protected by `get_admin`
- `get_admin` allows the request only when the authenticated user’s tier is exactly `admin`

Relevant auth file:

- [backend/app/api/deps/auth.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/deps/auth.py)

What this means in practice:

- there is no separate “log in as admin” mechanism
- there is no impersonation route in the code reviewed here
- there is no public admin magic link flow shown in the current backend code
- you must authenticate as a real LoreVia user whose stored tier is `admin`

## How to log in as an admin in practice

### If you already have an admin account

Use the normal LoreVia sign-in flow.

After signing in:

- the app issues the same access / refresh auth session it uses for normal users
- your requests to admin endpoints succeed because your user record has `tier = "admin"`

From that point, you can:

- use the frontend if an admin surface exists
- or call admin API routes directly with the same authenticated session or bearer token

### If you do not yet have an admin account

One account must already be marked as admin in the database before it can use admin routes.

Important limitation:

- the existing `PUT /api/v1/admin/users/{user_id}/tier` route itself requires admin access
- that means it cannot bootstrap the very first admin account by itself

Practical bootstrap options for the first admin account:

1. Mark the intended account as `tier = 'admin'` directly in the database.
2. Use an already-existing admin account to promote another user.

For the very first admin, the usual approach is a direct database update performed carefully in a trusted environment.

Example SQL shape:

```sql
update users
set tier = 'admin'
where email = 'you@example.com';
```

Only do this in a controlled environment and only for trusted internal accounts.

### How to verify admin access

Once signed in as the intended admin user, test a protected admin endpoint such as:

- `GET /api/v1/admin/reports`

If access is working:

- the endpoint returns data or an empty list

If access is not working:

- the endpoint returns `403 Admin only`

## How to use admin auth when banning a book

The “ban the book” workflow uses your normal authenticated admin session.

There is no separate admin token type in the route layer reviewed here.

In practice:

1. Sign in with your admin-tier LoreVia account.
2. Confirm your account can access an admin route.
3. Use that same authenticated session to call:
   - `GET /api/v1/admin/reports`
   - `POST /api/v1/admin/books/{book_id}/hide`
   - `POST /api/v1/admin/books/{book_id}/remove`
   - `POST /api/v1/admin/books/{book_id}/restore`
   - `POST /api/v1/admin/users/{user_id}/strikes`

## How a public book gets flagged

There are three practical ways a book enters moderation:

1. A public report is submitted
   - `POST /api/v1/reports/content`
   - stored as a `content_reports` row
   - creates a moderation action log entry
   - notifies admin users

2. Automated risk signals exist on the book
   - examples: `isbn`, `copyright_warning`
   - these are signals for review, not automatic permanent takedown decisions by themselves

3. An admin manually reviews the book
   - based on report queue, user history, obvious infringement, or direct observation

## Important current behavior for copyright reports

Copyright reports are intentionally handled conservatively.

Current behavior:

- a copyright report creates a report row
- the book is automatically hidden
- the report status becomes `content_hidden`
- a moderation action is logged

This means LoreVia currently follows a:

- hide first
- review second

pattern for copyright complaints.

## Public visibility states that matter

The public reader only exposes books that pass the central visibility check.

In practice, a public book should only be visible when it is:

- `is_public = true`
- `public_status = published`
- `moderation_status = clean`

Books should not be publicly visible if they are:

- `hidden`
- `removed`
- `reported`
- `under_review`
- `pending_review`

## Admin moderation actions

### 1. View incoming reports

Endpoint:

- `GET /api/v1/admin/reports`

What it returns:

- report ID
- reported book ID
- reported author user ID
- reporter user ID if logged in
- reporter email if provided
- report type
- report status
- reason
- details
- created timestamp

Use this as the primary queue when reviewing infringement complaints.

### 2. View pending public-share review requests

Endpoint:

- `GET /api/v1/admin/public-shares/pending`

What it returns:

- `book_id`
- `user_id`
- `author_username`
- `title`
- `author`
- `genre`
- `isbn`
- `copyright_warning`
- `public_description`
- `requested_at`
- `created_at`

Use this when reviewing manuscripts that authors want to make public through the share-review workflow.

Important:

- this is not the same as the reports queue
- this is a pre-publication review surface for pending shares

## Book-level enforcement actions

### Hide a book

Use when:

- a copyright complaint arrives
- the claim looks credible
- you need time to investigate
- the content may violate policy but you do not want to make a permanent decision yet

Endpoint:

- `POST /api/v1/admin/books/{book_id}/hide`

Request body:

```json
{
  "reason": "Copyright complaint received from rights owner."
}
```

What it does:

- sets `moderation_status = hidden`
- sets `public_status = hidden`
- sets `is_public = false`
- records `takedown_reason`
- records `takedown_at`
- records `takedown_by_user_id`
- logs a `book_hidden` moderation action

Operational meaning:

- the book is immediately removed from public visibility
- the manuscript itself is not deleted
- this is the safest default action during review

### Remove a book

Use when:

- infringement is confirmed
- the uploader clearly lacks rights
- the content is a repeated or severe policy violation

Endpoint:

- `POST /api/v1/admin/books/{book_id}/remove`

Request body:

```json
{
  "reason": "Confirmed unauthorized upload of copyrighted novel."
}
```

What it does:

- sets `moderation_status = removed`
- sets `public_status = removed`
- sets `is_public = false`
- records takedown metadata
- logs a `book_removed` moderation action

Operational meaning:

- the book is permanently out of public circulation unless later restored manually
- use this after review, not as the first response unless the violation is obvious

### Restore a book

Use when:

- the report was mistaken
- the uploader provided adequate proof of rights
- the content was hidden defensively and later cleared

Endpoint:

- `POST /api/v1/admin/books/{book_id}/restore`

Request body:

```json
{
  "reason": "Rights verified by author."
}
```

What it does:

- sets `moderation_status = clean`
- sets `public_status = published`
- sets `is_public = true`
- clears takedown metadata
- logs a `book_restored` moderation action

## User-level enforcement with strikes

### Add a strike

Use when:

- infringement is confirmed
- the same user repeats policy violations
- you need a durable enforcement history tied to the account

Endpoint:

- `POST /api/v1/admin/users/{user_id}/strikes`

Request body:

```json
{
  "book_id": "BOOK_UUID",
  "report_id": "REPORT_UUID",
  "strike_type": "copyright_violation",
  "severity": "high",
  "reason": "Confirmed unauthorized upload of a copyrighted commercial novel."
}
```

Available fields from the current schema:

- `book_id`
- `report_id`
- `strike_type`
- `severity`
- `reason`

Recommended values for copyright cases:

- `strike_type = "copyright_violation"`
- `severity = "high"`

Use `critical` only for especially egregious cases such as:

- repeated bad-faith uploads
- evasion after prior takedowns
- obvious library-style piracy behavior

What the endpoint does:

- creates a `creator_strikes` row
- logs a `strike_added` moderation action
- recalculates the user’s serious-strike count

## How public publishing gets blocked

Public publishing restrictions are enforced when the user tries to publish new public books.

Current serious strike levels:

1. One serious strike
   - creates a documented warning history
   - does not yet auto-block publishing on its own

2. Two serious strikes
   - public publishing becomes temporarily disabled
   - the publish endpoint returns a `403`

3. Three serious strikes
   - public publishing becomes disabled due to repeated policy violations
   - the publish endpoint returns a stronger `403`

Important:

- this is currently a public-publishing ban, not a full account ban
- the user may still have an account unless a separate account suspension mechanism is added later

## Recommended admin playbooks

### Playbook A: First credible copyright complaint

Use when:

- the reporter appears legitimate
- the complaint identifies the book clearly
- the upload plausibly infringes copyright

Steps:

1. Find the report in `GET /api/v1/admin/reports`
2. Hide the book immediately
3. Review the book metadata, uploader, ISBN, and `copyright_warning`
4. Ask the uploader for proof of rights if needed
5. If confirmed, remove the book
6. Add a `high` copyright strike to the uploader

Recommended outcome:

- book hidden immediately
- book removed if confirmed
- one serious strike added

### Playbook B: Obvious pirated commercial novel

Use when:

- the title and author clearly match a third-party copyrighted work
- the uploader is not the rights holder
- the upload is plainly unauthorized

Steps:

1. Remove the book immediately
2. Add a `high` or `critical` copyright strike
3. Check for other public books from the same user
4. Hide or remove any similar uploads
5. If the user already has prior serious strikes, confirm they are now blocked from future public publishing

Recommended outcome:

- immediate removal
- serious strike
- account flagged through strike history

### Playbook C: Repeat infringer

Use when:

- the same user has already been warned or struck
- a new infringing upload appears

Steps:

1. Remove the new book
2. Add another serious strike
3. Confirm the user now has at least 2 active serious strikes
4. Treat the user as blocked from future public publishing
5. If they reach 3 serious strikes, treat them as permanently disallowed from public publishing until code adds a formal reinstatement path

Recommended outcome:

- new book removed
- repeat-infringer history recorded
- user effectively banned from public publishing

### Playbook D: False report or valid rights proof

Use when:

- the uploader proves they own the rights
- the report is mistaken
- the content is original or licensed

Steps:

1. Review evidence
2. Restore the book
3. Do not add a strike
4. Document the reason in the restore action

Recommended outcome:

- book restored
- no user penalty

## How to think about “banning a book” versus “banning a user”

### Banning a book

In current LoreVia behavior, “banning a book” means:

- hide it now, or
- remove it from public visibility

Practical actions:

- temporary ban from visibility: `hide`
- confirmed permanent removal from public catalog: `remove`

### Banning a user

In current LoreVia behavior, “banning a user” means:

- using strikes to disable future public publishing

What currently exists:

- effective ban from future public book publishing after repeated serious strikes

What does not yet exist:

- dedicated `suspend user` admin endpoint
- dedicated `ban user account` admin endpoint
- dedicated user status field like `is_suspended`

So today:

- yes, you can stop their public books
- yes, you can stop them from publishing more public books after repeated serious strikes
- no, you cannot yet fully shut down the entire account through a dedicated admin ban route

## Example API calls

These examples assume:

- you are authenticated as an admin
- the API base URL is `https://api.getlorevia.com`
- you are sending the same auth token your admin frontend would use

### List reports

```bash
curl -X GET "https://api.getlorevia.com/api/v1/admin/reports" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Hide a book

```bash
curl -X POST "https://api.getlorevia.com/api/v1/admin/books/<BOOK_ID>/hide" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Copyright complaint received from rights owner."
  }'
```

### Remove a book

```bash
curl -X POST "https://api.getlorevia.com/api/v1/admin/books/<BOOK_ID>/remove" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Confirmed unauthorized upload of copyrighted commercial work."
  }'
```

### Restore a book

```bash
curl -X POST "https://api.getlorevia.com/api/v1/admin/books/<BOOK_ID>/restore" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Rights verified by uploader."
  }'
```

### Add a strike

```bash
curl -X POST "https://api.getlorevia.com/api/v1/admin/users/<USER_ID>/strikes" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "<BOOK_ID>",
    "report_id": "<REPORT_ID>",
    "strike_type": "copyright_violation",
    "severity": "high",
    "reason": "Confirmed unauthorized upload of copyrighted commercial novel."
  }'
```

## Audit trail and records

Every serious moderation step should leave evidence in the database.

Current audit structures:

- `content_reports`
- `creator_strikes`
- `moderation_actions`

Moderation actions currently log events such as:

- `report_created`
- `book_hidden`
- `book_removed`
- `book_restored`
- `strike_added`

This is important for:

- internal accountability
- handling disputes
- identifying repeat infringers
- reconstructing why a book or user was restricted

## Operational recommendations

Use these defaults unless there is a strong reason not to:

- hide first for copyright complaints
- remove after confirmation
- add a strike for confirmed infringement
- use `high` severity for confirmed unauthorized copyrighted uploads
- escalate to `critical` only when behavior is repeated, evasive, or clearly malicious

Also:

- keep reasons specific and factual
- include the source of the complaint when possible
- avoid vague reasons like `bad content`

Good reason examples:

- `Copyright complaint received from author representative.`
- `Confirmed unauthorized upload of commercially published novel.`
- `Repeat infringing upload after prior takedown.`

## Current tooling gaps

These are important current limitations.

### No full admin frontend moderation console

The backend moderation endpoints exist, but there does not appear to be a full repo-local frontend admin review UI for:

- report queue triage
- hide/remove/restore actions
- strike issuance

### No dedicated user suspension endpoint

There is currently no explicit endpoint like:

- `POST /api/v1/admin/users/{user_id}/suspend`
- `POST /api/v1/admin/users/{user_id}/ban`

Today, user enforcement is done through strike-based public-publishing restrictions.

### No explicit strike removal endpoint yet

The moderation model anticipates strike removal in the audit vocabulary, but the current admin route file does not expose a dedicated strike-removal endpoint.

## Recommended next improvements

If LoreVia wants a more complete moderation system, the next additions should be:

1. A frontend admin moderation page
   - report queue
   - book review
   - hide/remove/restore actions
   - strike history

2. A real user suspension endpoint
   - full account suspension
   - optional read-only mode
   - optional login disable

3. A strike management endpoint
   - remove or expire strikes
   - record appeal outcomes

4. A repeat-infringer dashboard
   - open reports by user
   - active strike counts
   - prior takedowns

## Bottom line

Current LoreVia admin moderation is strong enough to:

- receive copyright reports
- hide books immediately
- remove confirmed infringing books
- record moderation actions
- strike repeat infringers
- disable future public publishing for repeat offenders

Current LoreVia admin moderation is not yet complete enough to:

- fully ban user accounts with a dedicated admin route
- manage everything through a polished frontend admin dashboard

If you are moderating copyrighted uploads today, the safest operational flow is:

1. review the report
2. hide the book immediately
3. confirm the infringement
4. remove the book
5. add a serious strike
6. rely on strike thresholds to block future public publishing
