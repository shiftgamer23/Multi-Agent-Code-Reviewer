"""
Security Agent — same ReAct graph shape as the Style Agent (Phase 3),
built via react_agent_factory, bound to the security-scanning tool instead.

Responsible ONLY for security anti-patterns (hardcoded secrets, SQL
injection, dangerous functions, weak crypto). Must NOT comment on style
or test coverage - those belong to the other specialist agents.
"""
import os

from langchain_core.tools import tool

from app.agents.react_agent_factory import build_single_tool_agent
from app.mcp_clients import call_mcp_tool

SECURITY_MCP_SERVER = "mcp_servers/security_server.py"
SECURITY_MCP_URL = os.getenv("SECURITY_MCP_URL")

SECURITY_AGENT_SYSTEM_PROMPT = """You are a Security Reviewer, one specialist on a code review team.

Your ONLY job is flagging security anti-patterns: hardcoded secrets, SQL
injection, dangerous functions (eval/exec/pickle.loads), weak cryptography,
insecure deserialization, insecure transport. You do NOT comment on style
or missing tests - other specialists on the team own those, and commenting
outside your lane creates noise.

Always call the check_code_security tool on the diff before writing
feedback - do not guess at vulnerabilities from reading the diff yourself.

After seeing the tool result, write your review as a short PR comment
(1-3 sentences, like a real human reviewer would leave). Lead with the
highest-severity issue if there are several. If the tool found no issues,
say so briefly instead of inventing feedback.

If the tool reports that this language is not supported, say so plainly
(e.g. "Security scanning isn't available for this language yet") - do NOT
claim the code is secure or free of vulnerabilities, since that was never
actually checked.
"""


@tool
def check_code_security(diff_hunk: str, lang: str = "py") -> str:
    """Scan a code diff for security anti-patterns: hardcoded secrets, SQL
    injection, dangerous functions (eval/exec/pickle), weak cryptography,
    insecure deserialization, insecure transport. Call this before giving
    any security feedback on a diff."""
    # MCP Phase 4: was a direct in-process call to scan_security() (app/
    # tools/security_checker.py). Now goes over MCP to security_server.py,
    # which wraps that same untouched function - including the
    # unsupported-language handling, so no reduction logic needs to live
    # here anymore.
    if SECURITY_MCP_URL:
        return call_mcp_tool(
            tool_name="check_code_security", server_url=SECURITY_MCP_URL,
            diff_hunk=diff_hunk, lang=lang,
        )
    return call_mcp_tool(
        tool_name="check_code_security", server_script=SECURITY_MCP_SERVER,
        diff_hunk=diff_hunk, lang=lang,
    )


def run_security_review(diff_hunk: str, old_file: str = "", lang: str = "py", session_id: str = None) -> str:
    """Run the Security Agent on one diff and return its final review comment."""
    run = build_single_tool_agent(SECURITY_AGENT_SYSTEM_PROMPT, check_code_security)

    user_prompt = f"""Review this diff for SECURITY issues only.

Language: {lang}

Original file (context, may be truncated):
{old_file[:500]}

Diff:
{diff_hunk}
"""
    return run(user_prompt, session_id=session_id)
