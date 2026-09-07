"""
Shared factory for single-tool ReAct agents.

Phase 3's Style Agent built the agent<->tools graph by hand, on purpose,
so the LangGraph mechanics were explicit while learning them. Security
Agent and Test-Coverage Agent need the exact same graph shape - one tool
bound, identical should_continue routing - just a different system prompt
and tool. Rather than copy-paste that wiring twice more, this factory
builds it once, parameterized by system prompt + tool function.

Graph shape (same as style_agent.py):

    START -> agent -> [tool_calls present?] -> yes -> tools -> agent (loop)
                                              -> no  -> END
"""
from typing import Annotated, Callable, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.llm import bind_tools_with_fallback


class ReactAgentState(TypedDict):
    """State shared by every single-tool ReAct agent built with this factory."""
    messages: Annotated[list, add_messages]


def extract_text(message) -> str:
    """
    Normalize a message's content to plain text.

    Gemini (via langchain-google-genai) returns `.content` as a list of
    content blocks (e.g. [{'type': 'text', 'text': '...'}]) rather than a
    plain string - see Phase 3 notes in style_agent.py for where this was
    first found.
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


def build_single_tool_agent(
    system_prompt: str,
    tool_fn: Callable,
    temperature: float = 0.3,
) -> Callable[[str], str]:
    """
    Compile a single-tool ReAct agent and return a `run(user_prompt) -> str`
    function - callers never touch the graph or message objects directly.
    """
    tools = [tool_fn]
    llm_with_tools = bind_tools_with_fallback(tools, temperature=temperature)

    def agent_node(state: ReactAgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: ReactAgentState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return "end"

    graph = StateGraph(ReactAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "end": END}
    )
    graph.add_edge("tools", "agent")

    compiled = graph.compile()

    def run(user_prompt: str) -> str:
        initial_state = {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        }
        final_state = compiled.invoke(initial_state)
        return extract_text(final_state["messages"][-1])

    return run
