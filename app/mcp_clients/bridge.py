"""
Hand-rolled bridge: call one tool on an MCP server, return its text result
as a plain string - simple enough to call directly from inside the
existing @tool-decorated wrapper functions in app/agents/.

Decided in MCP Phase 1 over `langchain.mcp` (beta API, depends on the
separate `fastmcp` package) - this uses the same mcp SDK ClientSession
pattern verified end-to-end in Phase 1's hello-world server and Phase 2's
linter server tests.

Two transports, one call site (Phase 6 addition):
- stdio (Phases 2-5): spawns the server as a local subprocess fresh per
  call - simplest for local dev, but can't reach a server running in a
  *separate* Docker container (stdio spawns a child process on the same
  host; it cannot "spawn" an already-running, separate container).
- streamable-http (Phase 6): connects over the network to a server
  that's already running as its own long-lived service - what Docker
  Compose needs when each MCP server is its own container. Confirmed
  streamable_http_client() returns the same (read_stream, write_stream)
  shape stdio_client() does, so ClientSession/call_tool usage below is
  identical either way - only how the connection is established differs.

Which transport a given call uses is selected by which keyword argument
the caller passes (server_script vs server_url) - see each agent file for
how that's decided per-environment (mirrors the REDIS_HOST-with-a-
localhost-default pattern from Phase 7).
"""
import asyncio
import sys
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client


async def _call_via_stdio(server_script: str, tool_name: str, tool_args: dict[str, Any]) -> str:
    server_params = StdioServerParameters(command=sys.executable, args=[server_script])
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            return "".join(block.text for block in result.content if block.type == "text")


async def _call_via_http(server_url: str, tool_name: str, tool_args: dict[str, Any]) -> str:
    async with streamable_http_client(server_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)
            return "".join(block.text for block in result.content if block.type == "text")


def call_mcp_tool(
    tool_name: str,
    server_script: str | None = None,
    server_url: str | None = None,
    **tool_args: Any,
) -> str:
    """
    Synchronous entry point - LangGraph's agent nodes are sync, so this
    hides asyncio.run() and the connection lifecycle from callers. Safe to
    call from the parallel worker threads the supervisor graph's fan-out
    uses, since asyncio.run() creates a fresh event loop per call and
    there's no already-running loop in those threads.

    Pass exactly one of server_script (stdio, local dev) or server_url
    (streamable-http, Docker Compose).
    """
    if (server_script is None) == (server_url is None):
        raise ValueError("Pass exactly one of server_script or server_url")

    if server_url is not None:
        return asyncio.run(_call_via_http(server_url, tool_name, tool_args))
    return asyncio.run(_call_via_stdio(server_script, tool_name, tool_args))
