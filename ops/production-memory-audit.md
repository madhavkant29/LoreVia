# VPS memory audit, 2026-11-09

This audit uses the supplied VPS snapshot, repository code, and disposable local Docker measurements. No production process was inspected or restarted, so there is no production before/after result. The post-reboot host reading of about 2.4 GiB used occurred **before** these changes were deployed and cannot be attributed to them.

## What the snapshot means

The supplied container figures total about 4.4 GiB. They are container memory readings, not independent Python heap sizes. A container's cgroup memory includes anonymous memory, kernel charges, and file cache. Summing RSS across prefork processes double counts shared pages; summed PSS is the better process-level comparison. The collection script below records cgroup `memory.current`, `anon`, `file`, process RSS, PSS, and private memory separately. It cannot attribute every kernel charge to one Python object.

| Service | Supplied memory | Code-supported explanation | Unverified part |
|---|---:|---|---|
| Extraction | 1,248 MiB | Two prefork children by default plus parent; previously all seven task modules were imported before fork. It also parses source files and runs NLP. | Child PSS, retained parser objects, and idle-after-work difference. |
| API | 747 MiB | One Gunicorn/Uvicorn worker by default plus master. Startup builds the entire API router, importing many routes and dependencies. | Which imports, caches, or request history dominate PSS. |
| Embedding | 610 MiB | One prefork child plus parent; previously all task modules were imported. Embedding calls use a reusable client and batches up to 250,000 tokens. | Idle import savings and peak batch memory. |
| Analysis | 602 MiB | One prefork child plus parent; previously all task modules were imported. | Proportion due to imports versus completed analysis retained by the allocator. |
| Intelligence | 596 MiB | One prefork child plus parent; previously all task modules were imported. This worker must also register a maintenance recovery task dispatched to its queue. | Actual private memory of imported modules. |
| Maintenance | 473 MiB | One prefork child plus parent; previously all task modules were imported despite its own queue. | Import and post-task retention. |
| Beat | 218 MiB | Previously configured to import every task module. All scheduled entries are maintenance tasks. | VPS saving after narrowing imports; local idle comparison is below. |
| Redis and Nginx | ~11 MiB | Small relative to Python services in the supplied snapshot. | Cache and per-process breakdown. |

Evidence: [Compose](../docker-compose.yml) defines separate workers, Beat, health checks and `unless-stopped` restarts with no memory limits or reservations. [Worker settings](../backend/app/core/config.py) default extraction concurrency to 2 and the other roles to 1. [Launcher](../backend/app/workers/worker_launcher.py) uses the Celery default prefork pool. [Celery configuration](../backend/app/workers/celery_app.py) keeps late acknowledgments, rejection on worker loss, prefetch 1, 200 tasks per child, task-specific limits and retry/visibility settings. [API startup](../backend/app/core/events.py) builds the router; [Gunicorn startup](../backend/start.sh) defaults to one web worker. [Import processing](../backend/app/services/manuscript_import_job_service.py) downloads a whole source into `raw`, accumulates chapter jobs and retains the first PDF bytes for cover work. [Embedding](../backend/app/engine/embeddings/embedder.py) truncates inputs to 8,000 characters, then batches by token count. Startup import memory was measured locally below; parsing and post-task retention were not.

## Changes made

The Celery app now defaults to importing only the maintenance task module, so Beat retains its scheduled task registration and `RequestContextTask` publishing headers. The launcher replaces this list before starting each worker with modules needed by that worker. Extraction and analysis retain both normal and priority queues. Intelligence also imports maintenance tasks because `pipeline_state_service.py` explicitly sends `repair_processing_books` to intelligence. Queue names, pool type, concurrency, prefetch, acknowledgments, retry settings, task timeouts, and schedule remain as before. The five worker health-check commands changed as described below.

## Ranked next opportunities

| Priority | Opportunity | Possible saving | Effort | Operational risk / decision |
|---|---|---|---|---|
| 1 | Role-specific startup imports (implemented) | About 224 MiB lower summed isolated cgroup anon across five local idle workers, plus about 109 MiB for Beat; **one local pair, not a VPS saving** | Low | Low after local task registration and cross-queue recovery checks; staging workload still required. |
| 2 | Extraction autoscale from minimum 1 to maximum 2, if idle intervals and queue wait allow it | Up to one extraction child's private/PSS memory; **unmeasured estimate** | Low | Medium: cold start and loss of immediate parallelism for priority work. Do not enable without load measurements. |
| 3 | Release or spool import source bytes and chapter payloads earlier | Peak and post-task saving unknown; **unmeasured estimate** | Medium/high | Medium/high: PDF cover and chapter ordering/citations must stay intact. Profile a large manuscript first. |
| 4 | Reduce embedding batch token cap from 250,000 if measured peaks warrant it | Peak saving unknown; **unmeasured estimate** | Low | Medium: more provider calls and latency/cost accounting changes. |
| 5 | Defer heavy API route imports or split service initialization | Idle saving unknown; **unmeasured estimate** | High | High: startup, OpenAPI, and request latency behavior need coverage. |

The 1 GiB goal is not established by the available evidence. Do not lower worker counts, merge queues, use a thread/eventlet pool, or impose hard Docker memory limits based on the supplied snapshot alone. Prefork provides process isolation and supports the current task limits and worker recycling. A `worker_max_memory_per_child` value needs observed per-child peaks; a limit below normal manuscript peaks would cause repeated child replacement. The existing 200-task recycling is a guardrail, not proof of a leak.

## Reproducible measurement protocol

Run on the VPS during a controlled test, with the same image, workload, worker settings, and observation windows before and after rollout. Use a sanitized synthetic or explicitly authorized manuscript. Do not run migrations, clear Redis, or restart services merely to take a memory snapshot.

1. Save the release SHA and `docker compose ps`. Record host `free -h`, `swapon --show`, and `docker stats --no-stream`.
2. After all services have been idle at least 10 minutes, run the same collector from each release directory: `(cd /path/to/old-release && bash /path/to/audit/ops/collect-memory.sh > /path/to/audit/memory-idle-before.txt)`, then the corresponding new-release command writing `memory-idle-after.txt`. Keep a copy of the read-only script outside the release checkout if the old release predates it. The script reads cgroup and `/proc` metrics; it writes only to the redirected local file.
3. Process the same small manuscript. Sample `bash ops/collect-memory.sh` every 5 seconds while it runs, then once 10 and 30 minutes after completion. The collector reads `backend/.env` for Compose interpolation; set `LOREVIA_COMPOSE_ENV_FILE` if that file is elsewhere. Repeat for a large manuscript near the supported upload boundary. Label the peak sample and the two post-task idle samples.
4. Process the same manuscript three more times through the normal reprocessing flow. Capture the idle snapshot after each run. An upward trend in cgroup `anon`, private memory or PSS after each quiet period is evidence for retention; a rise in `file` alone may be cache.
5. At each phase run `docker compose exec -T worker-extraction celery -A app.workers.celery_app inspect registered`, then repeat with `active`, `reserved`, `scheduled`, `stats`, and `active_queues` as the single final argument. Repeat against the other worker services. Confirm each task is registered on its intended consumer, including `maintenance_tasks.repair_processing_books` on intelligence. Record queue lengths with `docker compose exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli LLEN extraction'` and repeat for `extraction_priority`, `analysis`, `analysis_priority`, `embedding`, `intelligence`, and `maintenance`. Redis priority subqueues may use additional broker keys, so corroborate backlog with Celery/Flower metrics.
6. Collect `docker compose logs --since 1h worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat`. Compare `celery_task_started` queue delay, Celery task completion durations, per-minute completed tasks, retries, and any worker-lost or timeout events. Record manuscript status transitions and completion time. A smaller idle footprint is unacceptable if backlog, p95 latency, failure rate, or incomplete jobs increase materially.
7. In a disposable local environment, interrupt a long task and verify redelivery/recovery, then start a replacement worker and verify registration. Also verify a Beat maintenance tick and the intelligence-queue recovery path. Never use a production manuscript for a kill test.

Use the same script and timeline on both releases. `docker stats` may subtract cache in its displayed memory figure; compare `memory.current` and `anon` from the script for a consistent cgroup view. `smaps_rollup` is only readable for accessible processes and may omit some processes; the script prints that count. No VPS before/after values are claimed in this document.

## Rollout and rollback

Build and test the image in the local Compose environment first. Before production rollout, verify `inspect registered` on every role in a controlled deployment and confirm the maintenance recovery task on intelligence. Deploy the new image through the existing VPS release procedure only with explicit deployment authorization. Watch task registration, queue backlog, task completion, memory snapshots, and health checks for at least one large manuscript and one scheduled maintenance cycle. If registration, latency, or recovery regresses, redeploy the previous image/release SHA using the same Compose procedure; this change has no schema or data migration. Keep Redis data and in-flight tasks intact.

Recommended initial settings on the approximately 8 GB VPS: extraction concurrency 2, analysis/embedding/intelligence/maintenance concurrency 1, API web concurrency 1, prefork, prefetch 1, late acknowledgments, and the current 200-task child recycling. These are the repository defaults, not newly validated production optima. Consider extraction autoscale or concurrency 1 only after measured queue wait and peak memory justify the trade-off. Keep memory limits unset until large-manuscript peaks and recovery behavior are measured.

## Celery worker health checks

The production Compose file previously ran `celery -A app.workers.celery_app inspect ping` every 60 seconds for each worker. This starts a new Python/Celery process and imports LoreVia configuration and database code before sending the control ping. A pinned-dependency `python -X importtime` trace of this command showed `app.core.database` and SQLAlchemy imports but **no** `app.workers.tasks` imports. Thus the measured probe saving is supported by avoiding application/database startup, not by claiming all heavyweight task modules were repeatedly imported. The command was piped through `grep -q OK`, so Docker saw the shell pipeline's status rather than a structured check of the exact worker reply. The maintenance check additionally tests its export spool directory; that check is retained.

The new `app.workers.healthcheck` uses a minimal Celery app with the same broker URL and TLS verification rules, sends the same remote control ping to `worker-<role>@$HOSTNAME`, and succeeds only for `{"ok": "pong"}` from that exact destination. Missing environment, broker errors, absent replies and wrong-worker replies are unhealthy. The 60-second interval, 5-second ping timeout, 15-second Docker timeout and three retries remain unchanged. Its `python -X importtime` trace and a fresh-process regression test showed no SQLAlchemy, `app.core.database`, or task-module import. This removes application/database startup from the health subprocess while retaining a live worker responsiveness test.

Beat's separate health check only tests whether `/tmp/celerybeat-schedule` exists. It is cheap, but a hung Beat process could leave that file present and still appear healthy. This change leaves Beat's check in place; a scheduler heartbeat or last-tick metric would be needed to detect that failure mode reliably.

Local proxy profile on Windows using the repository venv pinned to Celery 5.5.0, dummy settings, a `memory://` broker and no worker reply. Each pair used the same 5-second ping timeout. Peak working set measured the base Python process directly, sampled every 10 ms through `GetProcessMemoryInfo`. These values do **not** represent VPS cgroup or PSS savings, and both commands correctly failed because no worker was present. The earlier pre-pin profile (about 111/36 MiB) is superseded by this pinned run.

| Run | Previous CLI elapsed / peak working set | Minimal ping elapsed / peak working set |
|---|---:|---:|
| 1 | 7.493 s / 103.1 MiB | 5.499 s / 37.6 MiB |
| 2 | 7.103 s / 103.1 MiB | 5.542 s / 37.6 MiB |
| 3 | 7.416 s / 102.9 MiB | 5.525 s / 37.5 MiB |

More representative local Docker profile: with a real extraction worker and Redis DB 15, `python -m scripts.profile_worker_healthcheck MODE extraction` ran three old/new pairs **inside the built worker image**. All six probes returned exit 0. The script reports child peak RSS via `resource.getrusage` and samples the worker container's cgroup memory rise every 10 ms. The cgroup delta also includes concurrent container activity and is not a persistent saving.

| Pair | Legacy elapsed / child peak RSS / cgroup rise | Light elapsed / child peak RSS / cgroup rise |
|---|---:|---:|
| 1 | 1.071 s / 105.8 MiB / 82.2 MiB | 0.379 s / 40.6 MiB / 26.4 MiB |
| 2 | 1.428 s / 105.7 MiB / 82.4 MiB | 0.340 s / 40.4 MiB / 26.8 MiB |
| 3 | 1.449 s / 105.1 MiB / 82.2 MiB | 0.400 s / 40.5 MiB / 27.5 MiB |

To profile the real VPS container at a quiet time, run the following from the release directory. It runs both probes in the extraction container and reports elapsed time, exit status, child peak RSS, and sampled cgroup memory delta. Run it before and after rollout; on an old image, run only `legacy` because the new module is absent. Other concurrent tasks can raise the cgroup delta.

```bash
for mode in legacy light; do
  docker compose exec -T -e PROBE_MODE="$mode" worker-extraction python - <<'PY'
import os
import resource
import subprocess
import time
from pathlib import Path

mode = os.environ["PROBE_MODE"]
destination = f"worker-extraction@{os.environ['HOSTNAME']}"
command = (
    ["celery", "-A", "app.workers.celery_app", "inspect", "ping", "-d", destination, "--timeout=5"]
    if mode == "legacy"
    else ["python", "-m", "app.workers.healthcheck", "extraction"]
)
memory_current = Path("/sys/fs/cgroup/memory.current")
baseline = int(memory_current.read_text()) if memory_current.exists() else 0
peak = baseline
started = time.perf_counter()
process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while process.poll() is None:
    if memory_current.exists():
        peak = max(peak, int(memory_current.read_text()))
    time.sleep(0.01)
elapsed = time.perf_counter() - started
peak_rss_mib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
print(f"mode={mode} exit={process.returncode} seconds={elapsed:.3f} child_peak_rss_mib={peak_rss_mib:.1f} cgroup_peak_delta_mib={(peak-baseline)/1048576:.1f}")
PY
done
```

Inspect Docker's recorded health-check start/end times and exit codes with `docker inspect --format '{{range .State.Health.Log}}{{.Start}} {{.End}} exit={{.ExitCode}} {{println .Output}}{{end}}' "$(docker compose ps -q worker-extraction)"`. Read `/sys/fs/cgroup/memory.events` inside the container before and after a failed check to look for a process-level `oom_kill` increment. Exit 137 means the health subprocess was killed; it does not by itself identify OOM. [Docker documents](https://docs.docker.com/reference/dockerfile/#healthcheck) that a health check exceeding its timeout is killed with `SIGKILL`, so a 15-second duration is one possible explanation. `RestartCount=0` and `OOMKilled=false` describe the container's main process and do not prove how a health subprocess died. Compare timestamps, health log output and cgroup counters before attributing a cause.

Unit tests cover the expected pong, wrong worker, missing reply, broker exception, missing settings, and TLS configuration. The opt-in Linux integration test **passed in the built worker image** against disposable Redis DB 15: it started all five real prefork worker roles, inspected registration, checked the intended-worker pong, wrong identity, wrong authentication, an unresponsive worker, stopped-worker failure, and maintenance spool success/failure. A separate Docker smoke test with the production read-only, tmpfs, dropped-capability and privilege flags observed `healthy → unhealthy → healthy` when the extraction worker was stopped and resumed; a wrong hostname returned exit 1. With disposable Redis stopped, a probe container returned exit 1 in 6.7 seconds with `OperationalError`, below Docker's 15-second health timeout. That accelerated health-state smoke used 5-second intervals and two retries to avoid a multi-minute wait; production retains 60-second intervals and three retries. CI now repeats the live test and Docker health-state check, but that workflow has not run yet. VPS profiling remains pending.

## Complete task and producer inventory

The automated registry test parses all 33 declared `@celery_app.task` names and queues, then uses Celery's real loader in a **fresh process for each role**. It asserts that every declared task is present on every worker consuming its declared queue, that Beat's 17 scheduled names are registered, and that explicit priority routing resolves to the priority queues. The role-to-import relationship is: extraction and `extraction_priority` → `extraction_tasks`; analysis and `analysis_priority` → `analysis_tasks`; embedding → `embedding_tasks`; intelligence → `intelligence_tasks`, `voice_chapter_tasks`, and `maintenance_tasks`; maintenance → `maintenance_tasks` and `export_tasks`. The extra intelligence import is required by the special recovery dispatch. Static search found no `send_task`, Celery signature, chain, group, chord, or callback producers in `backend/app`. Task modules contain no Celery signal registration; process-init/shutdown and request-context signals stay in `celery_app.py`.

| Task name (prefix shown in heading) | Producer found | Declared queue / consumer |
|---|---|---|
| **`extraction_tasks.`** `process_manuscript_import_job` | `manuscript_import_job_service` | extraction / extraction worker |
| `process_book` | durable dispatch in `task_execution_service` | extraction / extraction worker |
| `process_chapter` | durable dispatch in `task_execution_service`; priority option | extraction or `extraction_priority` / extraction worker |
| `repair_chapter_payload` | durable dispatch in `task_execution_service` | extraction / extraction worker |
| **`analysis_tasks.`** `analyse_chapter` | durable dispatch in `task_execution_service`; priority option | analysis or `analysis_priority` / analysis worker |
| **`embedding_tasks.`** `update_character_embedding` | durable dispatch in `task_execution_service` | embedding / embedding worker |
| **`intelligence_tasks.`** `refresh_world_analysis` | `world_analysis_refresh_service` | intelligence / intelligence worker |
| `generate_wiki` | no active producer found | intelligence / intelligence worker |
| `generate_advisor_reply` | advisor chat route | intelligence / intelligence worker |
| `generate_beta_reader_report` | beta reader route and `first_impression_service` | intelligence / intelligence worker |
| `generate_series_advisor_reply` | advisor jobs route | intelligence / intelligence worker |
| `generate_advisor_suggestions` | advisor suggestions route | intelligence / intelligence worker |
| `review_voice_chapter` (declared in `voice_chapter_tasks`) | voice chapter route and maintenance resume task | intelligence / intelligence worker |
| **`export_tasks.`** `process_manuscript_export_job` | `manuscript_export_service` | maintenance / maintenance worker |
| **`maintenance_tasks.`** `resume_voice_chapter_reviews` | Beat | maintenance / maintenance worker |
| `reconcile_upload_intents` | Beat | maintenance / maintenance worker |
| `cleanup_inactive_generations` | Beat | maintenance / maintenance worker |
| `backfill_reader_events` | no active producer found | maintenance / maintenance worker |
| `maintain_task_executions` | Beat; dispatches the five durable task types above | maintenance / maintenance worker |
| `release_stale_processing_reservations` | Beat | maintenance / maintenance worker |
| `repair_processing_books` | Beat and `pipeline_state_service`, which explicitly routes to intelligence | maintenance **and** intelligence / both workers register it |
| `refresh_revision_digest_notification` | `notification_service` | maintenance / maintenance worker |
| `send_due_trial_emails` | Beat | maintenance / maintenance worker |
| `send_due_subscription_emails` | Beat | maintenance / maintenance worker |
| `reconcile_paddle_subscriptions` | Beat | maintenance / maintenance worker |
| `process_beta_reads` | Beat | maintenance / maintenance worker |
| `process_data_deletion_requests` | Beat | maintenance / maintenance worker |
| `backfill_public_assets` | Beat | maintenance / maintenance worker |
| `cleanup_expired_manuscript_exports` | Beat | maintenance / maintenance worker |
| `cleanup_expired_advisor_jobs` | Beat | maintenance / maintenance worker |
| `cleanup_expired_webhook_events` | Beat | maintenance / maintenance worker |
| `cleanup_expired_subscription_events` | Beat | maintenance / maintenance worker |
| `refresh_public_rankings` | Beat | maintenance / maintenance worker |

The declared queue on `repair_processing_books` remains maintenance; the explicit intelligence queue in `pipeline_state_service` overrides it at publish time. Registration on intelligence is therefore essential. The two tasks without a current producer remain registered, preserving compatibility with manual or future sends. Registration plus routing proves the import reduction does not create an unregistered-task rejection for these known tasks. It does **not** prove that each task's full business workflow succeeds against real database, storage, and provider services.

## Fresh-process import profile

`python -m scripts.profile_celery_imports MODE` is an executable import-only comparison: `MODE=all` restores the former seven-module include list; each role mode uses the new list. Run each mode in a separate fresh process with identical safe settings, without Redis or database I/O. The following is one exploratory Windows run on pinned dependencies. Peak working set includes application/Celery imports and is neither private memory nor VPS PSS. Values across prefork children cannot be added as container savings.

| Mode | Modules / registered tasks | Startup to loader complete | Peak working set | Difference from `all` |
|---|---:|---:|---:|---:|
| Former `all` | 7 / 33 | 4.337 s | 207.1 MiB | baseline |
| Extraction | 1 / 4 | 3.822 s | 206.1 MiB | 1.0 MiB |
| Analysis | 1 / 1 | 3.806 s | 182.7 MiB | 24.4 MiB |
| Embedding | 1 / 1 | 3.332 s | 156.9 MiB | 50.2 MiB |
| Intelligence | 3 / 26 | 3.200 s | 157.3 MiB | 49.8 MiB |
| Maintenance | 2 / 20 | 1.240 s | 83.9 MiB | 123.2 MiB |

The extraction module imports almost everything in the old combined set, so its startup benefit is small in this proxy. This profile supports narrower imports for maintenance, embedding, intelligence, and analysis, but cannot establish a 1 GiB host saving. Beat's separate idle comparison follows. Ten-minute idle, post-task idle, and repeated-workload memory still need equivalent workload measurements on the VPS.

The same import-only script ran in the built Linux worker image with the pinned dependencies. Its fresh-process peak RSS and startup time from import start to loader completion were: `all` 246.4 MiB / 3.865 s; extraction 245.0 / 2.851; analysis 208.6 / 2.405; embedding 178.1 / 1.969; intelligence 179.0 / 2.044; maintenance 92.4 / 0.697. These are import-process figures, not prefork container memory.

For a stronger idle comparison, the same built image started one prefork worker at a time on empty local Redis DB 15, under the production read-only/tmpfs/capability flags and identical role queue/concurrency settings. The `old` command explicitly included all seven task modules and its startup task list contained all 33 tasks. The `new` command used `worker_launcher`. After a successful exact-name health ping and five quiet seconds, `python -m scripts.snapshot_worker_memory` recorded cgroup anonymous memory and process `smaps_rollup`. No manuscript task ran. This is one local pair per role, so repeat before treating the numbers as stable production expectations.

| Worker | Old → new cgroup anon | Old → new summed PSS | Observed anon difference |
|---|---:|---:|---:|
| Maintenance (1 child) | 217.2 → 104.9 MiB | 270.0 → 120.9 MiB | 112.3 MiB |
| Embedding (1 child) | 217.1 → 171.7 MiB | 270.8 → 203.5 MiB | 45.4 MiB |
| Analysis (1 child) | 217.3 → 198.2 MiB | 269.9 → 236.9 MiB | 19.1 MiB |
| Intelligence (1 child) | 217.3 → 172.3 MiB | 270.4 → 203.3 MiB | 45.0 MiB |
| Extraction (2 children) | 327.5 → 325.7 MiB | 381.1 → 379.2 MiB | 1.8 MiB |
| **Five-role sum of isolated anon differences** | | | **223.6 MiB** |

Beat was measured separately with the same image, no network, an in-memory broker, and an ephemeral `/tmp` schedule file. The former all-module include list was applied before `celery_app.start(['beat', ...])`; the new default used the production CLI entry. After eight quiet seconds, old → new Beat was **198.3 → 89.1 MiB cgroup anon** and **241.1 → 102.2 MiB PSS** (one process each). A real new Beat tick published `maintenance_tasks.maintain_task_executions` at the minute boundary. The two Beat entry methods differ slightly, so treat the 109.2 MiB anonymous difference as exploratory.

The five-worker-plus-Beat isolated cgroup anon differences sum to **332.8 MiB**. This is a **local idle estimate**, not a measured host or production saving: each container ran alone, PSS attribution changes when several containers run together, and the VPS may retain memory after real tasks. The original 1 GiB target is not supported by these startup measurements. The old maintenance sample's first cgroup `memory.current` reading was inflated by cold file cache; the table uses anonymous memory and PSS instead. The API was neither changed nor included.

## Verification performed and remaining gates

The supported backend dependency set was installed into `backend/.venv` with `python -m pip install -r requirements.txt`; no requirements or env file changed. Safe dummy variables were supplied **only to the test process** for host checks. Docker Desktop was initially unavailable, then started successfully. Compose Local's resolved `DATABASE_URL` pointed to `postgres/lorevia`, and `TEST_DATABASE_URL` was explicitly overridden to `postgres/lorevia_test`; the latter existed with `vector` and `pg_trgm` extensions. The test fixture owns and resets only that disposable test schema. Redis DB 15 was confirmed empty before live worker tests. No remote database, migration, production service, or manuscript data was touched.

| Check and exact command (from indicated directory) | Result |
|---|---|
| `backend: .\.venv\Scripts\python.exe -m pytest tests/unit/test_worker_launcher.py tests/unit/test_worker_healthcheck.py tests/unit/test_celery_broker_utils.py tests/unit/test_worker_task_registration.py tests/unit/test_celery_routing.py tests/unit/test_celery_task_config.py tests/unit/test_celery_runtime_config.py -q --deselect tests/unit/test_celery_runtime_config.py::test_worker_process_init_detaches_parent_database_pool --deselect tests/unit/test_celery_runtime_config.py::test_worker_shutdown_disposes_database_even_if_redis_cleanup_fails` | **44 passed, 2 deselected** in 26.50 s. Includes fresh-process registration of all roles, Beat, priority routing, mocked health failures, and the lightweight-import boundary. |
| `backend: .\.venv\Scripts\python.exe -m pytest tests/integration/test_celery_worker_health_live.py -q` | **1 skipped**, as designed on Windows without `RUN_CELERY_LIVE_TESTS=1`. |
| `backend: .\.venv\Scripts\python.exe -m pytest tests/unit/test_extraction_tasks.py tests/unit/test_intelligence_worker_tasks.py tests/unit/test_chapter_recovery_service.py tests/unit/test_story_health_runtime.py -q -x -o faulthandler_timeout=15` | **Interrupted**, not counted as passed. It hung in Windows `asyncio.new_event_loop()` → `socket.socketpair()` before the test's database mock. The same sandbox behavior blocked the two deselected runtime tests. |
| `repo: docker compose -f docker-compose-local.yml run --rm --no-deps -e RUN_CELERY_LIVE_TESTS=1 -e CELERY_LIVE_BROKER_URL worker-extraction python -m pytest tests/integration/test_celery_worker_health_live.py -v` | **1 passed** in 113.49 s in the built Linux worker image. `CELERY_LIVE_BROKER_URL` was the Compose Local Redis URL with only `/0` changed to `/15`. It exercised all five real prefork roles, registration, ping and failure cases. Two diagnostic attempts failed first: Celery's environment broker precedence sent the test controller to DB 0, then `inspect registered` rate-limit annotations broke bare-name comparison. Both test defects were fixed; the worker startup registry contained the expected tasks. |
| `repo: docker compose -f docker-compose-local.yml run --rm --no-deps -e TEST_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lorevia_test worker-extraction python -m pytest tests/unit/test_celery_runtime_config.py tests/unit/test_extraction_tasks.py tests/unit/test_intelligence_worker_tasks.py tests/unit/test_chapter_recovery_service.py tests/unit/test_story_health_runtime.py tests/integration/test_story_health_api.py -q -x` | **47 passed** in 9.61 s, including the two Windows-blocked runtime tests and a FastAPI endpoint. |
| Same worker-image `pytest tests -q --maxfail=10` with the disposable test database and live test enabled | **10 failed, 178 passed** before the cap. Several tests wrote `/app/local`, which is not owned by the non-root user in the worker image. This is a test-image mismatch; the API image owns `/app`. |
| `repo: docker compose -f docker-compose-local.yml run --rm --no-deps -e TEST_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lorevia_test api python -m pytest tests/integration/test_admin.py::test_admin_can_create_and_append_public_demo_books_only_through_admin_routes tests/integration/test_books.py::test_large_export_prepare_creates_private_durable_job tests/integration/test_continuity_api.py::test_continuity_scan_workflow_returns_cited_finding_and_records_decision tests/integration/test_continuity_api.py::test_clean_scan_becomes_stale_after_a_covered_chapter_edit tests/integration/test_empty_project.py tests/integration/test_ingestion_pipeline.py::test_upload_pipeline_stages_and_processes_multiple_chapters tests/integration/test_ingestion_pipeline.py::test_process_book_persists_isbn_and_copyright_warning -q --tb=short --show-capture=no --maxfail=10` | **15 passed** in 11.95 s in the intended API image. |
| `repo: docker compose -f docker-compose-local.yml run --rm --no-deps -e TEST_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/lorevia_test -e RUN_CELERY_LIVE_TESTS=1 -e CELERY_LIVE_BROKER_URL api python -m pytest tests -q --tb=short --show-capture=no --maxfail=10` | **3,329 passed, 1 skipped** in 188.43 s. Same isolated DB 15 broker override as the standalone live test. The one skip is an existing test environment condition; no failure remained. |
| Docker health-state smoke in the built worker image with production read-only, tmpfs, dropped capabilities and privilege flags | **Passed**: exact worker probe returned 0; wrong hostname returned 1; Docker reported `healthy → unhealthy → healthy` across `SIGSTOP`/`SIGCONT`. The CI image smoke step now checks the same transitions. |
| `backend: .\.venv\Scripts\python.exe -c "from app.main import app; print(len(app.routes))"` with the dummy env | Passed import smoke; six top-level routes. It does not exercise FastAPI endpoints. |
| `backend: .\.venv\Scripts\python.exe scripts/check_production_service_contract.py` | Passed. |
| `repo: docker compose -f docker-compose.yml config --quiet` with dummy `EDGE_PROXY_SECRET` | Passed syntax/config rendering; no container started. |
| `backend: .\.venv\Scripts\python.exe -m ruff check` and `-m ruff format --check` on changed Python files | Passed after import-order fix. |
| `repo: git diff --check` and PyYAML parse of `.github/workflows/ci-cd.yml` | Passed; Git emitted only its CRLF conversion notice. |
| `repo: C:\Program Files\Git\bin\bash.exe -n ops/collect-memory.sh` outside the Windows sandbox | Passed. The extracted CI worker-smoke shell block also passed `bash -n` after GitHub expressions were substituted. |
| `repo: docker info` | Initially unavailable; Docker Desktop then started and the local daemon reported version 26.0.0. |

For reproducibility, set the dummy variables in the current PowerShell process before the commands above: `$env:DEPLOYMENT_ENV='test'; $env:DEBUG='true'; $env:DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/lorevia_test'; $env:REDIS_URL='redis://127.0.0.1:6379/0'; $env:S3_BUCKET='test-bucket'; $env:AWS_ACCESS_KEY_ID='test-key'; $env:AWS_SECRET_ACCESS_KEY='test-secret'; $env:OPENAI_API_KEY='test-key'; $env:JWT_SECRET='test-secret-key-for-ci'; $env:RESEND_API_KEY='test-key'; $env:SECRET_KEY='test-secret-key-for-ci'; $env:SENTRY_DSN=''`. These values are never written to `.env` files. For import-only profiling, additionally set `REDIS_URL` and `CELERY_BROKER_URL` to `memory://` and run `python -m scripts.profile_celery_imports all`, then each role in a fresh command.

The complete Docker-based suite and live worker test passed locally. The newly edited CI workflow itself has not run and remains a release gate. For another machine, resolve the Compose Local broker URL and set `CELERY_LIVE_BROKER_URL` to the same URL with Redis database `/15`, after verifying that DB 15 is disposable; run the exact Docker commands above. A representative small/large manuscript workload, interrupted in-flight task recovery, Beat operation in staging, post-task memory retention, throughput, and VPS before/after collection remain separate gates. The local Beat tick passed with an in-memory broker. Any CI failure must be resolved before rollout.

## Reliability and optimization decisions

The import and probe changes do not alter `task_acks_late`, `task_reject_on_worker_lost`, prefetch 1, worker child recycling at 200 tasks, retries, task time limits, queue names, producer payloads, transaction boundaries, task outbox, or LLM spending guards. The code inspection covered `task_execution_service`'s durable five-task dispatch, import/export job dispatch, priority paths, `repair_processing_books`' intelligence override, maintenance Beat schedule, and `deploy.sh`'s health gates. The full backend suite and live prefork registration/health tests passed. An in-flight task kill and representative end-to-end workload are still needed to validate recovery and idempotency under operational conditions. No schema change or migration was made. Existing `unless-stopped` restart policies remain. Docker memory limits/reservations remain unset because a normal large-task peak is unknown.

`deploy.sh` refuses a dirty checkout, requires an explicit remote Alembic URL/confirmation, takes a database backup by default, checks one head and schema compatibility, runs a read-only data preflight, records the legacy freeze cutoff, and waits for all runtime services to become healthy. It also stops services and may run a migration, so its existing review and authorization gates must be respected. The memory change itself needs no database migration or legacy cutoff rewrite. The health probe's new exact-name match can report an intentionally renamed worker unhealthy; the image smoke test checks the Compose-style hostname. Transient Redis failure or a busy worker may still produce a missed ping; Docker requires three failed 60-second checks before marking the container unhealthy. A health-check exit 137 remains **unattributed** without a matching health-log duration and cgroup `oom_kill` counter change. `RestartCount=0`, `OOMKilled=false`, and absent kernel OOM logs do not establish the subprocess cause.

The following were considered but not changed: extraction autoscale or concurrency 1 (unknown queue delay and priority-work latency), a different pool (would change task isolation and time-limit semantics), `worker_max_memory_per_child` or hard cgroup limits (unknown normal manuscript peak), smaller embedding batches (provider latency/cost unknown), and early disposal of whole-document/PDF buffers (cover extraction and chapter order need workload tests). HTTP/embedding clients have existing per-process lifecycle cleanup; SQLAlchemy engine disposal is wired to worker child init/shutdown. These are code findings, not proof of no retained memory. Beat's file-existence probe cannot detect a stalled scheduler; a last-tick heartbeat would need a durable, validated signal and an actual Beat failure test, so it was not replaced with another potentially misleading check.

## Changed-file inventory

| File | Purpose |
|---|---|
| `backend/app/workers/celery_app.py` | Narrow Beat's default task include and share Redis URL normalization. |
| `backend/app/workers/worker_launcher.py` | Load task modules for the actual role, preserving both priority queues and intelligence recovery. |
| `backend/app/utils/celery_broker_utils.py` | Share the broker/TLS normalization without importing the application from the health subprocess. |
| `backend/app/workers/healthcheck.py` | Minimal exact-worker Celery remote-control ping. |
| `docker-compose.yml` | Use the minimal probe for all five workers; keep the maintenance spool test. |
| `backend/tests/unit/test_worker_launcher.py` | Assert role arguments, module lists, Beat list, and recovery registration. |
| `backend/tests/unit/test_celery_broker_utils.py` | Cover plain Redis and TLS normalization. |
| `backend/tests/unit/test_worker_healthcheck.py` | Cover success, missing/wrong replies, broker errors, env errors, and TLS. |
| `backend/tests/unit/test_worker_task_registration.py` | Parse all declarations and verify real fresh-process registration, routing and Beat. |
| `backend/tests/integration/test_celery_worker_health_live.py` | Opt-in Linux live Redis/worker success and failure checks. |
| `.github/workflows/ci-cd.yml` | Run the Linux test in CI and boot the actual worker image for a smoke check. |
| `backend/scripts/profile_celery_imports.py` | Reproducible fresh-process import profile. |
| `backend/scripts/profile_worker_healthcheck.py` | Reproducible old/new probe time, RSS and cgroup-peak comparison in Linux. |
| `backend/scripts/snapshot_worker_memory.py` | Read-only idle cgroup and process RSS/PSS/private-memory snapshot inside a worker. |
| `ops/collect-memory.sh` | Read-only cgroup/process/host memory and OOM-event collection. |
| `ops/production-memory-audit.md` | Evidence, methodology, risks, rollout and verdict. |

## Staging, production rollout, and rollback procedure

**Gate first:** the local Linux backend suite, live worker test and built-image Docker health smoke passed. The edited GitHub Actions workflow must still pass on its runner. Before a production rollout, run a representative staging manuscript/reprocessing workload with a controlled interrupted task. Require healthy registrations for all 33 tasks, both priority queues, the intelligence recovery task, one Beat tick, successful import/export and no stuck manuscripts after interruption. Compare queue wait, throughput, retries and peak memory against the same workload on the previous image. Do not proceed on an untested CI change or a failed gate.

For a subsequently authorized VPS rollout, collect the before snapshots with the same read-only collector using the release-directory command above and the workload procedure above. Save `git rev-parse HEAD`, `docker compose ps`, current worker image IDs, and the previous clean release SHA. Use the existing approved release process and its database/legacy safeguards for a normal release. If deploying only this no-schema worker change, the following targeted sequence avoids changing the API, Redis, schema or data; run it only after explicit deployment authorization:

```bash
export RELEASE_SHA="$(git rev-parse HEAD)"
dc=(docker compose --env-file backend/.env -f docker-compose.yml)
"${dc[@]}" build --pull worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat
# Inspect active/reserved tasks and wait for the selected role to drain before each stop.
for service in worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat; do
  "${dc[@]}" stop --timeout 1800 "$service"
  "${dc[@]}" up -d --no-deps --wait "$service"
  "${dc[@]}" ps "$service"
done
```

Before stopping each role, check `celery -A app.workers.celery_app inspect active` and `reserved` from that service and confirm it is drained; if it cannot drain within its task budget, stop the rollout and investigate. The targeted procedure is **not** a substitute for the normal migration/legacy preflight when a release contains other application or schema changes. Never set a remote `ALEMBIC_DATABASE_URL` for this profiling work or run a migration as part of this no-schema change. Preserve Redis and the export spool. After each role starts, run `"${dc[@]}" exec -T "$service" python -m app.workers.healthcheck "${service#worker-}"` for worker services and inspect `registered` plus `active_queues`; check the maintenance spool and Beat's schedule file. Then run one small and one large authorized test manuscript and one repeated processing run. Record cgroup `memory.current`, `anon`, `file`, PSS, host MemAvailable, task latency, backlog, health-log duration, and `memory.events` before/after with the same observation windows. Accept the optimization only if correctness and latency remain acceptable; calculate actual GiB saved from equivalent idle snapshots, rather than adding the Windows process differences.

If registration, health, recovery, backlog, or manuscript status regresses, halt the rollout. Restore the saved previous clean release SHA in the release checkout, rebuild the same worker/Beat services from that revision and restart them one at a time after checking/draining active work using the sequence above. Confirm all worker names and queues, Beat schedule, API readiness, and task completion. No database downgrade or Redis flush is part of this rollback; the code changes add no schema or data migration. If the release includes unrelated migrations or legacy operations, use that release's separately reviewed rollback plan before changing the checkout.

## Requirement checklist and readiness

| Requirement | Status / evidence |
|---|---|
| Inspect VPS/Compose/Celery/Gunicorn architecture, imports, queues, restart policy and memory semantics | **Complete at code level**; supplied snapshot is not an idle/post-task profile. |
| Implement reversible worker import and genuine responsive-worker health optimizations | **Complete in code**; exact worker pong retained and spool check preserved. |
| Enumerate and test every declared task, Beat entry, priority queue and special recovery route | **Complete locally for registration/routing**; 33 tasks, 17 Beat names, 44 focused tests passed. |
| Validate real worker registration and responsiveness, broker failures, stopped/unresponsive worker, and actual worker image | **Complete locally**; all five real prefork roles passed the live test, and Docker health transitions passed under production hardening flags. CI rerun pending. |
| Run full backend/FastAPI/manuscript/retry/rollback regression tests | **Complete locally**; 3,329 passed and one existing skip in the intended API image. Representative staging workload and in-flight kill/recovery remain. |
| Measure health-check time and peak memory on pinned dependencies | **Complete locally** for both Windows no-reply proxy and real Linux worker; old about 105 MiB/1.1–1.4 s versus new about 40 MiB/0.34–0.40 s in the worker image. |
| Compare old all-task and new role-specific idle worker/Beat memory | **Complete for one local pair per role**; summed isolated cgroup anon difference 223.6 MiB for workers and 109.2 MiB for Beat. Repeat and production comparison pending. |
| Verify a real Beat maintenance tick | **Complete locally**; `maintenance_tasks.maintain_task_executions` was published using an in-memory broker with no network. |
| Measure true VPS idle, startup, task peak, retained memory, throughput and host memory before/after | **Incomplete**; read-only collector and equivalent-workload protocol supplied. |
| Investigate further optimizations without reducing reliability | **Complete at code-review level**; concurrency, autoscale, batching, parsing and limits deferred pending workload evidence. |
| Verify production rollout and rollback safeguards | **Complete at code-review level**; no deployment or migration executed. |
| Attribute the prior health-check exit 137 | **Unresolved**; logs/cgroup evidence is insufficient to distinguish timeout, manual kill, or another cause. |

**Verdict: READY FOR STAGING.** All locally executable backend tests and live image/health checks pass, a real Beat tick published, and no known registration or health correctness blocker remains. The edited CI workflow, staging workload and in-flight recovery gate, and equivalent VPS before/after memory collection still need to pass before production. The approximately 1 GiB production saving is unverified; the measured worker-plus-Beat local idle difference was about 333 MiB of isolated cgroup anonymous memory.
