# MCP Phase 4: Test-Coverage + Security → MCP Clients ✓ COMPLETE

## What We Built

Same pattern as Phase 2/3, applied to the remaining two tools, one at a
time per the plan's guardrail:

- `mcp_servers/test_coverage_server.py` — wraps `check_test_coverage()`
  (`app/tools/test_detector.py`)
- `mcp_servers/security_server.py` — wraps `scan_security()`
  (`app/tools/security_checker.py`), including the unsupported-language
  honesty fix from the original build's Phase 6
- `test_mcp_test_coverage_server.py`, `test_mcp_security_server.py` —
  standalone byte-identical verification, each server tested in isolation
  before touching its agent
- `app/agents/test_coverage_agent.py`, `app/agents/security_agent.py` —
  same minimal-change pattern as Style Agent: only the tool wrapper's body
  changed (direct call → `call_mcp_tool(...)`); decorator, signature,
  docstring all untouched

## Verified Three Ways

**1. Standalone server tests** (no LLM) — all cases byte-identical to the
direct-import path, including:
- Test-Coverage: test-file-detected case + no-test-files case
- Security: real hardcoded-secret/dangerous-function case + clean diff +
  unsupported language (`rust`) - the Phase 6 honesty fix, confirmed intact

**2. Both agents individually, real LLM calls**, same dev/valid examples
used throughout this project — reproduced the original findings on all 3
examples: Security correctly reports no issues on genuinely clean diffs;
Test-Coverage correctly flags missing tests with diff-specific reasoning
each time (not templated).

**3. Full supervisor graph end-to-end** (the plan's required final step
for this phase) — all three agents now MCP-based, run through the same
test diff used throughout this project's testing:

```
Style:         No style violations found.
Security:      No security issues found in this diff.
Test Coverage: This change modifies production code without adding or
               updating any corresponding test files...
MERGED:        ...combines all three into one coherent comment, same
               structure and substance as every pre-refactor run of this
               same diff (Phases 4/5/7/8 of the original build).
```

Nothing about `supervisor_graph.py` itself changed in this phase - the
routing, parallel fan-out, and merge logic are untouched, exactly as the
plan's scope guardrail requires ("should not change unless something
about the MCP transition specifically requires it"). Only what happens
*inside* each specialist's tool call changed.

## Encoding Bug Fixed Along the Way (Unrelated to MCP)

`test_mcp_test_coverage_server.py` crashed on Windows before even showing
results - `UnicodeEncodeError` from the console's default `cp1252`
encoding choking on the ✓/⚠ characters in the tool's own output strings.
Pre-existing issue (same class as earlier phases' `✓` crashes), fixed with
`sys.stdout.reconfigure(encoding="utf-8")` at the top of both new test
scripts.

## Files Created/Modified

- `mcp_servers/test_coverage_server.py`, `mcp_servers/security_server.py` (new)
- `test_mcp_test_coverage_server.py`, `test_mcp_security_server.py` (new)
- `app/agents/test_coverage_agent.py`, `app/agents/security_agent.py`
  (import + tool body changed; nothing else)

## Status: All Three Tools Converted

Style (Phase 2/3), Test-Coverage and Security (this phase) all now call
their MCP server counterparts. `app/tools/*.py`'s original functions
remain the actual implementation everywhere - unchanged since the
original build - each MCP server is just a thin protocol shell around
them, exactly as `mcp_plan.md` specified.

## Next: MCP Phase 5 (optional) or Phase 6 - Docker Compose

Phase 5 (GitHub MCP integration) is explicitly optional/exploratory per
the plan. Phase 6 updates `docker-compose.yml` so each MCP server runs as
its own service - a real multi-service topology instead of the current
"subprocess spawned per tool call" pattern.
