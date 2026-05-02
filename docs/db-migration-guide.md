# Database Migration Guide

This guide explains how to run Alembic migrations for LoreVia in three environments:

- Local Docker
- Dev Supabase
- Prod Supabase

It also covers prod backup and restore workflow, recovery from a broken `public` schema, and how migrations behave in CI/CD.

## Core rules

- Run migrations from the `backend` project root unless the command explicitly says otherwise.
- Use the repo's Alembic environment and versioned code, not a globally installed Alembic.
- Never point a local Docker migration at a Supabase database by accident.
- For any non-local database, set `ALEMBIC_DATABASE_URL` explicitly.
- For any remote database, set `ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE`.
- Do not use destructive upgrade or downgrade overrides unless you have reviewed the migration and explicitly intend to drop data.

## Environment variables

These variables control Alembic behavior in this repo:

- `ALEMBIC_DATABASE_URL`
  - Optional for local Docker if the app settings already point at the container network database.
  - Required for remote Supabase databases.
- `ALEMBIC_CONFIRM_REMOTE`
  - Required for remote databases.
  - Set to `YES_I_AM_SURE`.
- `ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES`
  - Only set to `1` if you have reviewed the migration and intentionally want to allow destructive operations in `upgrade()`.
- `ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES`
  - Only set to `1` if you intentionally want to allow destructive `downgrade()` steps.

## Local Docker migrations

Use this path when the app, worker, Postgres, and Redis are running through `docker compose`.

### Start the stack

```powershell
docker compose -f docker-compose-local.yml up --build
```

### Run migrations

Run Alembic inside the API container so it can reach the container network database:

```powershell
docker compose -f docker-compose-local.yml exec api python -m alembic upgrade head
```

### Create a new migration

```powershell
docker compose -f docker-compose-local.yml exec api python -m alembic revision --autogenerate -m "your message"
```

### Useful checks

```powershell
docker compose -f docker-compose-local.yml exec api python -m alembic current
docker compose -f docker-compose-local.yml exec api python -m alembic heads
```

### Reset local data

If the local schema is out of sync and you do not need to preserve local data:

```powershell
docker compose -f docker-compose-local.yml down -v
docker compose -f docker-compose-local.yml up --build
docker compose -f docker-compose-local.yml exec api python -m alembic upgrade head
```

## Dev Supabase migrations

Use this path when you are migrating a remote dev Supabase database from your local backend environment.

### Set the target database

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://<user>:<password>@<dev-host>:5432/postgres?sslmode=require"
$env:ALEMBIC_CONFIRM_REMOTE="YES_I_AM_SURE"
```

### Inspect current state

```powershell
cd C:\Users\madha\.vscode\prod\LoreVia2\backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

### Run the migration

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Create a migration

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "your message"
```

### Verify after the run

```powershell
& psql "$env:ALEMBIC_DATABASE_URL" -c "select * from public.alembic_version;"
```

## Prod Supabase migrations

Use this path only after:

- You have tested the exact migration chain on a full clone of prod.
- You have taken a fresh backup of prod.
- You have confirmed the target database host and project ref.

Before every prod migration:

1. Confirm the target database is the real prod project.
2. Confirm `public.alembic_version` matches the expected current revision.
3. Confirm critical app tables exist in `public`:
   - `users`
   - `books`
   - `book_obsidian_notes`
4. Confirm you have a fresh database dump saved outside Supabase.
5. Confirm you have already tested the same Alembic sequence on a full prod clone.

### Recommended prep

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://<user>:<password>@<prod-host>:5432/postgres?sslmode=require"
$env:ALEMBIC_CONFIRM_REMOTE="YES_I_AM_SURE"
```

Only set destructive overrides if you intentionally want them:

```powershell
$env:ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES="1"
```

### Inspect current state

```powershell
cd C:\Users\madha\.vscode\prod\LoreVia2\backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

### Run the migration

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Verify after the run

```powershell
& psql "$env:ALEMBIC_DATABASE_URL" -c "select * from public.alembic_version;"
```

### Backup before prod

Create a dump before applying prod migrations:

```bash
pg_dump "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require" -F c -f dump.dump
```

### Restore backup

Use `pg_restore` when you need to rebuild a Supabase database from a known-good dump:

```bash
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  -d "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require" \
  dump.dump
```

Use this when:

- The target database is disposable or already empty.
- You want to rebuild the database from a known-good dump.
- You understand that `--clean` drops existing objects before restoring them.

If you only want to restore `public`, use:

```bash
pg_restore \
  --schema=public \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  -d "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require" \
  dump.dump
```

### If prod `public` gets nuked

If the app schema in `public` is gone or empty:

1. Stop all writes to prod immediately.
2. Confirm that `auth` and `storage` still exist and were not touched.
3. Check whether you have a usable dump.
4. If you have a dump, restore it with `pg_restore`.
5. If you do not have a dump, recreate `public` and replay migrations only if you intentionally want a clean rebuild.
6. Verify the rebuilt schema before reconnecting the app.

If you intentionally want to rebuild only the app schema and leave Supabase-managed schemas alone:

```sql
drop schema if exists public cascade;
create schema public;
```

This affects only `public`.

It does not remove:

- `auth`
- `storage`
- other non-`public` schemas

### Post-restore validation

After restore or rebuild, verify:

```sql
select current_database(), current_schema();

select table_schema, table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;

select * from public.alembic_version;
```

You should also confirm that the app can connect and that the expected tables exist before allowing writes again.

## CI/CD for prod

Yes, the migration runs the same in CI/CD if the pipeline uses the same Alembic command and the same code revision.

### What must be the same

- The repo commit or release tag
- The Alembic migration files
- The database URL
- The required confirmation variables

### What usually changes

- The execution environment
- How secrets are injected
- Whether the command runs inside a container image or a hosted runner

### Recommended CI/CD command

Run the same backend command the repo uses locally:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Or, if your CI image builds the backend container, run Alembic inside that image with the same environment variables set.

### CI/CD safety checks

- Set `ALEMBIC_DATABASE_URL` explicitly.
- Set `ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE`.
- Keep destructive overrides disabled unless you intentionally need them.
- Ensure the pipeline uses the expected migration revision.
- Prefer a separate migration job before the app deploy job.

## GitHub Secrets For Safe Migration

For the current `database-migrations.yml` workflow, the only required GitHub Secret for the prod migration job is:

- `DATABASE_URL`
  - The full Supabase connection string for the target database.
  - Used for the backup step, the Alembic upgrade step, and the post-migration verification step.

Recommended practice:

- Store `DATABASE_URL` in the `production` environment, not as a repo-wide secret.
- Use a dedicated production database password for GitHub Actions if possible.
- Rotate that password if it has ever been pasted into chat or logs.

Workflow values that are not secrets but should remain explicit in the workflow:

- `ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE`
- `ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES=1` only when you intentionally need it
- `ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES=1` only for deliberate downgrade testing

Other app/runtime secrets may still be needed by the broader CI or deploy pipeline, but they are not required just to run the migration job shown in this repo:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `OPENAI_API_KEY`
- `JWT_SECRET`
- `RESEND_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `PADDLE_WEBHOOK_SECRET`
- `SENTRY_DSN`

If your GitHub Actions deployment job also starts the full backend application, add the runtime secrets for that deployment separately. Keep migration secrets as small and isolated as possible.

## What went wrong in the incident

- Dev and prod were not in the same schema state.
- Prod had a broken or empty `public` schema but still had a stale `alembic_version`.
- `alembic upgrade heads` continued from a revision state that did not match the real tables.
- Supabase `auth` is separate from your app schema, but your app data lives in `public`, so a `public` reset can look like the whole database is gone.

## Safe prod sequence

1. Verify the prod project ref and connection string.
2. Run `pg_dump` and save the dump offsite.
3. Test the exact migration sequence on a full clone of prod.
4. If the clone succeeds, run the same migration sequence on prod.
5. Validate the schema after migration.
6. Confirm `alembic_version` reaches the expected heads.

## Quick recovery checklist

If you suspect prod `public` is damaged:

1. Stop writes.
2. Check `public.alembic_version`.
3. Check whether the core tables exist in `public`.
4. Restore from dump if available.
5. Rebuild `public` only if you intentionally want a fresh app schema.
6. Reconnect the app only after validation.

## Quick reference

### Local Docker

```powershell
docker compose -f docker-compose-local.yml exec api python -m alembic upgrade head
```

### Dev Supabase

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://<user>:<password>@<dev-host>:5432/postgres?sslmode=require"
$env:ALEMBIC_CONFIRM_REMOTE="YES_I_AM_SURE"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Prod Supabase

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://<user>:<password>@<prod-host>:5432/postgres?sslmode=require"
$env:ALEMBIC_CONFIRM_REMOTE="YES_I_AM_SURE"
.\.venv\Scripts\python.exe -m alembic upgrade head
```
