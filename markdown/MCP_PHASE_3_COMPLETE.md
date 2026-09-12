# MCP Phase 3: Style Agent → MCP Client ✓ COMPLETE

## What We Built

- `app/mcp_clients/bridge.py` — the hand-rolled bridge decided in Phase 1:
  `call_mcp_tool(server_script, tool_name, **kwargs)` spawns the target
  MCP server fresh, opens a `ClientSession` over stdio, calls the tool,
  and returns its text result as a plain string. Synchronous entry point
  (`asyncio.run()` internally) so it drops straight into LangGraph's sync
  node functions with no ripple-through changes elsewhere.
- `app/agents/style_agent.py`'s `check_code_style` tool: **only its body
  changed** - same `@tool` decorator, same signature, same docstring. It
  now calls `call_mcp_tool(...)` against `linter_server.py` instead of
  `check_style()` directly. The language-unsupported reduction logic that
  used to live here moved server-side in Phase 2, so it's gone from this
  file entirely - one less thing duplicated between client and server.

## Verified Two Ways

**1. Isolated tool call (no LLM)** — `check_code_style.invoke(...)`
produces the identical output to Phase 2's direct comparison, confirming
the wiring is correct before spending any LLM calls on it.

**2. Full agent, real LLM, same dev/valid examples as the original
build's Phase 3** — all three examples reproduce the *exact* original
findings:
- Example 1 (scapy): "No style violations found" - unchanged
- Example 2 (nvda): **caught the same real trailing-whitespace issue** as
  the original in-process version - this is the important one, since it
  proves the tool call is genuinely happening over MCP and its real
  output is driving the LLM's answer, not a coincidentally-similar
  hallucination
- Example 3 (kinto): "clean... no issues found" - unchanged

## Measured Latency Difference (the plan explicitly asked for this)

Isolated the tool-call overhead itself (not agent latency, which is
dominated by LLM calls either way and identical in both paths):

```
Direct in-process call:  0.02 ms/call
Via MCP (spawn+call):     789.35 ms/call
Overhead added by MCP:    789.32 ms/call  (~32,700x)
```

**Why it's this large**: our Phase 1 design decision - spawn the server
fresh, call one tool, tear down - means every single tool call pays for a
new Python subprocess start *and* a full MCP handshake. That's not an
inherent cost of the MCP protocol itself; it's the cost of choosing "no
persistent connection" for simplicity. A connection kept open for an
agent's lifetime (reused across multiple tool calls) would amortize the
handshake to once per agent run instead of once per call - a real,
concrete optimization to consider if/when this becomes a bottleneck, but
out of scope for what this phase asked for.

**Practical impact today**: each specialist agent calls its tool
~once per review, so this adds roughly 0.8s to that agent's total time -
noticeable next to LLM call latency (1-3s each) but not dominant, and
since Style/Security/Test-Coverage already run in parallel (Phase 4 of the
original build), it doesn't multiply across agents.

## Files Created/Modified

- `app/mcp_clients/__init__.py`, `app/mcp_clients/bridge.py` (new)
- `app/agents/style_agent.py` (import + tool body changed; nothing else)

## Next: MCP Phase 4 - Repeat for Test-Coverage and Security

Convert `check_test_coverage()` and `scan_security()` to their own MCP
servers, update their agents the same way, one at a time - then run the
full supervisor graph end-to-end to confirm the merged review is still
consistent with pre-refactor behavior.
