"""
MCP server wrapping the existing Style/Linter tool.

Phase 2 of the MCP refactor: a thin protocol layer around check_style()
(app/tools/linter.py) - that function's tested logic is untouched, not
reimplemented, per mcp_plan.md's guidance. The tool's name, docstring
(-> MCP description), parameters, and reduced-string output deliberately
mirror style_agent.py's current check_code_style @tool wrapper exactly,
so swapping the Style Agent to call this over MCP (Phase 3) changes
nothing about what the LLM sees.

Run standalone: .\\venv\\Scripts\\python.exe mcp_servers\\linter_server.py
Normally an MCP client spawns this as a subprocess instead (see
test_mcp_linter_server.py).
"""
import sys
from pathlib import Path

# Let `python mcp_servers/linter_server.py` find the `app` package when run
# directly - this is exactly how the client will spawn it (by file path,
# not as an installed module), so the path fix belongs here, not in a
# README note.
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.tools.linter import check_style  # noqa: E402
from mcp_servers._run import run_server  # noqa: E402

server = MCPServer(name="linter-server")


@server.tool()
def check_code_style(diff_hunk: str, lang: str = "py") -> str:
    """Check a code diff for style violations: line length, trailing
    whitespace, blank-line conventions, missing docstrings, unused imports.
    Call this before giving any style feedback on a diff."""
    result = check_style(diff_hunk, lang=lang)
    if result.get("unsupported_language"):
        return (
            f"STYLE CHECK NOT AVAILABLE for language '{lang}'. This is not "
            "the same as 'no issues found' - the check was never performed. "
            "Do not claim the code is stylistically clean; state plainly "
            "that style checking isn't supported for this language."
        )
    return result["summary"]


if __name__ == "__main__":
    run_server(server, default_port=8001)
