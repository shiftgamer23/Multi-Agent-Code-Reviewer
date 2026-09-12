"""
MCP Phase 5 (optional/exploratory): connect to GitHub's official, real
MCP server - not one we built - as a genuine test of "any MCP client can
consume any MCP server."

Runs the server locally via Docker over stdio transport (confirmed
supported by github/github-mcp-server's own docs), same connection
pattern as our own servers in mcp_servers/. Our .env has the token as
GITHUB_ACCESS_TOKEN, not the GITHUB_PERSONAL_ACCESS_TOKEN name the
container itself expects - remapped here rather than renaming it in .env,
same approach as the LANGFUSE_BASE_URL/LANGFUSE_HOST fix in MCP Phase
8 of the original build.

Run: .\\venv\\Scripts\\python.exe test_mcp_github_server.py
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

load_dotenv()

REPO_OWNER = "shiftgamer23"
REPO_NAME = "Multi-Agent-Code-Reviewer"
BRANCH = "main"


async def main():
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    if not token:
        raise ValueError("GITHUB_ACCESS_TOKEN not found in .env")

    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server",
        ],
        # docker run's bare "-e GITHUB_PERSONAL_ACCESS_TOKEN" forwards that
        # name from docker run's own environment into the container - so
        # it must exist under exactly that name here, regardless of what
        # it's called in our .env.
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("Handshake complete with GitHub's real MCP server.\n")

            tools = await session.list_tools()
            print(f"Discovered {len(tools.tools)} tool(s) total.")
            # Just the ones relevant to what we actually want to try.
            relevant = [t for t in tools.tools if "file" in t.name.lower() or "issue" in t.name.lower()]
            print(f"Relevant to our test ({len(relevant)}):")
            for t in relevant:
                print(f"  - {t.name}: {t.description[:100]}")

            print(f"\n--- Calling get_file_contents for requirements.txt on {REPO_OWNER}/{REPO_NAME}@{BRANCH} ---")
            result = await session.call_tool(
                "get_file_contents",
                {"owner": REPO_OWNER, "repo": REPO_NAME, "path": "requirements.txt", "ref": BRANCH},
            )
            text = "".join(block.text for block in result.content if block.type == "text")
            print(text[:500])

            print(f"\n--- Calling list_issues for {REPO_OWNER}/{REPO_NAME} ---")
            result2 = await session.call_tool(
                "list_issues",
                {"owner": REPO_OWNER, "repo": REPO_NAME},
            )
            text2 = "".join(block.text for block in result2.content if block.type == "text")
            print(text2[:500])


if __name__ == "__main__":
    asyncio.run(main())
