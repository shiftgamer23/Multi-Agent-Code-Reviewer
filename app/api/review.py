"""
Review API endpoints.

POST /review                -> checks the diff-content cache first (Phase 7).
                                On a cache hit: marks the run complete
                                immediately, zero LLM calls. On a miss:
                                registers the run AND immediately kicks off
                                a BackgroundTasks job that runs the graph -
                                unlike Phase 5, the graph no longer waits
                                for /stream to trigger it.
GET  /review/{run_id}/stream -> subscribes to that run's Redis Pub/Sub
                                channel and forwards events as SSE. If the
                                run already finished (cache hit, or it
                                completed before this connected), replays
                                the final state immediately instead of
                                waiting on messages that already fired.
GET  /review/{run_id}       -> fetch the current/final stored result.
"""
import json
from typing import Iterator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.supervisor_graph import build_supervisor_graph
from app.infra.cache import compute_diff_hash, get_cached_review, set_cached_review
from app.infra.logging import get_logger
from app.infra.pubsub import publish_event, subscribe_events
from app.infra.store import create_run, get_request, get_result, update_result
from app.infra.tracing import get_langfuse_client, invoke_config
from app.models.review import ReviewCreatedResponse, ReviewRequest, ReviewResult

router = APIRouter(prefix="/review", tags=["review"])
logger = get_logger(__name__)

REVIEW_FIELDS = ["style_review", "security_review", "test_review", "final_review"]
# Maps each ReviewResult field to the SSE event name it's replayed under,
# matching the node names the supervisor graph itself emits during .stream().
FIELD_TO_EVENT = {
    "style_review": "style",
    "security_review": "security",
    "test_review": "test_coverage",
    "final_review": "merge",
}


@router.post("", response_model=ReviewCreatedResponse)
def submit_review(payload: ReviewRequest, background_tasks: BackgroundTasks) -> ReviewCreatedResponse:
    run_id = create_run(payload)
    diff_hash = compute_diff_hash(payload.diff_hunk, payload.old_file, payload.lang)

    cached = get_cached_review(diff_hash)
    if cached is not None:
        logger.info("Cache hit for run %s (diff_hash=%s...)", run_id, diff_hash[:12])
        update_result(run_id, status="complete", **cached)
        publish_event(run_id, "status", {"status": "complete", "cached": True})
        _log_cache_status(run_id, "hit")
        return ReviewCreatedResponse(run_id=run_id)

    logger.info("Cache miss for run %s - starting background review", run_id)
    _log_cache_status(run_id, "miss")
    background_tasks.add_task(_run_review_task, run_id, payload, diff_hash)
    return ReviewCreatedResponse(run_id=run_id)


def _log_cache_status(run_id: str, status: str) -> None:
    """Log cache hit/miss as a Langfuse score (Phase 8), grouped by run_id.
    No-op if Langfuse isn't configured."""
    client = get_langfuse_client()
    if client is None:
        return
    client.create_score(
        name="cache_status",
        value=status,
        session_id=run_id,
        data_type="CATEGORICAL",
    )


def _run_review_task(run_id: str, request: ReviewRequest, diff_hash: str) -> None:
    """Runs in FastAPI's background threadpool - the graph now executes
    immediately on submission, not only when /stream is consumed."""
    update_result(run_id, status="running")
    publish_event(run_id, "status", {"status": "running"})

    graph = build_supervisor_graph()
    initial_state = {
        "diff_hunk": request.diff_hunk,
        "old_file": request.old_file,
        "lang": request.lang,
        "style_review": None,
        "security_review": None,
        "test_review": None,
        "final_review": None,
        "run_id": run_id,
    }

    for step in graph.stream(initial_state, stream_mode="updates", config=invoke_config(run_id)):
        for node_name, node_output in step.items():
            update_result(run_id, **node_output)
            publish_event(run_id, node_name, node_output)
            logger.info("Run %s: node '%s' completed", run_id, node_name)

    final_result = get_result(run_id)
    set_cached_review(diff_hash, {f: getattr(final_result, f) for f in REVIEW_FIELDS})

    update_result(run_id, status="complete")
    publish_event(run_id, "status", {"status": "complete"})


@router.get("/{run_id}", response_model=ReviewResult)
def fetch_review(run_id: str) -> ReviewResult:
    result = get_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")
    return result


@router.get("/{run_id}/stream")
def stream_review(run_id: str) -> StreamingResponse:
    if get_result(run_id) is None:
        raise HTTPException(status_code=404, detail="Unknown run_id")

    return StreamingResponse(_watch_run(run_id), media_type="text/event-stream")


def _watch_run(run_id: str) -> Iterator[str]:
    # Subscribe BEFORE checking stored state, so events published in the
    # gap between the check and the subscribe call aren't missed.
    pubsub = subscribe_events(run_id)
    try:
        result = get_result(run_id)
        if result and result.status == "complete":
            for field in REVIEW_FIELDS:
                val = getattr(result, field)
                if val is not None:
                    yield _sse_event(FIELD_TO_EVENT[field], {field: val})
            yield _sse_event("status", {"status": "complete"})
            return

        yield _sse_event("status", {"status": result.status if result else "pending"})

        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            payload = json.loads(message["data"])
            yield _sse_event(payload["event"], payload["data"])
            if payload["event"] == "status" and payload["data"].get("status") == "complete":
                break
    finally:
        pubsub.close()


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
