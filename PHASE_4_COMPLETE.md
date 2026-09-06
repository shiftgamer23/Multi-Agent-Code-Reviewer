# Phase 4: Remaining Agents + Supervisor Graph ✓ COMPLETE

## What We Built

### 1. Two More Specialist Agents (same ReAct pattern as Phase 3)

Rather than copy-pasting Style Agent's ~40 lines of `StateGraph` wiring
twice more, extracted the shared shape into a factory:

- **`app/agents/react_agent_factory.py`** — `build_single_tool_agent(system_prompt, tool_fn)`
  builds the identical `agent ↔ tools` graph from Phase 3 and returns a
  plain `run(prompt) -> str` function. Includes the same `extract_text()`
  content-block fix discovered in Phase 3.
- **`app/agents/security_agent.py`** — bound to `scan_security`, restricted
  to security anti-patterns only (hardcoded secrets, SQL injection,
  dangerous functions, weak crypto).
- **`app/agents/test_coverage_agent.py`** — bound to `check_test_coverage`,
  restricted to whether tests were added/updated only.

`style_agent.py` itself was left untouched (its own hand-written graph) —
already reviewed in Phase 3, and kept as the explicit "here's how LangGraph
mechanics work" reference.

**Verified** (`test_security_and_test_agents.py`) against real dev-slice
examples: both agents correctly stayed in-lane and produced diff-specific
(not templated) feedback backed by real tool output — e.g. Test-Coverage
Agent named the exact exception path (`COMError`) missing test coverage,
which only comes from reading the actual diff via its tool, not a generic
template.

### 2. Router (`app/agents/router.py`)

Plain Python, no LLM call — decides which agents are relevant *before* any
agent runs:
- Unsupported language (not in `{py, js, java, ts}`) → skip everything
- Docs-only diff (every touched file matches `.md`/`.rst`/`.txt`/`LICENSE`/etc.,
  reusing `extract_filenames_from_diff()` from Phase 2's test detector) →
  skip everything
- Otherwise → run all three specialists

**Verified** (`test_router.py`) against 4 cases including an edge case
(file patterns disagree with the `lang` tag — file patterns win).

### 3. Supervisor Graph (`app/agents/supervisor_graph.py`)

```
START -> route() -> fan out to [style, security, test_coverage] (parallel)
                  -> merge -> END
                  -> skip -> END   (unsupported lang / docs-only)
```

Key mechanics:
- **Conditional entry point returning a list** (`set_conditional_entry_point`
  with a path function returning `Sequence[Hashable]`) fans out to multiple
  nodes in parallel — verified against the installed LangGraph 1.2.11
  source before relying on it, rather than assumed.
- **Fan-in**: `merge` has static edges from all three specialist nodes;
  LangGraph only waits for whichever branches the router actually
  triggered in a given run, not all three unconditionally.
- **`merge` node**: the one new LLM call this graph adds — takes whichever
  specialist reviews ran and synthesizes them into one coherent PR comment,
  deduplicating overlapping points and ordering by importance.

**Verified** (`test_supervisor_graph.py`) end-to-end: fan-out, parallel
execution, fan-in, and merge all confirmed working — e.g. one merged
review correctly folded a test-coverage gap and a style nit into one
concise paragraph while dropping the redundant "no security issues"
mention, exactly as instructed in the merge prompt.

## Real Constraint Found: Gemini Free-Tier Rate Limit

Each full supervisor run costs ~7 LLM calls (2 per specialist × 3 + 1
merge). Because the 3 specialist branches run **concurrently** (LangGraph's
thread-pool execution of parallel graph branches), their calls land in
tight bursts — occasionally exceeding Gemini's 15 requests/minute free-tier
quota (`429 RESOURCE_EXHAUSTED`).

**Confirmed as a true rate-limit** (not a logic bug) by re-running the
identical test twice in a row: it failed once, then passed fully on
immediate retry with no code changes — the classic signature of a timing-
dependent quota rather than a deterministic error.

**Not fixed now** — this is exactly what Phase 7 (Redis caching) exists to
solve (cache full review results so repeated/eval runs don't re-burn
quota). Adding retry/backoff logic now would be premature infra work for a
problem with a proper fix already scheduled. For now: test manually with
1-2 examples at a time.

## Files Created

- `app/agents/react_agent_factory.py` — shared single-tool ReAct graph builder
- `app/agents/security_agent.py`
- `app/agents/test_coverage_agent.py`
- `app/agents/router.py` — plain-Python routing heuristic
- `app/agents/supervisor_graph.py` — full pipeline
- `test_security_and_test_agents.py`
- `test_router.py`
- `test_supervisor_graph.py`

## Next: Phase 5 — FastAPI Backend

Wrap `run_full_review()` behind HTTP endpoints. Mostly plumbing at this
point — the core multi-agent system already works end-to-end.
