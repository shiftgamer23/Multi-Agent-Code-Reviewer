# MCP Phase 1: Fundamentals + Environment Setup ✓ COMPLETE

## What We Built

- Installed the official MCP Python SDK (`mcp==2.2.0` - the current major
  version; note this is a different API generation than most existing
  tutorials describe, see "API surface changed" below)
- `mcp_servers/hello_server.py` — a trivial MCP server with one dummy tool
  (`say_hello`), run over stdio transport
- `test_mcp_hello_client.py` — a minimal MCP client that spawns the server
  as a subprocess, completes the handshake, discovers its tools, and calls
  `say_hello` — verified working end-to-end

## Core MCP Concepts (grounded in what we just built)

**Server and client are separate processes, not separate objects in the
same program.** `hello_server.py` run standalone does nothing visible - it
sits waiting on stdin/stdout. `test_mcp_hello_client.py` is what actually
starts it, via `stdio_client(StdioServerParameters(command=..., args=...))`,
which spawns the server file as a subprocess and wires its stdin/stdout as
the wire protocol. This is the "stdio transport" the plan flagged as
simplest for local dev - no network sockets, no ports, just a pipe. (The
SDK also supports SSE and streamable-HTTP transports for a network-
accessible server; we're not using those yet.)

**Tool declaration is schema-first, and it's automatic.** `@server.tool()`
on a plain typed function (`say_hello(name: str) -> str`) is enough - the
SDK inspects the function signature and generates the JSON Schema a client
needs (`{"properties": {"name": {"type": "string"}}, "required": ["name"]}`)
without us writing it by hand. This is the same mental model as
LangChain's `@tool` decorator we've used throughout this project - just a
different protocol carrying it.

**Discovery happens at runtime, over the wire.** The client doesn't import
anything from the server's code - it calls `session.list_tools()` *after*
connecting, and gets back names/descriptions/schemas as data. This is the
actual point of MCP: any MCP-aware client could discover and call
`say_hello` without ever having seen `hello_server.py`'s source.

**The three-step client dance**: `stdio_client(...)` (spawn + connect) →
`ClientSession(read_stream, write_stream)` + `.initialize()` (handshake) →
`.call_tool(name, arguments)` (actual invocation). All three are async
context managers/calls - MCP is fundamentally async under the hood.

## A Real Bug Found and Fixed Along the Way

Installing `mcp` pulled in `starlette 1.6.0` as a transitive dependency
(via `sse-starlette`, used for MCP's non-stdio transports) - but our
`fastapi==0.115.0` requires `starlette<0.39.0`. This silently broke the
existing FastAPI app (`Router.__init__() got an unexpected keyword
argument 'on_startup'`) until caught by directly testing `from app.main
import app` after the install, rather than assuming it still worked.

Fixed by pinning `starlette==0.38.6` explicitly in `requirements.txt`
alongside `mcp==2.2.0`. Verified the fix is real (not just a local
workaround) via `pip install -r requirements.txt --dry-run`, which showed
pip's resolver independently arriving at a compatible `sse-starlette`
version (3.0.3, down from 3.4.11) given our pin - meaning a fresh install
(e.g. inside the Phase 6 Docker rebuild) resolves cleanly too, not just
our already-patched dev venv. `pip check` now reports zero conflicts.

## API Surface Changed Since Most Existing Tutorials

`mcp==2.2.0` renamed `mcp.server.fastmcp.FastMCP` to
`mcp.server.mcpserver.MCPServer` - the old import raises a
`ModuleNotFoundError` with an explicit message pointing at the migration
guide. Confirmed the current class shape by reading the installed SDK
source directly (`server.py`'s `MCPServer` class, `.tool()` decorator,
`.run(transport=...)` method) rather than relying on possibly-outdated
training knowledge - worth remembering for later phases too, since this
SDK generation may differ from what's commonly documented online.

## Research: How Will Agents Bridge to MCP Tools? (Resolved Before Phase 2)

Our agents bind tools via LangChain's native `bind_tools()` (see
`react_agent_factory.py`, `style_agent.py`) - converting to MCP clients
means an MCP server's tool needs to become something `bind_tools()` can
accept. Researched the options rather than assume from memory, since we'd
already been burned once this phase by an out-of-date assumption about
the `mcp` SDK's own API:

- **`langchain-mcp-adapters`** (what I originally recalled) is now
  explicitly deprecated - its README states MCP support "has moved into
  LangChain under the `langchain.mcp` namespace."
- **`langchain.mcp`**, the replacement, does exist in our installed
  `langchain==1.4.0` - but it's marked **beta** (`LangChainBetaWarning`,
  "actively being worked on, so the API may change") and its core
  function `as_langchain_tool(tool, client)` requires a **separate
  third-party package**, `fastmcp` (`client: Client | ClientGroup`) - not
  the `mcp.client.session.ClientSession` we already have verified working
  from this phase's hello-world test. Confirmed by reading
  `langchain/mcp/tools.py`'s actual imports, not documentation summaries.

**Decision: hand-roll the bridge ourselves**, directly on the raw `mcp`
SDK already verified above, rather than adopt `langchain.mcp` + `fastmcp`.
Reasoning: zero new dependencies (we're already managing one delicate
pin - `mcp==2.2.0` + `starlette==0.38.6` - and don't want to stack a beta
API and another package's version surface on top of it), no risk of the
bridge API shifting mid-refactor, and it keeps us actually understanding
the client-to-LangChain-tool conversion rather than delegating it to a
still-unstable abstraction - which fits this plan's own stated goal of
learning real MCP mechanics, not just consuming a library that does it
for us.

Concretely, in Phase 2/3: connect via `ClientSession` (as in
`test_mcp_hello_client.py`), call `session.list_tools()` to discover the
server's tool + schema, and wrap it as a `langchain_core.tools.StructuredTool`
whose `func` calls `session.call_tool(name, args)` - then it slots into
`bind_tools_with_fallback()` exactly like any other tool today.

## Files Created

- `mcp_servers/__init__.py`, `mcp_servers/hello_server.py`
- `test_mcp_hello_client.py`
- `requirements.txt` updated (`mcp==2.2.0`, `starlette==0.38.6` pinned)

## Next: MCP Phase 2 - Convert the Linter Tool to an MCP Server

Wrap `check_style()` from `app/tools/linter.py` in its own MCP server,
verify standalone via a client call matching the original function's
output on the same input. Style Agent stays untouched until Phase 3.
