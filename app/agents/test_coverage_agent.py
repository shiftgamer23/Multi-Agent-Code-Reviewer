"""
Test-Coverage Agent — same ReAct graph shape as the Style Agent (Phase 3),
built via react_agent_factory, bound to the test-coverage-detection tool
instead.

Responsible ONLY for whether tests were added/updated for a change. Must
NOT comment on style or security - those belong to the other specialist
agents.
"""
import os

from langchain_core.tools import tool

from app.agents.react_agent_factory import build_single_tool_agent
from app.mcp_clients import call_mcp_tool

TEST_COVERAGE_MCP_SERVER = "mcp_servers/test_coverage_server.py"
TEST_COVERAGE_MCP_URL = os.getenv("TEST_COVERAGE_MCP_URL")

TEST_COVERAGE_AGENT_SYSTEM_PROMPT = """You are a Test-Coverage Reviewer, one specialist on a code review team.

Your ONLY job is judging whether this diff has adequate test coverage:
were test files added or updated alongside the production code change? You
do NOT comment on style or security vulnerabilities - other specialists on
the team own those, and commenting outside your lane creates noise.

Always call the check_test_coverage tool on the diff before writing
feedback - do not guess at test coverage from reading the diff yourself.

After seeing the tool result, write your review as a short PR comment
(1-3 sentences, like a real human reviewer would leave). If tests look
sufficient, say so briefly instead of inventing feedback.
"""


@tool
def check_test_coverage_tool(diff_hunk: str, lang: str = "py") -> str:
    """Check whether a diff includes test file additions or modifications
    alongside its production code changes. Call this before giving any
    test-coverage feedback on a diff."""
    # MCP Phase 4: was a direct in-process call to check_test_coverage()
    # (app/tools/test_detector.py). Now goes over MCP to
    # test_coverage_server.py (MCP Phase 4), which wraps that same
    # untouched function.
    if TEST_COVERAGE_MCP_URL:
        return call_mcp_tool(
            tool_name="check_test_coverage_tool", server_url=TEST_COVERAGE_MCP_URL,
            diff_hunk=diff_hunk, lang=lang,
        )
    return call_mcp_tool(
        tool_name="check_test_coverage_tool", server_script=TEST_COVERAGE_MCP_SERVER,
        diff_hunk=diff_hunk, lang=lang,
    )


def run_test_coverage_review(diff_hunk: str, old_file: str = "", lang: str = "py", session_id: str = None) -> str:
    """Run the Test-Coverage Agent on one diff and return its final review comment."""
    run = build_single_tool_agent(
        TEST_COVERAGE_AGENT_SYSTEM_PROMPT, check_test_coverage_tool
    )

    user_prompt = f"""Review this diff for TEST COVERAGE only.

Language: {lang}

Original file (context, may be truncated):
{old_file[:500]}

Diff:
{diff_hunk}
"""
    return run(user_prompt, session_id=session_id)
