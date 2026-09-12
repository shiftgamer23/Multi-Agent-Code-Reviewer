"""
MCP server wrapping the existing Security tool.

Same pattern as linter_server.py (MCP Phase 2) and test_coverage_server.py
(MCP Phase 4): a thin protocol layer around scan_security() (app/tools/
security_checker.py) - that function's tested logic is untouched. The
tool's name, docstring, parameters, and reduced-string output mirror
security_agent.py's current check_code_security @tool wrapper exactly,
including the unsupported-language honesty fix from the original build's
Phase 6.

Run standalone: .\\venv\\Scripts\\python.exe mcp_servers\\security_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.tools.security_checker import scan_security  # noqa: E402
from mcp_servers._run import run_server  # noqa: E402

server = MCPServer(name="security-server")


@server.tool()
def check_code_security(diff_hunk: str, lang: str = "py") -> str:
    """Scan a code diff for security anti-patterns: hardcoded secrets, SQL
    injection, dangerous functions (eval/exec/pickle), weak cryptography,
    insecure deserialization, insecure transport. Call this before giving
    any security feedback on a diff."""
    result = scan_security(diff_hunk, lang=lang)
    if result.get("unsupported_language"):
        return (
            f"SECURITY SCAN NOT AVAILABLE for language '{lang}'. This is not "
            "the same as 'no issues found' - the scan was never performed. "
            "Do not claim the code is secure; state plainly that security "
            "scanning isn't supported for this language."
        )
    output = result["summary"]
    if result.get("recommendations"):
        output += "\n\nRecommendations:\n" + "\n".join(
            f"- {r}" for r in result["recommendations"]
        )
    return output


if __name__ == "__main__":
    run_server(server, default_port=8003)
