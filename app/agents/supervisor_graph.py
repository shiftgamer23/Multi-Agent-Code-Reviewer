"""
Supervisor graph (Phase 4): ties Style, Security, and Test-Coverage agents
together into one end-to-end review pipeline.

Flow:

    START -> route() -> fan out to relevant agents (parallel) -> merge -> END
                      -> skip -> END   (unsupported lang / docs-only diff)

`route` (app/agents/router.py) is plain Python - no LLM call, so deciding
which agents are relevant costs nothing against free-tier rate limits.
`merge` is the one new LLM call this graph adds: it synthesizes whichever
specialist reviews ran into one coherent PR comment.

Each of style/security/test_coverage below invokes that agent's own,
already-compiled ReAct graph (its internal agent<->tools loop from Phase 3
/ Phase 4) as a single step in *this* graph - the supervisor doesn't know
or care that Style Agent might loop through its tool multiple times
internally; it just waits for that node to return.
"""
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.react_agent_factory import extract_text
from app.agents.router import decide_which_agents
from app.agents.security_agent import run_security_review
from app.agents.style_agent import run_style_review
from app.agents.test_coverage_agent import run_test_coverage_review
from app.infra.tracing import invoke_config
from app.llm import get_llm_with_fallback


class SupervisorState(TypedDict):
    diff_hunk: str
    old_file: str
    lang: str
    style_review: Optional[str]
    security_review: Optional[str]
    test_review: Optional[str]
    final_review: Optional[str]
    run_id: Optional[str]  # groups this run's agent traces in Langfuse (Phase 8)


def _style_node(state: SupervisorState) -> dict:
    review = run_style_review(
        state["diff_hunk"], state.get("old_file", ""), state["lang"], session_id=state.get("run_id")
    )
    return {"style_review": review}


def _security_node(state: SupervisorState) -> dict:
    review = run_security_review(
        state["diff_hunk"], state.get("old_file", ""), state["lang"], session_id=state.get("run_id")
    )
    return {"security_review": review}


def _test_coverage_node(state: SupervisorState) -> dict:
    review = run_test_coverage_review(
        state["diff_hunk"], state.get("old_file", ""), state["lang"], session_id=state.get("run_id")
    )
    return {"test_review": review}


def _skip_node(state: SupervisorState) -> dict:
    return {
        "final_review": "No review needed (unsupported language or docs-only change)."
    }


def _merge_node(state: SupervisorState) -> dict:
    """The one LLM call this graph adds: synthesize the specialist reviews
    that actually ran into one coherent PR comment."""
    parts = []
    if state.get("style_review"):
        parts.append(f"[Style] {state['style_review']}")
    if state.get("security_review"):
        parts.append(f"[Security] {state['security_review']}")
    if state.get("test_review"):
        parts.append(f"[Test Coverage] {state['test_review']}")

    prompt = (
        "These are independent specialist review comments on the same code diff:\n\n"
        + "\n".join(parts)
        + "\n\nCombine them into one coherent PR review comment. Remove "
        "redundant points, lead with the most important issue, keep it "
        "concise (3-5 sentences). If a specialist found nothing notable, "
        "don't mention them explicitly."
    )

    llm = get_llm_with_fallback(temperature=0.3)
    response = llm.invoke(prompt, config=invoke_config(state.get("run_id")))
    return {"final_review": extract_text(response)}


def _route(state: SupervisorState) -> list:
    return decide_which_agents(state["diff_hunk"], state["lang"])


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("style", _style_node)
    graph.add_node("security", _security_node)
    graph.add_node("test_coverage", _test_coverage_node)
    graph.add_node("skip", _skip_node)
    graph.add_node("merge", _merge_node)

    graph.set_conditional_entry_point(
        _route,
        {
            "style": "style",
            "security": "security",
            "test_coverage": "test_coverage",
            "skip": "skip",
        },
    )

    # Fan-in: merge only runs once every branch the router actually
    # triggered for this run has completed.
    graph.add_edge("style", "merge")
    graph.add_edge("security", "merge")
    graph.add_edge("test_coverage", "merge")

    graph.add_edge("skip", END)
    graph.add_edge("merge", END)

    return graph.compile()


def run_full_review(diff_hunk: str, old_file: str = "", lang: str = "py", run_id: str = None) -> dict:
    """
    Run the full supervisor pipeline on one diff.

    Returns the final state dict so callers (e.g. FastAPI in Phase 5) can
    show both the merged review and each specialist's individual output.
    `run_id`, if given, groups this run's agent traces under one Langfuse
    session (Phase 8) - purely observability, no effect on behavior.
    """
    app = build_supervisor_graph()
    initial_state: SupervisorState = {
        "diff_hunk": diff_hunk,
        "old_file": old_file,
        "lang": lang,
        "style_review": None,
        "security_review": None,
        "test_review": None,
        "final_review": None,
        "run_id": run_id,
    }
    return app.invoke(initial_state, config=invoke_config(run_id))
