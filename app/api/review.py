"""
Review API endpoints.

POST /review               -> register a pending run, return its run_id.
                               Does NOT execute the graph - see /stream.
GET  /review/{run_id}/stream -> SSE endpoint: runs the supervisor graph via
                               .stream(stream_mode="updates"), forwarding
                               each agent's output the moment it completes,
                               and persisting progress to the store as it goes.
GET  /review/{run_id}      -> fetch the current/final stored result
                               (works whether or not /stream has been called
                               yet - status will just be "pending").
"""
import json
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.supervisor_graph import build_supervisor_graph
from app.infra.logging import get_logger
from app.infra.store import create_run, get_request, get_result, update_result
from app.models.review import ReviewCreatedResponse, ReviewRequest, ReviewResult

router = APIRouter(prefix="/review", tags=["review"])
logger = get_logger(__name__)


@router.post("", response_model=ReviewCreatedResponse)
def submit_review(payload: ReviewRequest) -> ReviewCreatedResponse:
    run_id = create_run(payload)
    logger.info("Created review run %s", run_id)
    return ReviewCreatedResponse(run_id=run_id)


@router.get("/{run_id}", response_model=ReviewResult)
def fetch_review(run_id: str) -> ReviewResult:
    result = get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return result


@router.get("/{run_id}/stream")
def stream_review(run_id: str) -> StreamingResponse:
    request = get_request(run_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")

    return StreamingResponse(
        _run_and_stream(run_id, request), media_type="text/event-stream"
    )


def _run_and_stream(run_id: str, request: ReviewRequest) -> Iterator[str]:
    logger.info("Starting stream for run %s", run_id)
    update_result(run_id, status="running")
    yield _sse_event("status", {"status": "running"})

    graph = build_supervisor_graph()
    initial_state = {
        "diff_hunk": request.diff_hunk,
        "old_file": request.old_file,
        "lang": request.lang,
        "style_review": None,
        "security_review": None,
        "test_review": None,
        "final_review": None,
    }

    # stream_mode="updates" emits {node_name: node_output} the moment each
    # node finishes, instead of waiting for the whole graph like .invoke().
    for step in graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in step.items():
            update_result(run_id, **node_output)
            logger.info("Run %s: node '%s' completed", run_id, node_name)
            yield _sse_event(node_name, node_output)

    update_result(run_id, status="complete")
    yield _sse_event("status", {"status": "complete"})


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
