"""
Phase 2 verification: confirm the linter MCP server produces byte-identical
output to the existing in-process check_code_style tool (style_agent.py)
on the same inputs, before the Style Agent is touched (that's Phase 3).

Run: .\\venv\\Scripts\\python.exe test_mcp_linter_server.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.agents.style_agent import check_code_style as original_check_code_style

TEST_CASES = [
    {
        "name": "long line (real style issue)",
        "diff_hunk": (
            "@@ -1,2 +1,3 @@\n"
            " def process_data(data):\n"
            "+    result = some_function_that_has_a_very_long_line_name_that_exceeds_the_100_character_limit_for_sure_yes\n"
            "     return data\n"
        ),
        "lang": "py",
    },
    {
        "name": "clean diff (no issues)",
        "diff_hunk": "@@ -1,2 +1,2 @@\n def hello():\n-    return \"hi\"\n+    return \"hello\"\n",
        "lang": "py",
    },
    {
        "name": "unsupported language (java)",
        "diff_hunk": "@@ -1,2 +1,2 @@\n public void hello() {\n-    return;\n+    return;\n",
        "lang": "java",
    },
]


async def call_via_mcp(diff_hunk: str, lang: str) -> str:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_servers/linter_server.py"],
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "check_code_style", {"diff_hunk": diff_hunk, "lang": lang}
            )
            # MCP wraps text results as a list of TextContent blocks.
            return "".join(block.text for block in result.content if block.type == "text")


def call_via_direct_import(diff_hunk: str, lang: str) -> str:
    # .invoke() is how any LangChain @tool-decorated callable is actually
    # invoked in production (style_agent.py never calls it as a bare
    # function) - so this is a true apples-to-apples comparison against
    # the real existing code path, not a re-implementation of it.
    return original_check_code_style.invoke({"diff_hunk": diff_hunk, "lang": lang})


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
        print("All cases match - MCP server output is identical to the direct-import path.")
    else:
        print("MISMATCH FOUND - do not proceed to Phase 3 until resolved.")


if __name__ == "__main__":
    asyncio.run(main())
