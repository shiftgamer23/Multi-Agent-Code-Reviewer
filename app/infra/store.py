"""
Run store: tracks each review run's input request and evolving result.

Deliberately a plain in-process dict for Phase 5 - swapped for Redis in
Phase 7, which is when persistence across restarts and cross-process
access actually starts to matter. Keeping get/update as the only interface
here means Phase 7 only needs to change this file, not the API layer.
"""
import uuid
from dataclasses import dataclass
from typing import Optional

from app.models.review import ReviewRequest, ReviewResult


@dataclass
class _RunRecord:
    request: ReviewRequest
    result: ReviewResult


_RUNS: dict[str, _RunRecord] = {}


def create_run(request: ReviewRequest) -> str:
    """Register a new pending run and return its ID. Does not execute anything."""
    run_id = str(uuid.uuid4())
    _RUNS[run_id] = _RunRecord(
        request=request,
        result=ReviewResult(run_id=run_id, status="pending"),
    )
    return run_id


def get_request(run_id: str) -> Optional[ReviewRequest]:
    record = _RUNS.get(run_id)
    return record.request if record else None


def get_result(run_id: str) -> Optional[ReviewResult]:
    record = _RUNS.get(run_id)
    return record.result if record else None


def update_result(run_id: str, **fields) -> Optional[ReviewResult]:
    """Merge `fields` into the stored result (e.g. status='running', style_review='...')."""
    record = _RUNS.get(run_id)
    if record is None:
        return None
    record.result = record.result.model_copy(update=fields)
    return record.result
