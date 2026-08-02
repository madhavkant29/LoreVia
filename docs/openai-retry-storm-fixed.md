# OpenAI Retry Storm: Incident and Fix

Status: Fixed
Verified: July 26, 2026

## Bottom line

The most likely cause was a **retry storm**: one temporary OpenAI connection failure caused the same paid work to be attempted repeatedly at several different layers.

A retry storm means "an error causes retries, and each retry mechanism triggers another retry mechanism." Instead of one failed request becoming two or three attempts, it can multiply into dozens.

The Sentry errors and the old code strongly support this explanation. However, only OpenAI's usage report can prove exactly which requests consumed the missing balance.

## What happened step by step

### 1. LoreVia sent several OpenAI requests for a chapter

Processing one chapter is not necessarily one API request. LoreVia may need to:

- Generate embeddings for multiple text batches.
- Extract characters and relationships from multiple batches.
- Generate summaries.
- Identify plot threads.
- Perform fallback extraction if the normal extraction result is unusable.

An **embedding** is a numerical representation of text used for similarity search. Creating one is an OpenAI API call and therefore costs money.

The chapter processor can run some batches concurrently. "Concurrently" means several operations are in progress at the same time.

### 2. The connection was interrupted

Sentry recorded errors such as `APIConnectionError` and remote disconnects.

A connection error does not always mean OpenAI did no work. This sequence is possible:

1. LoreVia sends a request.
2. OpenAI receives and processes it.
3. The connection drops before LoreVia receives the response.
4. LoreVia sees an error, even though OpenAI may have already charged for processing it.

From LoreVia's point of view, the result is unknown. It cannot safely tell whether the provider processed nothing, processed part of it, or completed everything before the response was lost.

### 3. The OpenAI SDK retried

The **SDK** is OpenAI's official Python library used to send requests.

It had its own automatic retries enabled. With the default configuration, one application call could result in as many as three network attempts: the original attempt plus two retries.

### 4. LoreVia's retry wrapper retried the SDK operation

LoreVia also used Tenacity, a Python retry library, around the same call.

It allowed three call-level attempts. Because each Tenacity attempt invoked an SDK that could retry internally, the layers multiplied:

```text
3 application attempts × 3 SDK attempts = up to 9 network attempts
```

These were not necessarily all charged, but each represented another possible paid request.

### 5. Celery replayed the entire chapter

**Celery** is the background-job system that processes chapters outside the web request.

The chapter task had `max_retries=3`. In Celery, that means the initial execution plus as many as three additional executions.

If the task failed near the end, Celery did not know which earlier stages had succeeded. It restarted the whole chapter workflow, potentially repeating:

- Embeddings that had succeeded.
- Character extraction that had succeeded.
- Other completed batches.
- Summary or analysis calls.
- Database operations.

The approximate worst-case multiplier for one provider operation was therefore:

```text
3 SDK attempts
× 3 call-level attempts
× 4 whole-task executions
= up to 36 attempts
```

Chapter batching and fallback calls could increase the total further. This does not mean exactly 36 requests were charged; it demonstrates why the old design could turn a short outage into unexpectedly high spending.

### 6. The fallback could make another paid call

When character extraction failed, the code sometimes called `fallback_character_mentions`.

A fallback is a second method used when the normal method fails.

The problem was that some failures were connection or provider failures—not bad extraction results. Calling another provider-backed fallback after a provider failure could spend money again without fixing the underlying connection problem.

### 7. Database-session errors made the situation worse

Sentry also recorded:

- `InvalidRequestError`
- `IllegalStateChangeError`
- `PendingRollbackError`
- Warnings about database connections being cleaned up unexpectedly

A SQLAlchemy `AsyncSession` represents an active database conversation and transaction. A **transaction** is a group of database changes that should succeed or fail together.

The same session could be associated with parallel work, or sibling asynchronous operations could remain alive after the first one failed. SQLAlchemy sessions are not designed to perform multiple overlapping operations this way.

There was another subtle issue with `asyncio.gather`, the Python feature used to wait for parallel operations:

1. Several embedding operations started.
2. One failed.
3. `gather` reported that first error immediately.
4. Some sibling operations could still be running.
5. The caller began closing or rolling back the database session.
6. A surviving sibling attempted to use related state while cleanup was occurring.

That produced the "session is provisioning a connection," "close already in progress," and "pending rollback" errors. Those database errors then reached Celery, which interpreted some as retryable and replayed the task again.

The database issue was therefore both a bug and a retry-storm amplifier.

## How it was fixed

| Old behaviour | New behaviour |
|---|---|
| SDK and application both retried the same call | Explicit call-level retry is the only retry owner on those paths |
| Celery replayed complete chapters after provider work | Celery retries only before paid work starts |
| Provider failure could invoke another provider fallback | Provider/control failures stop immediately |
| Parallel operations could share chapter-session state | Provider usage tracking uses independent short sessions |
| First failed embedding left siblings running | Siblings are cancelled and fully drained |
| Capacity or token-limit errors retried the task | Work is paused for later resumption |
| Advisor and character-embedding workers still replayed paid work | The second audit added the same phase protection to those workers |

### One bounded retry owner

Where LoreVia has an explicit call-level retry policy, the OpenAI client now uses `max_retries=0`.

That does not mean there are no retries. It means LoreVia owns them in one visible place:

- Maximum of three attempts.
- Only temporary errors are retried.
- Exponential delay between attempts.

An **exponential delay** means each wait is longer than the previous wait. This prevents the application from repeatedly hammering a struggling provider.

The relevant changes are in [`llm.py`](../backend/app/core/llm.py) and [`embedder.py`](../backend/app/engine/embeddings/embedder.py).

### No whole-task replay after paid work begins

The workers now track whether provider-backed work has started:

- `chapter_work_started`
- `analysis_work_started`
- `advisor_work_started`
- `embedding_work_started`

The behaviour is now:

```text
Failure before paid work starts
    → safe infrastructure retry is allowed

Failure after paid work starts
    → record the failure
    → do not replay the whole job
```

For example, if the database is temporarily unavailable while loading a chapter, retrying is safe because no OpenAI request has happened.

If an embedding has already started and the database later fails, the task is not replayed because doing so could purchase the same embedding again.

This protection applies to:

- [Chapter extraction](../backend/app/workers/tasks/extraction_tasks.py)
- [Chapter analysis](../backend/app/workers/tasks/analysis_tasks.py)
- [Advisor replies and scans](../backend/app/workers/tasks/intelligence_tasks.py)
- [Character embeddings](../backend/app/workers/tasks/embedding_tasks.py)

### Capacity and usage limits now pause work

If LoreVia's token allowance is exhausted or its internal OpenAI capacity is busy, the task is marked as paused instead of being repeatedly executed.

A paused task keeps its reason, such as:

- `llm_usage_limit`
- `llm_capacity`

This makes the work resumable without continuously spending money or filling the error logs.

### Provider failures no longer trigger provider fallback

Character extraction now distinguishes between:

- A parsing or result-quality failure, where fallback may help.
- A provider, network, timeout, usage-limit, or capacity failure, where another paid call is inappropriate.

Provider failures are propagated directly after all concurrent batches settle. The fallback remains available for genuine extraction or formatting problems.

This is implemented in [`extraction_chapter_llm_service.py`](../backend/app/services/extraction_chapter_llm_service.py).

### Parallel embedding cleanup is deterministic

Each embedding operation now uses independent provider-usage tracking rather than the chapter's shared database session.

If one parallel embedding fails:

1. All sibling tasks are cancelled.
2. LoreVia waits for every sibling to finish cancellation.
3. Only then does the error return to the chapter processor.
4. The chapter database session can safely roll back or close.

That prevents background coroutines from touching state after session cleanup begins. The fix is in [`extraction_chapter_embedding_service.py`](../backend/app/services/extraction_chapter_embedding_service.py).

### Concurrency was limited

Extraction batches now use a configured concurrency limit rather than starting every possible provider call simultaneously.

This reduces:

- Sudden API request spikes.
- OpenAI rate-limit errors.
- Database pressure.
- The number of calls affected by one network incident.

## What happens now during the same failure

If an embedding connection drops today:

1. That embedding call may retry up to the bounded call-level limit.
2. The SDK does not secretly multiply those retries.
3. Other parallel embedding operations are cancelled and drained if necessary.
4. The database session is closed safely.
5. Celery does not replay the entire chapter after provider work has started.
6. The chapter remains incomplete instead of being incorrectly marked successful.
7. It can later be deliberately resumed or reprocessed.

There is still a small unavoidable uncertainty: if OpenAI completes a request but the response is lost, a call-level retry might purchase the request again. Client code cannot always distinguish that situation from a request OpenAI never received. The important change is that this risk is now strictly bounded and cannot multiply through complete task replays.

## Verification performed

After both audit passes:

- 93 focused unit tests passed.
- 16 ingestion integration tests passed.
- Tests cover both sides of the boundary:
  - Failures before paid work still retry.
  - Failures after paid work do not replay.
- Ruff static checks passed.
- Git diff validation passed.
- The local API started successfully and remained healthy on port 8000.
- No environment or secret files were modified.
- No migrations were run.
- Application database data was not altered.
- Existing unrelated worktree changes were preserved.

The fix does not merely catch the specific Sentry exception. It changes the workflow's retry structure so that a temporary OpenAI or database failure cannot again multiply into an uncontrolled sequence of paid chapter executions.
