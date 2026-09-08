"""
Shared Redis client. One connection pool per process, lazily created.

Host/port come from env vars so this points at a local Docker container
today and a docker-compose service in Phase 9 without code changes.
"""
import os

import redis

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )
    return _client
