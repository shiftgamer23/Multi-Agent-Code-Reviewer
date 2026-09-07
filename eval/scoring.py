"""
Scoring functions for Phase 6 evaluation: compare a generated review against
the real human reviewer comment from the dataset.

Two signals, per plan.md:
1. judge_review() - LLM-as-judge: "does this address the same underlying
   issue?" This is the primary signal, since two reviews can be worded
   completely differently but flag the same real problem.
2. word_overlap_score() - a cheap secondary signal with no LLM call, so we
   have something to sanity-check the judge against.
"""
import re

from app.agents.react_agent_factory import extract_text
from app.llm import get_llm_with_fallback

JUDGE_PROMPT_TEMPLATE = """You are evaluating an AI-generated code review comment \
against a real human reviewer's comment left on the same code change.

Human reviewer's comment:
{human_comment}

AI-generated review:
{final_review}

Does the AI-generated review address the same underlying issue or concern \
as the human comment? Judge by substance, not wording - if both would lead \
a PR author to make a similar fix, that counts as a match even if phrased \
very differently.

Respond with EXACTLY one word on the first line: MATCH, PARTIAL, or NO_MATCH.
Then a one-sentence reason on the second line.
"""


def judge_review(final_review: str, human_comment: str) -> dict:
    """LLM-as-judge scoring. Returns {'verdict': 'MATCH'|'PARTIAL'|'NO_MATCH', 'reason': str}."""
    llm = get_llm_with_fallback(temperature=0.0)
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        human_comment=human_comment, final_review=final_review
    )
    response = llm.invoke(prompt)
    text = extract_text(response).strip()

    lines = text.split("\n", 1)
    verdict = lines[0].strip().upper()
    if verdict not in ("MATCH", "PARTIAL", "NO_MATCH"):
        verdict = "NO_MATCH"  # fail-safe if the model doesn't follow format
    reason = lines[1].strip() if len(lines) > 1 else ""

    return {"verdict": verdict, "reason": reason}


def word_overlap_score(text_a: str, text_b: str) -> float:
    """
    Jaccard similarity over lowercased word tokens - a cheap, no-LLM
    secondary signal. Not meant to be accurate on its own (two reviews
    about the same issue can share zero words), just a sanity-check
    alongside the judge's verdict.
    """
    def tokenize(s: str) -> set:
        return set(re.findall(r"[a-z0-9']+", s.lower()))

    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
