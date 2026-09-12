"""
Shared entrypoint helper for mcp_servers/*.py - Phase 6 (Docker Compose)
addition. Each server's own `if __name__ == "__main__":` block just calls
run_server(server, default_port=...) instead of repeating the same
transport-selection logic three times.

MCP_TRANSPORT env var selects the mode:
- unset/"stdio" (default): local dev, unchanged since Phase 2
- "http": streamable-http, host 0.0.0.0 so the container is reachable by
  service name from other Docker Compose services (matches the
  REDIS_HOST-with-a-localhost-default pattern from Phase 7)
"""
import os

from mcp.server.mcpserver import MCPServer


def run_server(server: MCPServer, default_port: int) -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        port = int(os.getenv("MCP_PORT", str(default_port)))
        server.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        server.run(transport="stdio")
