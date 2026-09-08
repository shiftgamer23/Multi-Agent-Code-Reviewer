"""
Run store: tracks each review run's input request and evolving result.

Moved from Phase 5's in-memory dict to Redis in Phase 7 - run state now
survives a server restart, and decouples the API process from whatever
runs the actual graph (relevant once BackgroundTasks and, later, Docker
Compose services are in the picture).
"""
import uuid
from typing import Optional

from app.infra.redis_client import get_redis
from app.models.review import ReviewRequest, ReviewResult

RUN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days - ephemeral run tracking, not the long-lived diff cache


def _request_key(run_id: str) -> str:
    return f"run:{run_id}:request"


def _result_key(run_id: str) -> str:
    return f"run:{run_id}:result"


def create_run(request: ReviewRequest) -> str:
    """Register a new pending run and return its ID. Does not execute anything."""
    run_id = str(uuid.uuid4())
    result = ReviewResult(run_id=run_id, status="pending")
    r = get_redis()
    r.set(_request_key(run_id), request.model_dump_json(), ex=RUN_TTL_SECONDS)
    r.set(_result_key(run_id), result.model_dump_json(), ex=RUN_TTL_SECONDS)
    return run_id


def get_request(run_id: str) -> Optional[ReviewRequest]:
    raw = get_redis().get(_request_key(run_id))
    return ReviewRequest.model_validate_json(raw) if raw is not None else None


def get_result(run_id: str) -> Optional[ReviewResult]:
    raw = get_redis().get(_result_key(run_id))
    return ReviewResult.model_validate_json(raw) if raw is not None else None


def update_result(run_id: str, **fields) -> Optional[ReviewResult]:
    """Merge `fields` into the stored result (e.g. status='running', style_review='...')."""
    current = get_result(run_id)
    if current is None:
        return None
    updated = current.model_copy(update=fields)
    get_redis().set(_result_key(run_id), updated.model_dump_json(), ex=RUN_TTL_SECONDS)
    return updated
