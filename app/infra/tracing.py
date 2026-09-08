"""
Langfuse observability (Phase 8).

Deliberately optional: if LANGFUSE_PUBLIC_KEY isn't set, get_langfuse_handler()
returns None and every call site just skips passing callbacks - the app
works identically with or without Langfuse configured, so this can't break
anything for anyone who hasn't set up an account yet.

Uses Langfuse's LangChain CallbackHandler, which auto-instruments every
LLM call and tool call as a trace/span via LangChain's existing callback
system - no manual span-management code needed in any agent.
"""
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_handler = None
_client = None


def _ensure_host_env_var() -> None:
    """
    The SDK only reads LANGFUSE_HOST for the endpoint URL - it does not
    recognize LANGFUSE_BASE_URL. Accept the latter as a fallback alias so a
    reasonably-named env var still works instead of silently falling back
    to the default cloud.langfuse.com host.
    """
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]


def get_langfuse_handler():
    """Shared CallbackHandler, or None if Langfuse isn't configured."""
    global _handler
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return None
    if _handler is None:
        _ensure_host_env_var()
        from langfuse.langchain import CallbackHandler

        _handler = CallbackHandler()
    return _handler


def invoke_config(session_id: Optional[str] = None) -> dict:
    """
    Build a LangChain `config` dict with the Langfuse callback attached (if
    configured). `session_id` (typically the API's run_id) groups every
    agent's trace from one review under the same session in the Langfuse
    dashboard - `langfuse_session_id` is the specific metadata key the
    CallbackHandler looks for. Pass this as `config=...` to any
    .invoke()/.stream() call.
    """
    handler = get_langfuse_handler()
    config: dict = {}
    if handler is not None:
        config["callbacks"] = [handler]
        if session_id:
            config["metadata"] = {"langfuse_session_id": session_id}
    return config


def get_langfuse_client():
    """Raw Langfuse client, for logging standalone scores (Phase 6 eval,
    cache hit/miss) that aren't tied to a specific LangChain invocation.
    Returns None if Langfuse isn't configured."""
    global _client
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return None
    if _client is None:
        _ensure_host_env_var()
        from langfuse import get_client

        _client = get_client()
    return _client
