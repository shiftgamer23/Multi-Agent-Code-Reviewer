"""
MCP server wrapping the existing Test-Coverage tool.

Same pattern as linter_server.py (MCP Phase 2): a thin protocol layer
around check_test_coverage() (app/tools/test_detector.py) - that
function's tested logic is untouched. The tool's name, docstring,
parameters, and reduced-string output mirror test_coverage_agent.py's
current check_test_coverage_tool @tool wrapper exactly.

Run standalone: .\\venv\\Scripts\\python.exe mcp_servers\\test_coverage_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.tools.test_detector import check_test_coverage  # noqa: E402
from mcp_servers._run import run_server  # noqa: E402

server = MCPServer(name="test-coverage-server")


@server.tool()
def check_test_coverage_tool(diff_hunk: str, lang: str = "py") -> str:
    """Check whether a diff includes test file additions or modifications
    alongside its production code changes. Call this before giving any
    test-coverage feedback on a diff."""
    result = check_test_coverage(diff_hunk, lang=lang)
    output = result["summary"]
    if result.get("recommendation"):
        output += f"\n\nRecommendation: {result['recommendation']}"
    return output


if __name__ == "__main__":
    run_server(server, default_port=8002)
