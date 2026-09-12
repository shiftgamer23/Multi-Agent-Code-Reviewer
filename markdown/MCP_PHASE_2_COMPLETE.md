# MCP Phase 2: Linter Tool → MCP Server ✓ COMPLETE

## What We Built

- `mcp_servers/linter_server.py` — wraps `check_style()` from
  `app/tools/linter.py` (untouched, tested logic from the original build)
  in an `MCPServer`. The `check_code_style` tool's name, docstring,
  parameters, and reduced-string output deliberately mirror
  `style_agent.py`'s existing `@tool`-decorated wrapper exactly.
- `test_mcp_linter_server.py` — calls the same input through both paths
  (direct import + `.invoke()`, vs. spawning the server and calling it
  over MCP) and asserts identical output.

## Verified: Byte-Identical Output, 3 Cases

| Case | Result |
|---|---|
| Real style issue (line >100 chars) | `MATCH: True` |
| Clean diff, no issues | `MATCH: True` |
| Unsupported language (`java`) - the Phase 6 honesty fix | `MATCH: True` |

The third case matters most: it confirms the "don't fabricate a clean bill
of health for unsupported languages" fix from the original project's Phase
6 survives the MCP round-trip unchanged, not just the happy path.

## Style Agent Is Still Untouched

Per the plan's guardrail - `style_agent.py` still calls `check_style()`
directly, in-process. This phase only proved the MCP server works in
isolation. Phase 3 is where the agent itself switches over.

## Files Created

- `mcp_servers/linter_server.py`
- `test_mcp_linter_server.py`

## Next: MCP Phase 3 - Update the Style Agent to Use This Server

Switch `style_agent.py`'s tool-calling mechanism from the direct `@tool`
wrapper to an MCP client call against this server (per the hand-rolled
bridge decided in Phase 1: `ClientSession` → `list_tools()` →
`StructuredTool` → `bind_tools_with_fallback()`). Re-run the same
dev/valid examples from the original build's Phase 3 to confirm consistent
behavior, and note any latency difference from the added protocol hop.
