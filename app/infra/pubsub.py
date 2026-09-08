"""
Per-run Redis Pub/Sub channel: the background task (app/api/review.py)
publishes each node's completion here; GET /review/{id}/stream subscribes
and forwards messages as SSE. This is what lets /stream observe a run that
POST /review already kicked off in the background, instead of /stream
itself being the thing that triggers execution (Phase 5's design).
"""
import json

from app.infra.redis_client import get_redis


def _channel(run_id: str) -> str:
    return f"review:{run_id}:events"


def publish_event(run_id: str, event: str, data: dict) -> None:
    get_redis().publish(_channel(run_id), json.dumps({"event": event, "data": data}))


def subscribe_events(run_id: str):
    """Returns a redis PubSub object already subscribed to this run's channel."""
    pubsub = get_redis().pubsub()
    pubsub.subscribe(_channel(run_id))
    return pubsub
