"""
Style Agent — the first LangGraph agent in this project.

Responsible ONLY for style/readability feedback (line length, naming,
formatting, unused imports, docstrings). Must NOT comment on security or
test coverage — those are separate agents built in Phase 4.

Graph shape (the ReAct pattern):

    START -> agent -> [conditional] -> tools -> agent -> ... -> END
                            |
                            +-> (no tool call) -> END

- "agent" node: one LLM call (gemini-3.5-flash-lite, tools bound). The LLM
  itself decides, per turn, whether it needs a tool or has enough to answer.
- "tools" node: executes whatever tool the LLM asked for and appends the
  result as a ToolMessage.
- "should_continue": plain Python, no LLM call — inspects the last message's
  .tool_calls to route to "tools" or END.
- The agent -> tools edge loops back to "agent" so the LLM sees the tool
  result and can either call another tool or produce its final review text.
"""
import os
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.infra.tracing import invoke_config
from app.llm import bind_tools_with_fallback
from app.mcp_clients import call_mcp_tool

LINTER_MCP_SERVER = "mcp_servers/linter_server.py"
# Unset locally (stdio, spawn-per-call) - set in docker-compose.yml, Phase 6,
# where linter-server is its own long-lived container reached over the network.
LINTER_MCP_URL = os.getenv("LINTER_MCP_URL")

STYLE_AGENT_SYSTEM_PROMPT = """You are a Style Reviewer, one specialist on a code review team.

Your ONLY job is style and readability: line length, naming, formatting,
unused imports, missing docstrings, blank-line conventions. You do NOT
comment on security vulnerabilities or missing tests - other specialists on
the team own those, and commenting outside your lane creates noise.

Always call the check_code_style tool on the diff before writing feedback -
do not guess at style issues from reading the diff yourself.

After seeing the tool result, write your review as a short PR comment
(1-3 sentences, like a real human reviewer would leave). If the tool found
no issues, say so briefly instead of inventing feedback.

If the tool reports that this language is not supported, say so plainly
(e.g. "Style checking isn't available for this language yet") - do NOT
claim the code is clean, well-formatted, or free of style issues, since
that was never actually checked.
"""


@tool
def check_code_style(diff_hunk: str, lang: str = "py") -> str:
    """Check a code diff for style violations: line length, trailing
    whitespace, blank-line conventions, missing docstrings, unused imports.
    Call this before giving any style feedback on a diff."""
    # MCP Phase 3: was a direct in-process call to check_style() (app/tools/
    # linter.py). Now goes over MCP to linter_server.py (MCP Phase 2), which
    # wraps that same untouched function - including its unsupported-language
    # handling, so no reduction logic needs to live here anymore.
    if LINTER_MCP_URL:
        return call_mcp_tool(
            tool_name="check_code_style", server_url=LINTER_MCP_URL,
            diff_hunk=diff_hunk, lang=lang,
        )
    return call_mcp_tool(
        tool_name="check_code_style", server_script=LINTER_MCP_SERVER,
        diff_hunk=diff_hunk, lang=lang,
    )


class StyleAgentState(TypedDict):
    """
    The state that flows through the graph.

    `add_messages` is a reducer: instead of each node replacing `messages`
    wholesale, LangGraph appends new messages onto the existing list. This
    is what lets the agent node "remember" the tool result the next time
    it runs, without us wiring memory manually.
    """
    messages: Annotated[list, add_messages]


def build_style_agent():
    """Compile the Style Agent graph. Call once, reuse the returned app."""
    tools = [check_code_style]
    llm_with_tools = bind_tools_with_fallback(tools, temperature=0.3)

    def agent_node(state: StyleAgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: StyleAgentState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return "end"

    graph = StateGraph(StyleAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))

    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_style_review(diff_hunk: str, old_file: str = "", lang: str = "py", session_id: str = None) -> str:
    """
    Run the Style Agent on one diff and return its final review comment.

    Builds a fresh graph per call for now (cheap - it's just wiring, no
    network calls happen until .invoke()). We can cache the compiled graph
    later if this becomes a bottleneck.
    """
    app = build_style_agent()

    user_prompt = f"""Review this diff for STYLE issues only.

Language: {lang}

Original file (context, may be truncated):
{old_file[:500]}

Diff:
{diff_hunk}
"""

    initial_state = {
        "messages": [
            SystemMessage(content=STYLE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    }

    final_state = app.invoke(initial_state, config=invoke_config(session_id))
    return extract_text(final_state["messages"][-1])


def extract_text(message) -> str:
    """
    Normalize a message's content to plain text.

    Newer Gemini responses (via langchain-google-genai) return `.content`
    as a list of content blocks (e.g. [{'type': 'text', 'text': '...'}])
    instead of a plain string, so a raw `.content` access leaks the block
    structure into what should be a human-readable review comment.
    """
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)
