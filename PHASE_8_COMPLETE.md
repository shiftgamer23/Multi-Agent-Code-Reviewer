# Phase 8: Langfuse Observability ✓ COMPLETE

## What We Built

`app/infra/tracing.py` — deliberately optional (returns `None`/no-op
everywhere if `LANGFUSE_PUBLIC_KEY` isn't set, so the app behaves
identically with or without it configured):
- `get_langfuse_handler()` — shared `langfuse.langchain.CallbackHandler`
- `invoke_config(session_id)` — builds the LangChain `config=` dict with
  the callback attached, plus `langfuse_session_id` metadata to group
  traces
- `get_langfuse_client()` — raw client, for standalone scores not tied to
  a specific LLM call (cache hit/miss, Phase 6 eval results)

Wired `config=invoke_config(...)` into every `.invoke()`/`.stream()` call:
Style/Security/Test-Coverage agents, the supervisor graph, the merge
node's LLM call, `api/review.py`'s background task, and the eval judge.
Threaded an optional `session_id`/`run_id` parameter through
`run_style_review`, `run_security_review`, `run_test_coverage_review`,
`build_single_tool_agent`'s `run()`, and `run_full_review` so one review's
traces can be grouped.

Cache hit/miss (`app/api/review.py`) and Phase 6 eval scores
(`eval/scoring.py`'s new `log_eval_scores()`, wired into `run_eval.py`)
are logged as Langfuse scores via `create_score(..., session_id=..., data_type="CATEGORICAL"/"NUMERIC")`.

## Bugs Found and Fixed While Verifying This

1. **`LANGFUSE_BASE_URL` vs `LANGFUSE_HOST`**: the SDK only reads
   `LANGFUSE_HOST` for the endpoint URL - the env var name added to
   `.env` wasn't recognized and would have silently fallen back to the
   default cloud host. Fixed with a small compatibility shim
   (`_ensure_host_env_var()`) that copies `LANGFUSE_BASE_URL` into
   `LANGFUSE_HOST` if the latter isn't set, rather than requiring a
   rename.
2. **`langfuse==3.0.0` incompatible with `langchain==1.4.0`**: the
   bundled `CallbackHandler` imported from `langchain.callbacks.base`,
   which LangChain 1.x removed entirely (moved to `langchain_core.callbacks`).
   Upgraded to `langfuse==4.15.1`, which fixed it cleanly. Pinned in
   `requirements.txt`.
3. **`tracing.py` silently returned `None` when imported standalone**:
   it relied on some *other* module having already called `load_dotenv()`
   first (true when imported via `supervisor_graph.py`, false in
   isolation). Added its own `load_dotenv()` call, matching the pattern
   already used in `app/llm/model_config.py`.

## Verified Server-Side (not just "no exception locally")

Queried Langfuse's own REST API (`client.api.sessions.get(...)`,
`client.api.trace.get(...)`, `client.api.scores.get_many(...)`) after a
real review run:

- **One unified trace** (not 4 separate ones as originally expected) -
  because sub-agent calls happen inside nested Python function calls
  sharing the same callback handler instance, LangChain's contextvar-based
  run tracking naturally folded everything into one coherent trace tree
  instead of requiring manual parent/child wiring.
- **42 nested observations** inside that one trace: the router, each
  specialist's own internal `agent ↔ tools` loop (`style`, `security`,
  `test_coverage` as CHAIN nodes), all 3 tool calls (`check_code_style`,
  `check_code_security`, `check_test_coverage_tool`), the `merge` step,
  and all **7 `ChatGoogleGenerativeAI` generations** - exactly matching
  the expected 2-per-specialist × 3 + 1 merge = 7 LLM calls.
- **`cache_status` score** confirmed landed, correctly associated with
  its `session_id`.

This ended up being considerably richer than the "basic, not too complex"
scope originally aimed for - full nested visibility into tool calls, LLM
generations, and control flow came essentially for free from LangChain's
existing callback system once the handler was wired in, with no manual
span-management code anywhere.

## Files Created/Modified

- `app/infra/tracing.py` (new)
- `app/agents/style_agent.py`, `react_agent_factory.py`,
  `security_agent.py`, `test_coverage_agent.py`, `supervisor_graph.py`
  (added `session_id` threading + `config=invoke_config(...)`)
- `app/api/review.py` (tracing config on the background task's `.stream()`;
  `_log_cache_status()`)
- `eval/scoring.py` (`judge_review()` now traced; new `log_eval_scores()`)
- `eval/run_eval.py` (passes `run_id`/session through, calls `log_eval_scores`)
- `requirements.txt` (`langfuse==3.0.0` → `4.15.1`)

## Next: Phase 9 - Docker Deployment

`docker-compose.yml` with the FastAPI app + Redis (already running
standalone via `docker run` since Phase 7 - this formalizes it), get
everything working locally via Compose.
