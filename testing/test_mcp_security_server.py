"""
MCP Phase 4 verification: confirm the security MCP server produces
byte-identical output to the existing in-process check_code_security tool
(security_agent.py) on the same inputs, before the Security Agent is touched.

Run: .\\venv\\Scripts\\python.exe test_mcp_security_server.py
"""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.agents.security_agent import check_code_security as original_tool

TEST_CASES = [
    {
        "name": "hardcoded secret + dangerous function (real issues)",
        "diff_hunk": (
            "@@ -1,10 +1,15 @@\n import os\n+import pickle\n\n"
            " def authenticate(user_input):\n-    return user_input == \"admin\"\n"
            "+    password = \"supersecret123\"\n+    data = pickle.loads(user_input)\n"
            "+    query = \"SELECT * FROM users WHERE name='\" + user_input + \"'\"\n"
            "+    return query\n"
        ),
        "lang": "py",
    },
    {
        "name": "clean diff (no issues)",
        "diff_hunk": "@@ -1,2 +1,2 @@\n def hello():\n-    return \"hi\"\n+    return \"hello\"\n",
        "lang": "py",
    },
    {
        "name": "unsupported language (rust) - the Phase 6 honesty fix",
        "diff_hunk": "@@ -1,2 +1,2 @@\n fn hello() {\n-    return;\n+    return;\n",
        "lang": "rust",
    },
]


async def call_via_mcp(diff_hunk: str, lang: str) -> str:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_servers/security_server.py"],
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                "check_code_security", {"diff_hunk": diff_hunk, "lang": lang}
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
