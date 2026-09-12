"""
Phase 1 sanity check - a trivial MCP server with one dummy tool, run before
touching any real ReviewCrew tool.

Built against mcp==2.2.0's actual current API (confirmed by reading the
installed SDK source directly, not assumed from memory): the old
`mcp.server.fastmcp.FastMCP` class was renamed to
`mcp.server.mcpserver.MCPServer` in mcp 2.x. Ergonomics are otherwise the
same as v1/FastMCP - a `@server.tool()` decorator on a plain typed
function, input schema auto-derived from the signature. Same mental model
as the `@tool` decorator we've used throughout this project with LangChain,
just a different protocol underneath.

Run standalone (for manual testing): .\\venv\\Scripts\\python.exe mcp_servers\\hello_server.py
Normally, an MCP client spawns this as a subprocess instead (see
test_mcp_hello_client.py) - stdio transport means "this process's stdin/
stdout IS the wire protocol," so nothing should ever print() here outside
of what the SDK itself writes.
"""
from mcp.server.mcpserver import MCPServer

server = MCPServer(name="hello-server")


@server.tool()
def say_hello(name: str) -> str:
    """Say hello to someone. Dummy tool - just proves the client<->server
    plumbing works before any real ReviewCrew tool logic is involved."""
    return f"Hello, {name}! (from the MCP hello-server)"


if __name__ == "__main__":
    server.run(transport="stdio")
