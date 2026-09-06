"""
Swappable LLM provider configuration.

Design decision: All agents call get_llm() instead of instantiating
ChatGoogleGenerativeAI directly. This means switching providers (Gemini -> Groq
-> local Ollama) later only requires changing this one file, not every agent.

Provider is selected via LLM_PROVIDER env var (defaults to 'gemini').
Only 'gemini' is implemented in Phase 3 - Groq/Ollama branches are added
later if free-tier rate limits become a blocker (see plan.md constraints).
"""
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def get_llm(temperature: float = 0.3, provider: str = None):
    """
    Return a configured chat model, provider-agnostic to calling code.

    Args:
        temperature: Sampling temperature. Lower = more consistent/focused
            output, which we want for code review (not creative writing).
        provider: Override the LLM_PROVIDER env var for this call.

    Returns:
        A LangChain chat model with .bind_tools() support.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")

        return ChatGoogleGenerativeAI(
            model=DEFAULT_GEMINI_MODEL,
            api_key=api_key,
            temperature=temperature,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{provider}'. Only 'gemini' is implemented so far."
    )
