# Hetzner Service Management

This repo uses Docker Compose for the app stack and systemd to make sure the stack starts after a VPS reboot.

## What systemd does here

- Starts the Compose stack on boot
- Stops the Compose stack cleanly on shutdown
- Lets Docker handle per-container restarts with `restart: unless-stopped`

## Install the unit

The recommended path is to let [`deploy.sh`](/C:/Users/madha/.vscode/prod/LoreVia2/deploy.sh) handle this automatically.

If you need to do it manually:

1. Copy [ops/systemd/lorevia-compose.service](/C:/Users/madha/.vscode/prod/LoreVia2/ops/systemd/lorevia-compose.service) to:
   - `/etc/systemd/system/lorevia-compose.service`
2. Make sure the repo is deployed at:
   - `/opt/lorevia/current`
3. Reload systemd:
   - `sudo systemctl daemon-reload`
4. Enable the service:
   - `sudo systemctl enable lorevia-compose.service`
5. Start it:
   - `sudo systemctl start lorevia-compose.service`

## Deploy script behavior

- `deploy.sh` installs the systemd unit from `ops/systemd/lorevia-compose.service`
- It runs `systemctl daemon-reload`
- It enables `lorevia-compose.service`
- It can be disabled by setting `ENABLE_SYSTEMD_UNIT=0`

## Coordinated Vercel and VPS release contract

The public frontend and API are separate production deployments. Read-only probes on 2026-09-06 confirmed this topology:

- `getlorevia.com` redirects to the Vercel-hosted `www.getlorevia.com` frontend.
- `api.getlorevia.com` reaches the VPS API through Cloudflare.
- The Vercel same-origin `/api/v1` rewrite reaches that API.

Treat one Git commit as the release candidate for both hosts. The release owner should complete this sequence for every production release:

1. Record the exact reviewed Git commit SHA and the currently active Vercel production deployment and VPS commit before changing either host. Confirm the VPS environment has an independent 32-128 character URL-safe `EDGE_PROXY_SECRET` (generate one with `openssl rand -hex 32`). Compose requires it for Nginx and the API; both fail closed when it is absent or malformed, and Nginx removes it from its long-lived process environment after rendering the private upstream header.
2. Confirm the Vercel project uses `frontend` as its root, the intended production branch, and the production values for `API_ORIGIN`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`, Paddle, Supabase, and observability settings. Ensure [Automatically expose System Environment Variables](https://vercel.com/docs/environment-variables/system-environment-variables) is enabled so `VERCEL_GIT_COMMIT_SHA` is present at build and runtime. Check names and presence without copying secret values into tickets or logs.
3. Build and exercise a Vercel preview from the exact release commit. Its API contract must remain compatible with the currently deployed VPS version.
4. Deploy backward-compatible API and worker changes from that same commit using `deploy.sh`. Production migration execution still requires the explicit database safeguards and authorization documented elsewhere in this repository.
5. Verify `https://api.getlorevia.com/health` and `/ready`, then promote the already-tested Vercel deployment from the same commit.
6. Run `python backend/scripts/check_public_release_boundaries.py`. It verifies the same full Git SHA from the Vercel `/api/release` endpoint and VPS `/health`, API readiness, anonymous private-page redirect, direct and same-origin API denial, trusted/untrusted CORS, no-store response policy, and required security headers. It uses unauthenticated GET and OPTIONS requests only; malformed or mismatched revisions and any boundary regression fail the check. `check_release_pair.py` remains available when only the revision comparison is needed.
7. Verify the homepage, unauthenticated private-page redirect, login, one authenticated book read, one authorized save, and one deliberately unauthorized cross-book request. Confirm the browser uses the same-origin `/api/v1` path.
8. Record the released commit, Vercel deployment identifier, completion time, and operator. Do not infer success solely from a green CI build or from one host being healthy.

If the frontend fails but the API is healthy, restore the recorded prior Vercel production deployment. If the API fails, restore the prior reviewed VPS commit only after confirming its schema compatibility; do not downgrade a database casually. When a change is not backward compatible across the two hosts, use an explicit compatibility window or feature gate instead of relying on simultaneous deployment timing.

The frontend Docker image built by CI is a build artifact; it is not evidence that Vercel is serving that image or commit. Verify the active Vercel source commit directly during release.

## Daily commands

- Check status:
  - `sudo systemctl status lorevia-compose.service`
- Restart the full stack:
  - `sudo systemctl restart lorevia-compose.service`
- Stop the full stack:
  - `sudo systemctl stop lorevia-compose.service`
- View boot/runtime logs for the unit:
  - `journalctl -u lorevia-compose.service -f`

## Container logs

Once the stack is up, use Docker for service-level logs:

- `docker compose -f docker-compose.yml logs -f nginx`
- `docker compose -f docker-compose.yml logs -f backend`
- `docker compose -f docker-compose.yml logs -f worker-extraction`
- `docker compose -f docker-compose.yml logs -f worker-analysis`
- `docker compose -f docker-compose.yml logs -f worker-embedding`
- `docker compose -f docker-compose.yml logs -f worker-intelligence`
- `docker compose -f docker-compose.yml logs -f worker-maintenance`
- `docker compose -f docker-compose.yml logs -f celery-beat`

## Advisor streaming

- Production AI streaming uses Server-Sent Events through the `nginx` service.
- The SSE proxy rule lives in [ops/nginx/nginx.conf](/C:/Users/madha/.vscode/prod/LoreVia2/ops/nginx/nginx.conf) and disables proxy buffering and gzip for every `/api/v1/intelligence/*-stream` route, including Ask LoreVia, advisor tools, and series continuity checks.
- After changing the Nginx config, redeploy or restart the edge container:
  - `docker compose -f docker-compose.yml up -d nginx`
  - or `sudo systemctl restart lorevia-compose.service`

## Worker tuning

- Production worker concurrency defaults and validation live in `backend/app/core/config.py`.
  Pydantic settings allow VPS environment overrides without changing Compose commands.
- Current recommended CCX13 baseline:
  - `EXTRACTION_WORKER_CONCURRENCY=2`
  - `ANALYSIS_WORKER_CONCURRENCY=1`
  - `INTELLIGENCE_WORKER_CONCURRENCY=1`
  - `EMBEDDING_WORKER_CONCURRENCY=1`
- Extraction is the main throughput lever for manuscript ingest because each extraction task performs chapter chunking, embeddings, LLM extraction, deduplication, and chapter persistence in one worker slot.
- Keep analysis at `1` for the first rollout so extraction gets the speedup without oversubscribing a 2 vCPU VPS.

## Throughput benchmarking

- Capture a baseline on one representative manuscript before changing worker settings.
- After changing concurrency, re-run the same manuscript and compare these log markers:
  - `ingestion_timing stage=process_book_total`
  - `ingestion_timing stage=chapter_queue_wait`
  - `ingestion_timing stage=embed`
  - `ingestion_timing stage=llm_extract`
  - `ingestion_timing stage=chapter_total`
  - `analysis_timing stage=llm`
- Example filters:
  - `docker compose -f docker-compose.yml logs worker-extraction | grep "ingestion_timing stage="`
  - `docker compose -f docker-compose.yml logs worker-analysis | grep "analysis_timing stage="`
- Treat the rollout as successful only if the same manuscript finishes materially faster without worker restart loops, OOMs, or extraction-quality regressions.

## Notes

- Keep `restart: unless-stopped` on the Compose services.
- Do not add a second supervisor for the same containers unless you are replacing systemd entirely.
- If you move the repo path, update `WorkingDirectory` in the unit file.
