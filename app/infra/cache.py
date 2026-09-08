"""
Content-addressed cache: an identical diff never re-triggers the LLM
pipeline. This is the core of Phase 7 - both a latency/cost optimization
and, given the free-tier-only LLM constraint (see PHASE_6_COMPLETE.md's
daily-quota discovery), a real protection against burning through rate
limits on repeated/eval runs over unchanged diffs.

Cache key = SHA-256 hash of (lang, old_file, diff_hunk). Only the review
content is cached here (style/security/test/final) - not run-tracking
metadata like run_id or status, which belongs to app.infra.store instead.
"""
import hashlib
import json
from typing import Optional

from app.infra.redis_client import get_redis

CACHE_PREFIX = "diffcache:"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def compute_diff_hash(diff_hunk: str, old_file: str, lang: str) -> str:
    """Normalize inputs into one hash so identical requests hit the same key."""
    normalized = f"{lang}\x00{old_file}\x00{diff_hunk}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_review(diff_hash: str) -> Optional[dict]:
    raw = get_redis().get(f"{CACHE_PREFIX}{diff_hash}")
    return json.loads(raw) if raw is not None else None


def set_cached_review(diff_hash: str, review_fields: dict) -> None:
    get_redis().set(
        f"{CACHE_PREFIX}{diff_hash}", json.dumps(review_fields), ex=CACHE_TTL_SECONDS
    )
