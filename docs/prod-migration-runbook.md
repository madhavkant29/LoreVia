# Prod Migration Runbook

This guide is for running Alembic migrations safely against Supabase prod, and for recovering if a prod `public` schema is damaged or emptied.

## Core rule

Never run migrations on prod unless:

1. You have already run the exact same migration chain on a full clone of prod.
2. You have created an external dump of prod immediately before the migration.
3. You have confirmed the target database host and project ref are correct.

Testing on a different database is not enough unless that database is an actual clone of prod.

## What went wrong in this incident

- Dev and prod were not in the same schema state.
- Prod had a broken or empty `public` schema but still had a stale `alembic_version`.
- `alembic upgrade heads` continued from a revision state that did not match the real tables.
- Supabase `auth` is separate from your app schema, but your app data lives in `public`, so a `public` reset can look like the whole database is gone.

## Before every prod migration

Run these checks first:

1. Confirm the target database is the real prod project.
2. Confirm `public.alembic_version` matches the expected current revision.
3. Confirm critical app tables exist in `public`:
   - `users`
   - `books`
   - `book_obsidian_notes`
4. Confirm you have a fresh database dump saved outside Supabase.
5. Confirm you have already tested the same Alembic sequence on a full prod clone.

## Recommended backup command

Use `pg_dump` to create a compressed custom-format backup:

```bash
pg_dump "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require" \
  -F c \
  -f dump.dump
```

Notes:

- Replace `<password>` with the Supabase database password.
- Replace `<project-ref>` with the Supabase project ref.
- Store the dump somewhere outside the Supabase project.

## Recommended restore command

Use `pg_restore` when you need to restore the dump back into a Supabase database:

```bash
pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  -d "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require" \
  dump.dump
```

When to use this:

- The target database is disposable or already empty.
- You want to rebuild the database from a known-good dump.
- You understand that `--clean` drops existing objects before restoring them.

## Which command to use

Use `pg_dump` when:

- You want a backup before running migrations.
- You want to clone the current prod state into a file.

Use `pg_restore` when:

- You need to restore from a `.dump` file.
- You want to rebuild the database from a previous backup.

## Safe migration sequence

1. Verify the prod project ref and connection string.
2. Run `pg_dump` and save the dump offsite.
3. Test the exact migration sequence on a full clone of prod.
4. If the clone succeeds, run the same migration sequence on prod.
5. Validate the schema after migration.
6. Confirm `alembic_version` reaches the expected heads.

## If prod `public` gets nuked

If the app schema in `public` is gone or empty:

1. Stop all writes to prod immediately.
2. Confirm that `auth` and `storage` still exist and were not touched.
3. Check whether you have a usable dump.
4. If you have a dump, restore it with `pg_restore`.
5. If you do not have a dump, recreate `public` and replay migrations only if you intentionally want a clean rebuild.
6. Verify the rebuilt schema before reconnecting the app.

## Clean rebuild of `public`

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

## Restore only `public` from a dump

If only the `public` schema was lost and you have a dump that contains the app schema and data, restore just `public` by targeting a database where you want the app schema rebuilt.

Safer sequence:

1. Confirm the dump was taken from the same app version or a compatible schema version.
2. Make sure you are connected to the correct Supabase project.
3. Drop and recreate only `public` if you want a clean rebuild of app tables.
4. Restore the dump into that database.
5. Verify that `auth` still exists and was not touched.
6. Verify the restored `public` tables and data.

If your dump is a full database dump and you only want `public`, use `pg_restore` with schema filters, for example:

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

Notes:

- This is the right choice when you want to restore app tables and data without touching `auth` or other Supabase-managed schemas.
- If the dump already contains only `public`, the `--schema=public` filter is optional.
- If the schema is completely empty, you can also recreate `public` first and then restore into it.

## Post-restore validation

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
