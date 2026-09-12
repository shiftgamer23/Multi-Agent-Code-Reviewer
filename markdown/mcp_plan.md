# Project: MCP Refactor for ReviewCrew (Multi-Agent Code Review Assistant)

## Context for Claude Code

I already have a working project called ReviewCrew — a multi-agent code review system
built with LangGraph, FastAPI, Redis caching, and Langfuse observability. It has three
agents (Style, Security, Test-Coverage) each using a plain Python-function tool, merged by
a supervisor graph. Full details of the original build are in `plan.md` in this repo —
please read that first for full context on the existing architecture before starting this
refactor.

This plan is a **follow-up refactor**, not a rebuild. The goal is to convert the existing
tools from plain Python functions into proper MCP (Model Context Protocol) servers, and
update the agents to call them as MCP clients instead of direct function calls — while
keeping the agents' actual review behavior/quality unchanged. This is purely an
architecture upgrade to learn and demonstrate real MCP server-building and client
integration, since I deliberately deferred MCP in the original build.

Please work with me iteratively, phase by phase. Confirm each phase works (tool calls still
produce correct behavior) before moving to the next. Explain the MCP-specific concepts as
you go (server/client roles, how tool discovery works over the protocol), since this is
new to me.

## Goal

Turn ReviewCrew's existing tools into standalone MCP servers that any MCP-compatible client
could use (not just this project), and update the LangGraph agents to consume them over the
protocol. Optionally integrate a real external MCP server (GitHub's official one) to add
genuine repo-context capability the current system doesn't have.

## What MCP is, for reference

MCP is a standard protocol that lets an AI agent (the "client") discover and call tools
exposed by a separate service (the "server"), without custom glue code per integration —
similar in spirit to how USB-C standardized device connections. A tool exposed via MCP can
be reused by any MCP-aware client, not just the one it was originally built for.

## Current state (before this refactor)

- `app/tools/` contains plain Python functions:
  - a linter/style-check tool (used by the Style Agent)
  - a test-coverage-check tool (used by the Test-Coverage Agent)
  - a security-pattern-check tool (used by the Security Agent)
- Each LangGraph agent imports and calls its tool function directly, in-process.
- No MCP involved anywhere in the current build.

## Target state (after this refactor)

- Each existing tool becomes its own standalone MCP server (a small independent process
  using the official MCP Python SDK), exposing that tool's functionality over the protocol.
- Each LangGraph agent becomes an MCP client — it connects to the relevant MCP server(s) at
  runtime and calls tools via MCP instead of a direct Python import.
- Optionally, the system also connects to GitHub's official MCP server as a genuinely
  external tool source (see Phase 5), to demonstrate consuming a real third-party MCP
  server, not just custom-built ones.
- Review quality/behavior should be functionally equivalent to before — this refactor
  changes the tool-access architecture, not the agents' reasoning or review content.

## Architecture / Phases

Work through these phases in order. Get one tool fully converted and verified before moving
to the next — do not convert all three tools simultaneously.

### Phase 1 — MCP fundamentals + environment setup
- Install the official MCP Python SDK.
- Read/summarize the core concepts needed here: how an MCP server declares its available
  tools (name, description, input schema), how a client discovers and calls them, and how
  a server is run/hosted (stdio-based local process vs. a network-accessible server) — pick
  whichever transport is most appropriate for local development first (stdio is simplest to
  start with).
- Build one trivial "hello world" MCP server with a single dummy tool, and a minimal client
  script that connects to it and calls that tool successfully, before touching any real
  ReviewCrew tool. This is a sanity check of the plumbing before real logic is involved.

### Phase 2 — Convert the linter/style tool to an MCP server
- Wrap the existing linter tool function in an MCP server, exposing it with a clear tool
  name, description, and input schema (matching what it already accepts — the diff content
  and/or changed file content).
- Write a small standalone test that connects to this server as a client and calls the tool
  directly, confirming the output matches what the original plain-function version
  produced on the same input.
- Do not touch the Style Agent yet — verify the server works in isolation first.

### Phase 3 — Update the Style Agent to use the MCP server
- Change the Style Agent's tool-calling mechanism from a direct Python function call to an
  MCP client call against the Phase 2 server.
- Re-run the same dev/valid examples used originally when the Style Agent was first built
  (see `plan.md`), and confirm behavior/output is consistent with before the refactor.
- Note any latency or behavior differences introduced by going through the protocol layer
  instead of an in-process call, and note them in the README later.

### Phase 4 — Repeat for the remaining two tools/agents
- Convert the test-coverage-check tool to an MCP server, update the Test-Coverage Agent to
  use it as an MCP client, verify against dev/valid examples.
- Convert the security-pattern-check tool to an MCP server, update the Security Agent the
  same way, verify.
- Run the full supervisor graph end-to-end afterward and confirm the merged final review
  output is consistent with pre-refactor behavior.

### Phase 5 — Optional: integrate GitHub's official MCP server
- Investigate GitHub's official MCP server (check current setup/auth requirements, as this
  may have changed since this plan was written) and connect it as an additional MCP client
  connection from the system.
- Potential real use: let an agent (or a new lightweight "context agent") pull actual
  repository context for a diff being reviewed — e.g. related file contents, existing open
  issues referencing the same file, or prior PR history — to give agents more real context
  than the current dataset-only diff/old_file fields provide.
- Treat this as a genuinely additive capability, not a required replacement for anything
  existing — the core three-agent review system should continue working correctly whether
  or not the GitHub MCP connection is available (design for graceful fallback if the GitHub
  server is unreachable or unauthenticated).
- This phase is exploratory — confirm feasibility and a minimal working integration before
  investing significant time in expanding it further.

### Phase 6 — Update infra (Docker Compose)
- Update `docker-compose.yml` so each MCP server runs as its own service/container
  (demonstrating a real multi-service topology, not a single monolith calling functions
  in-process).
- Confirm the full system (FastAPI app, all MCP tool servers, Redis, Langfuse, and
  optionally the GitHub MCP connection) runs correctly together via `docker compose up`.

### Phase 7 — Re-run eval + update README
- Re-run the existing eval script (from the original `plan.md`, Phase 6) against the same
  final eval slice used before, to confirm the MCP refactor did not degrade review quality
  compared to the pre-refactor baseline numbers.
- Update the README with:
  - A before/after architecture description (direct function calls vs. MCP-based tool
    access).
  - Why this refactor was done (learning + demonstrating real MCP server-building and
    client integration, not just consuming someone else's server).
  - If Phase 5 was completed, a note on the GitHub MCP integration and what it adds.

## Suggested structure additions

```
code-review-agent/
├── mcp_servers/
│   ├── linter_server.py           # MCP server wrapping the style/lint tool
│   ├── test_coverage_server.py    # MCP server wrapping the test-check tool
│   └── security_server.py         # MCP server wrapping the security-check tool
├── app/
│   ├── agents/                    # updated to use MCP clients instead of direct imports
│   └── mcp_clients/                # shared MCP client connection/helper logic
```

(Existing `app/tools/` plain functions can either be removed once their MCP server
counterparts are verified working, or kept internally as the actual implementation that the
MCP server wraps — i.e. the MCP server is a thin protocol layer around the same underlying
function logic. Prefer the latter: keep the tested function logic as-is, wrap it, don't
rewrite the logic itself.)

## Scope guardrails

- This is an architecture refactor, not a feature rebuild — agent reasoning, prompts, and
  the supervisor graph's merge logic should not change unless something about the MCP
  transition specifically requires it.
- Convert and verify one tool at a time — never convert all three at once.
- The GitHub MCP integration (Phase 5) is optional and exploratory — do not let it block
  completing Phases 1-4 and 6-7 first.
- Re-use the existing eval slice and dev/valid slice from the original project rather than
  building new ones — the point of Phase 7 is a direct before/after comparison.

## Immediate next step

Start with Phase 1. Confirm the MCP SDK is installed correctly, summarize the core
client/server concepts relevant to this project, and build the minimal "hello world"
server + client pair before touching any real ReviewCrew tool.
