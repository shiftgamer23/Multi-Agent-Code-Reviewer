"""
MCP Phase 4 verification: confirm the test-coverage MCP server produces
byte-identical output to the existing in-process check_test_coverage_tool
(test_coverage_agent.py) on the same inputs, before the Test-Coverage
Agent is touched.

Run: .\\venv\\Scripts\\python.exe test_mcp_test_coverage_server.py
"""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252, can't print the checkmarks in tool output
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.agents.test_coverage_agent import check_test_coverage_tool as original_tool

TEST_CASES = [
    {
        "name": "test file added alongside production change",
        "diff_hunk": (
            "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
            "@@ -1,5 +1,6 @@\n import flask\n+from utils import helper\n\n"
            " def hello():\n     return \"Hello\"\n"
            "diff --git a/test_app.py b/test_app.py\n--- /dev/null\n+++ b/test_app.py\n"
            "@@ -0,0 +1,10 @@\n+import pytest\n+from app import hello\n+\n"
            "+def test_hello():\n+    assert hello() == \"Hello\"\n"
        ),
        "lang": "py",
    },
    {
        "name": "no test files (should recommend adding tests)",
        "diff_hunk": (
            "diff --git a/production.py b/production.py\n--- a/production.py\n+++ b/production.py\n"
            "@@ -1,3 +1,4 @@\n def critical_function():\n-    return 42\n+    return 43  # Changed logic\n"
        ),
        "lang": "py",
    },
]


async def call_via_mcp(diff_hunk: str, lang: str) -> str:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_servers/test_coverage_server.py"],
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "check_test_coverage_tool", {"diff_hunk": diff_hunk, "lang": lang}
            )
            return "".join(block.text for block in result.content if block.type == "text")


def call_via_direct_import(diff_hunk: str, lang: str) -> str:
    return original_tool.invoke({"diff_hunk": diff_hunk, "lang": lang})


async def main():
    all_match = True
    for case in TEST_CASES:
        print(f"=== {case['name']} ===")
        direct_result = call_via_direct_import(case["diff_hunk"], case["lang"])
        mcp_result = await call_via_mcp(case["diff_hunk"], case["lang"])

        match = direct_result == mcp_result
        all_match = all_match and match

        print(f"  direct import: {direct_result}")
        print(f"  via MCP:       {mcp_result}")
        print(f"  MATCH: {match}\n")

    if all_match:
        print("All cases match.")
    else:
        print("MISMATCH FOUND - do not proceed until resolved.")


if __name__ == "__main__":
    asyncio.run(main())
