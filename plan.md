# Project: Multi-Agent Code Review Assistant

## Context for Claude Code

I am building a portfolio project to learn and demonstrate agentic AI engineering skills —
specifically LangGraph orchestration, tool calling, multi-agent design, and a properly
built FastAPI backend with real infra (caching, observability, containerization). This is
part of upskilling toward Applied AI Engineer / Forward Deployed Engineer roles, so the
emphasis is on production-quality engineering, not core ML research or model training.

Please work with me iteratively, phase by phase, rather than generating everything at once.
Confirm your understanding of each phase before writing code, explain key design decisions
as you go (especially around LangGraph graph structure and tool design, since that's the
main thing I'm learning here), and don't move to the next phase until the current one is
working and I've reviewed it.

## Goal

Build a multi-agent system that reviews a code change (a diff) the way a team of human
reviewers would — each specialized agent checks one concern (style, security, test
coverage), a supervisor agent merges their findings into one coherent review — and measure
how well it performs against **real historical human reviewer comments**, not just
eyeballed output.

## Important constraints

- **No model training or fine-tuning of any kind.** Everything is achieved through
  prompting an existing LLM plus tool calling and orchestration. This is a deliberate
  choice — the target roles value applied engineering (prompting, tools, orchestration,
  infra) over ML research skills.
- **Free LLM APIs only — no paid LLM usage at any point, ever.** Primary choice: Gemini
  (Google AI Studio free tier) and/or Groq (free tier, hosts open models like Llama). The
  system should use LangChain's model abstraction so the provider is swappable via config,
  not hardcoded — this also allows falling back to a locally-run open model via Ollama for
  large eval runs if free-tier daily/rate limits become a blocker. Design for this
  multi-provider flexibility from the start rather than bolting it on later.
- **No MCP for now.** Tools should be implemented as plain Python functions with
  LangChain/LangGraph tool-calling (`@tool` decorator or equivalent), not wrapped in MCP
  servers. MCP integration is a deliberate later extension, not part of this build.
- Cache aggressively (Redis) — this isn't just a latency optimization here, it's also a
  practical way to avoid exhausting free-tier rate limits by never re-calling the LLM for
  an identical diff.

## Dataset

**Source:** CodeReviewer dataset (Microsoft Research), specifically the **Comment
Generation** task subset — downloaded from Zenodo as `Comment_Generation.zip`.

- Do NOT use `Diff_Quality_Estimation.zip` (different task — predicts whether a diff needs
  a comment at all, not the comment content), `Code_Refinement.zip` (different task — takes
  the comment as an input to predict a code fix, not as an output to generate), or
  `CodeReviewer.zip` (this is Microsoft's own model training source code, not data — not
  relevant since we're not training anything).
- After unzipping, you get three files: `msg-train.jsonl`, `msg-valid.jsonl`,
  `msg-test.jsonl`.
  - **`msg-train.jsonl` is NOT used at all** in this project (it exists for training a
    model from scratch, which we are explicitly not doing). It can be deleted/ignored.
  - **`msg-valid.jsonl`** — used during development, for iterating on prompts/agent logic
    and sanity-checking behavior. Free to look at and tune against repeatedly.
  - **`msg-test.jsonl`** — the held-out final evaluation set. Only used once the full
    pipeline is built and stable, to compute the final, honest performance numbers. Should
    not be used to tune prompts/logic (avoid overfitting to it).
- **Record structure** (each line is a JSON object):
  ```json
  {
    "old_file": "import torch",
    "diff_hunk": "@@ -1 +1,2 @@\n import torch\n +import torch.nn as nn",
    "comment": "I don't think we need to import torch.nn here."
  }
  ```
  - `old_file` — the code before the change
  - `diff_hunk` — the actual diff (in standard unified diff format)
  - `comment` — the real human reviewer's comment on this change (our ground truth)
  - Check for a `lang` field on load — if present, it can be used to filter to a
    manageable subset (e.g. Python and/or JavaScript only) for a focused first pass.
- Both `msg-test.jsonl` and `msg-valid.jsonl` are large (~260MB each, hundreds of thousands
  of lines potentially) — do not load the entire file into memory as a first step. Stream
  line-by-line, filter/slice early, and persist a small working subset (e.g. 50-100
  examples for eval, similar scale for a dev/valid slice) to a separate smaller file for
  fast iteration.

## Architecture / Phases

Work through these phases strictly in order. Do not build all agents at once — get one
agent working end-to-end first, confirm it's solid, then extend.

### Phase 1 — Environment & data setup
- Python virtual environment; install `langchain`, `langgraph`, `langchain-google-genai`
  and/or Groq's SDK, `fastapi`, `uvicorn`, `redis`, `langfuse`.
- Obtain a free Gemini and/or Groq API key; confirm a basic tool-calling round trip works
  before building any agent logic.
- Write a small script to stream-load `msg-test.jsonl`, inspect the real field structure
  (confirm `old_file` / `diff_hunk` / `comment`, check for `lang`), and produce two small
  working subsets on disk: a dev/valid slice (drawn from `msg-valid.jsonl`) and a final eval
  slice (drawn from `msg-test.jsonl`, untouched until Phase 6).

### Phase 2 — Tools (plain functions, no MCP)
- Implement 2-3 tools as plain Python functions with clear docstrings/schemas so an LLM can
  correctly decide when/how to call them:
  - A linter/style-check tool (can wrap a real linter, e.g. run `ruff`/`flake8`-style checks
    against the diff's changed code where feasible).
  - A "check if tests were added/changed" tool — simple heuristic over the diff (e.g. does
    it touch a file matching a test-file pattern).
  - Optionally a basic static security-pattern checker (e.g. flags hardcoded secrets,
    obviously unsafe patterns) — keep this simple, it doesn't need to be a full scanner.
- Test each tool independently, outside of any agent, before wiring it into LangGraph.

### Phase 3 — First agent (Style Agent)
- Build a single LangGraph agent responsible only for style/readability feedback, with
  access to the linter tool.
- Test manually against a handful of examples from the dev/valid slice — confirm it
  reliably calls the tool when appropriate and produces sensible, focused feedback (not
  trying to comment on security or tests).
- This phase is the main learning target for LangGraph + tool-calling mechanics — go slowly
  here and make sure the pattern is solid before replicating it for other agents.

### Phase 4 — Remaining agents + supervisor graph
- Add the Security Agent (uses the security-pattern tool) and Test-Coverage Agent (uses the
  test-check tool), following the same pattern established in Phase 3.
- Build the LangGraph supervisor/orchestration graph:
  - Routes to relevant agents based on the diff (e.g. skip the security agent entirely on a
    docs-only change).
  - Runs applicable agents (in parallel where the graph structure allows).
  - Merges their individual findings into a single, coherent final review comment,
    resolving redundant or overlapping findings.
- Test the full graph end-to-end on the dev/valid slice before moving on.

### Phase 5 — FastAPI backend
- Endpoints:
  - `POST /review` — submit a diff (old_file + diff_hunk), returns a review run ID.
  - `GET /review/{id}/stream` — SSE endpoint streaming each agent's reasoning/output as the
    graph executes.
  - `GET /review/{id}` — fetch the final structured review report.
- Pydantic models for request/response validation.
- Wire the already-working LangGraph pipeline behind these endpoints — this phase should be
  mostly plumbing, not new agent logic, since the core system already works from Phase 4.

### Phase 6 — Evaluation against real human comments
- Using the untouched final eval slice (from `msg-test.jsonl`), run every example through
  the full pipeline (via the FastAPI endpoints or directly).
- For each example, compare the system's final generated review against the real human
  `comment` field — score via LLM-as-judge ("does this address the same underlying issue as
  the human comment?") and/or simple overlap-based heuristics as a secondary signal.
- Produce and save real aggregate numbers (e.g. "% of test cases where the agent's review
  matched the reviewer's flagged issue") — this is the project's key credibility metric,
  equivalent to the RAG project's recall@k.
- Build this as a repeatable script, not a one-off notebook cell, so it can be re-run after
  future changes to compare against a baseline.

### Phase 7 — Redis caching
- Cache full review results keyed on a normalized hash of the diff content, so an identical
  diff never triggers a fresh (and rate-limit-consuming) LLM run.
- This serves two purposes here: normal latency/cost optimization, and — given the
  free-tier-only LLM constraint — protecting against exhausting daily/rate limits during
  development and eval runs.

### Phase 8 — Langfuse observability
- Instrument each agent's run as a trace/span: which tools were called, how long each step
  took, cache hit/miss, and (where available) token usage.
- Push eval scores from Phase 6 into Langfuse so quality can be tracked over time as changes
  are made, not just captured as a single static number.

### Phase 9 — Docker deployment
- `docker-compose.yml` with services: the FastAPI app, Redis, and (optionally) a
  self-hosted Langfuse instance.
- Get everything working locally via Docker Compose first.
- Note: if local Ollama is later added as a fallback LLM provider for larger eval runs (see
  constraints section), it can run either as an additional Compose service or directly on
  the host — decide this in Phase 9 based on whether free-tier cloud limits actually became
  a blocker during Phase 6.

## Suggested repo structure

```
code-review-agent/
├── app/
│   ├── main.py                # FastAPI app + routes
│   ├── agents/
│   │   ├── style_agent.py
│   │   ├── security_agent.py
│   │   ├── test_coverage_agent.py
│   │   └── supervisor_graph.py   # LangGraph orchestration
│   ├── tools/                 # plain function tools (linter, test-check, security-check)
│   ├── cache/                  # redis client + caching logic
│   ├── llm/                    # swappable model-provider config (Gemini / Groq / Ollama)
│   └── observability/          # langfuse instrumentation
├── data/
│   ├── raw/                    # unzipped msg-*.jsonl (msg-train.jsonl not needed)
│   └── processed/              # small dev/valid slice + final eval slice
├── eval/
│   ├── build_eval_slice.py     # carve out the held-out eval sample from msg-test.jsonl
│   └── run_eval.py             # runs pipeline over eval slice, scores vs real comments
├── docker-compose.yml
├── Dockerfile
└── README.md                   # architecture + real eval numbers, written as a design doc
```

## Scope guardrails

- Start with a small dev/valid slice (a few dozen examples) while building Phases 1-5 —
  don't work against the full dataset until the eval phase.
- Prioritize getting one agent fully correct (Phase 3) before replicating the pattern —
  resist the urge to scaffold all agents simultaneously.
- Skip: MCP integration (deliberately deferred), any model training/fine-tuning, GitHub
  webhook/live-PR integration (out of scope for this version — this build works against the
  static dataset, not live PRs).

## Immediate next step

Start with Phase 1. Confirm the environment setup, help me verify a basic Gemini/Groq
tool-calling call works, and write the data-loading/slicing script against
`msg-test.jsonl` and `msg-valid.jsonl`. Walk me through the real field structure once we
load a sample, and confirm the dev/valid and eval slices before moving to Phase 2.
