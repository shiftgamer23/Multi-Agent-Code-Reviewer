# Phase 5: FastAPI Backend ✓ COMPLETE

## What We Built

Wrapped the already-working supervisor graph (Phase 4) behind HTTP
endpoints. Per the user's requested structure:

```
app/
├── api/
│   └── review.py       # the 3 endpoints
├── models/
│   └── review.py       # Pydantic request/response models
├── infra/
│   ├── store.py         # in-memory run store (Redis in Phase 7)
│   └── logging.py       # basic logging config
└── main.py               # FastAPI app, wires routers together
```

`app/cache/` and `app/observability/` (empty stubs from Phase 1) were
removed and folded into `app/infra/` per this restructure.

## The 3 Endpoints

1. **`POST /review`** — accepts `{old_file, diff_hunk, lang}`, registers a
   pending run in the store, returns `{run_id}` immediately. Does **not**
   execute the graph yet.
2. **`GET /review/{run_id}/stream`** — SSE endpoint. This is where the
   graph actually runs, via `.stream(stream_mode="updates")` instead of
   `.invoke()`.
3. **`GET /review/{run_id}`** — fetch the current/final stored result
   (works even before `/stream` is called - just shows `status: "pending"`).

## Key Design Decision: `.stream(stream_mode="updates")`

Verified directly against the installed LangGraph 1.2.11 source
(`langgraph/types.py`) before relying on it:

> `"updates"`: Emit only the node or task names and updates returned by
> the nodes or tasks after each step.

This yields `{node_name: node_output}` the instant each node finishes,
instead of `.invoke()`'s "wait for everything, return one final result."
Confirmed `.invoke()` is literally implemented as `.stream()` internally
(seen directly in a Phase 4 traceback), so this swap changes nothing about
computation, quality, or total runtime - only which intermediate outputs
we choose to observe and forward.

## End-to-End Verification (live server, real Gemini calls)

Started the server and drove it with `curl`:

- **`POST /review`** → returned a `run_id` ✓
- **`GET /review/{id}/stream`** → real SSE events observed in this order:
  ```
  event: status   {"status": "running"}
  event: style          {"style_review": "No style violations found."}
  event: test_coverage  {"test_review": "...add a corresponding test..."}
  event: security       {"security_review": "No security issues found..."}
  event: merge          {"final_review": "...synthesized comment..."}
  event: status   {"status": "complete"}
  ```
  **Notice the order**: style → test_coverage → security → merge - not
  the declaration order in the graph. This is direct evidence the 3
  specialist agents are genuinely running concurrently (whichever
  finishes first streams first), not sequentially.
- **`GET /review/{id}`** → returned the identical final state, confirming
  the store was updated correctly as each SSE event fired.
- **404 handling** → unknown `run_id` correctly returns HTTP 404.
- **Docs-only diff through the full API** → router correctly returned
  `["skip"]`, only the `skip` node fired, zero specialist LLM calls spent
  - confirms the Phase 4 routing optimization actually saves quota in the
  real HTTP path, not just in isolated tests.

## Known Simplification (intentional, not a bug)

`POST /review` only registers the run - the graph doesn't actually execute
until a client calls `GET /review/{id}/stream` and starts consuming it.
This avoids building a background task queue / worker process for what's
currently a single-user portfolio project. If multiple concurrent users or
"fire and forget" semantics are needed later, this is the seam where a
proper task queue (e.g. Celery, or FastAPI `BackgroundTasks` + the Phase 7
Redis store) would go.

## Files Created

- `app/models/review.py` — `ReviewRequest`, `ReviewCreatedResponse`, `ReviewResult`
- `app/infra/store.py` — in-memory run store
- `app/infra/logging.py` — logging setup
- `app/api/review.py` — the 3 endpoints
- `app/main.py` — FastAPI app entrypoint

## Next: Phase 6 — Evaluation Against Real Human Comments

Run every example in the locked `final_eval_slice.jsonl` (100 examples,
untouched since Phase 1) through the full pipeline, score the generated
reviews against the real human `msg` field via LLM-as-judge, and produce
real aggregate numbers - the project's key credibility metric.
