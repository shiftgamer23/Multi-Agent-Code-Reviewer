"""Request/response models for the /review endpoints."""
from typing import Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    """Body for POST /review."""
    old_file: str = Field(default="", description="Full original file content before the change")
    diff_hunk: str = Field(..., description="Unified diff showing the code change")
    lang: str = Field(default="py", description="Programming language, e.g. 'py', 'js'")


class ReviewCreatedResponse(BaseModel):
    """Response for POST /review - just the run ID, the graph hasn't run yet."""
    run_id: str


class ReviewResult(BaseModel):
    """Current or final state of one review run, returned by GET /review/{run_id}."""
    run_id: str
    status: str = "pending"  # "pending" | "running" | "complete"
    style_review: Optional[str] = None
    security_review: Optional[str] = None
    test_review: Optional[str] = None
    final_review: Optional[str] = None
