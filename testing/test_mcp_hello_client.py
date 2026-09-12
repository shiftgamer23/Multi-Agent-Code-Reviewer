"""
Phase 1 sanity check: a minimal MCP client that spawns hello_server.py as a
subprocess over stdio, discovers its tools, and calls the dummy tool.

This proves the plumbing (spawn -> handshake -> tool discovery -> tool
call -> result) works before any real ReviewCrew tool logic is involved.

Run: .\\venv\\Scripts\\python.exe test_mcp_hello_client.py
"""
import asyncio
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    # Use sys.executable, not the bare string "python" - a subprocess
    # spawned by name resolves via PATH, which may not be this venv's
    # interpreter (bit us before in Phase 1/5 of the original build).
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_servers/hello_server.py"],
    )

    # stdio_client spawns the server as a subprocess and hands back a
    # (read_stream, write_stream) pair wired to its stdin/stdout.
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Handshake complete.\n")

            tools = await session.list_tools()
            print(f"Discovered {len(tools.tools)} tool(s):")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")
                print(f"    input schema: {t.input_schema}")

            print("\nCalling say_hello(name='ReviewCrew')...")
            result = await session.call_tool("say_hello", {"name": "ReviewCrew"})
            print(f"Result: {result.content}")


if __name__ == "__main__":
    asyncio.run(main())
