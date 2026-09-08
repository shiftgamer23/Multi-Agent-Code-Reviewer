"""
Swappable LLM provider configuration, with automatic Gemini -> Groq fallback.

Design decision: All agents call get_llm()/get_llm_with_fallback()/
bind_tools_with_fallback() instead of instantiating a provider's chat model
directly. Switching or adding providers means changing this one file, not
every agent.

Why the fallback exists: Phase 6 eval hit Gemini's free-tier *daily* quota
(500 requests/day for gemini-3.5-flash-lite - separate from, and not fixed
by, the per-minute rate-limit pacing already used in eval/run_eval.py).
plan.md anticipated exactly this ("falling back to a locally-run open model
... if free-tier daily/rate limits become a blocker") - Groq is the first,
lighter-weight fallback before Ollama.

The fallback only triggers on ModelRateLimitError (langchain_core's
provider-agnostic exception for 429/quota errors), not on arbitrary
exceptions - a real bug in a request should surface, not get silently
masked by a switch to a different model.
"""
import os

from dotenv import load_dotenv
from langchain_core.exceptions import ModelRateLimitError

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"  # verified against this key's actual model list + tool-calling


def _build_gemini(temperature: float):
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    return ChatGoogleGenerativeAI(
        model=DEFAULT_GEMINI_MODEL,
        api_key=api_key,
        temperature=temperature,
    )


def _build_groq(temperature: float):
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")

    return ChatGroq(
        model=DEFAULT_GROQ_MODEL,
        api_key=api_key,
        temperature=temperature,
    )


def get_llm(temperature: float = 0.3, provider: str = None):
    """
    Return a single configured chat model, no fallback attached.

    Use this when you need direct control over one specific provider (e.g.
    testing Groq in isolation). Most call sites should use
    get_llm_with_fallback() or bind_tools_with_fallback() instead.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        return _build_gemini(temperature)
    if provider == "groq":
        return _build_groq(temperature)

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{provider}'. Supported: 'gemini', 'groq'."
    )


def get_llm_with_fallback(temperature: float = 0.3):
    """
    Gemini, automatically falling back to Groq if Gemini hits a rate/quota
    limit. For plain (no-tool-binding) calls - e.g. the supervisor's merge
    step, the eval judge.
    """
    primary = _build_gemini(temperature)
    fallback = _build_groq(temperature)
    return primary.with_fallbacks(
        [fallback], exceptions_to_handle=(ModelRateLimitError,)
    )


def bind_tools_with_fallback(tools: list, temperature: float = 0.3):
    """
    Same Gemini -> Groq fallback, but for tool-calling agents.

    RunnableWithFallbacks (what .with_fallbacks() returns) has no
    .bind_tools() method - only BaseChatModel does - so tools must be bound
    to *each* model individually before combining them with a fallback,
    rather than binding once afterward.
    """
    primary = _build_gemini(temperature).bind_tools(tools)
    fallback = _build_groq(temperature).bind_tools(tools)
    return primary.with_fallbacks(
        [fallback], exceptions_to_handle=(ModelRateLimitError,)
    )
