# Phase 7: Redis Caching ✓ COMPLETE

## What We Built

### Infrastructure
- Redis running via Docker (`docker run -d --name code-review-redis -p 6379:6379 redis:7-alpine`)
  - Formalizes into `docker-compose.yml` in Phase 9
- `app/infra/redis_client.py` — shared connection, host/port from env vars
  (defaults to `localhost:6379`)

### Content-Addressed Diff Cache (`app/infra/cache.py`)
- Cache key = SHA-256 hash of `(lang, old_file, diff_hunk)`
- An identical diff never re-triggers the LLM pipeline - the core Phase 7
  goal from plan.md, and a direct answer to the daily-quota problem
  discovered in Phase 6
- 30-day TTL

### Run Store Moved to Redis (`app/infra/store.py`)
- Was an in-memory dict (Phase 5); now Redis-backed, so run state survives
  a server restart. Same `create_run`/`get_request`/`get_result`/
  `update_result` interface - no other code had to change.
- 7-day TTL (ephemeral run tracking, distinct from the long-lived diff cache)

### Redis Pub/Sub for Live Progress (`app/infra/pubsub.py`)
- One channel per run (`review:{run_id}:events`)
- Needed because of the architecture change below: once `POST /review`
  triggers the graph immediately via `BackgroundTasks`, `/stream` is no
  longer the thing driving execution - it has to observe a run that may
  already be in progress (or already finished) in a separate task.

### The Actual Fix: `POST /review` No Longer Waits for `/stream`

This resolves the Phase 5 known-simplification (saved in memory, now
removed since it's done): previously the graph didn't execute until a
client called `/stream`; if nobody did, the review just never happened.

Now `POST /review`:
1. Registers the run
2. Checks the diff-content cache - **hit**: marks the run complete
   immediately, zero LLM calls, publishes a `status: complete` event
3. **Miss**: kicks off a `BackgroundTasks` job that runs the graph via
   `.stream(stream_mode="updates")` right away, publishing each node's
   output to the run's Pub/Sub channel and updating the Redis-backed store
   as it goes, then caches the final result

`GET /review/{run_id}/stream` now:
- Subscribes to the run's Pub/Sub channel **before** checking stored state
  (so events published in that gap aren't missed)
- If the run already completed (cache hit, or it finished before this
  connected) - replays the final state as synthetic SSE events immediately
  instead of hanging on messages that already fired
- Otherwise, forwards live Pub/Sub messages as SSE until `status: complete`

## End-to-End Verification (live server, real Redis, real Gemini calls)

1. **`POST /review` alone, no `/stream` ever called** → `GET /review/{id}`
   showed `status: "complete"` with full review content. Confirms the
   graph now genuinely runs on submission, not on-demand.
2. **Same diff submitted a second time** → new `run_id`, but byte-for-byte
   identical review content, returned in **270ms** (vs. several seconds
   for a fresh 7-LLM-call pipeline run). Confirms the cache actually
   short-circuits the pipeline, not just returns something similar.
3. **Fresh diff, connected to `/stream` immediately after `POST`** → real
   live events arrived in non-declaration order (`security` → `style` →
   `test_coverage` → `merge`), same parallel-execution evidence as Phase 5,
   now driven by a background task instead of the request itself.
4. **Connected to `/stream` for an already-complete run** → immediate
   replay of all fields + `status: complete`, no hang.

## Known Scope Note

Redis is running as a standalone Docker container for now, started
manually (not yet part of a `docker-compose.yml` - that's Phase 9). The
app's `REDIS_HOST`/`REDIS_PORT` env vars default to `localhost:6379`, which
will need to become the compose service name once that phase lands.

## Files Created/Modified

- `app/infra/redis_client.py`, `app/infra/cache.py`, `app/infra/pubsub.py` (new)
- `app/infra/store.py` (rewritten: in-memory dict → Redis)
- `app/api/review.py` (rewritten: `BackgroundTasks` + cache-check in
  `POST /review`; `/stream` now subscribes to Pub/Sub instead of driving
  the graph itself)

## Next: Phase 8 - Langfuse Observability

Instrument each agent's run as a trace/span (tools called, timing, cache
hit/miss, token usage where available), and push the Phase 6 eval scores
into Langfuse so quality is tracked over time, not just a static number.
