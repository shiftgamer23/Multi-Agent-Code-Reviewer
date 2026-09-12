# Phase 6: Evaluation Against Real Human Comments ✓ COMPLETE

## What We Built

- `eval/scoring.py` — `judge_review()` (LLM-as-judge: MATCH/PARTIAL/NO_MATCH
  against the real human `msg`) + `word_overlap_score()` (cheap Jaccard
  overlap, secondary signal, no LLM call)
- `eval/run_eval.py` — repeatable script over the locked 100-example
  `final_eval_slice.jsonl`, with:
  - Batching/delay pacing (not retry/backoff) to respect Gemini's
    per-minute free-tier limit
  - Crash-safe incremental saves (writes after every example) and resume
    support (skips already-scored examples, retries only real errors)

## Bugs Found and Fixed Along the Way

1. **Language-gap fabrication** (style_agent.py, security_agent.py): agents
   were claiming "clean, no issues" for languages their tools don't
   support, instead of admitting the check never ran. Fixed by having the
   tool wrappers detect `unsupported_language` and return an explicit
   "not available" signal the agent can't misread as a clean bill of health.
2. **Resume logic permanently skipped errored examples** instead of
   retrying them - fixed so only successfully-scored examples count as done.
3. **66/100 locked eval examples were being skipped entirely** - the
   dataset spans 9 languages (`py, js, java, go, rb, .cs, c, cpp, php`);
   `SUPPORTED_LANGS` only covered 4. Expanded `test_detector.py`'s file
   patterns and widened `security_checker.py`'s language allowlist to
   cover all 9 (most of those patterns were already language-agnostic
   regex, just gated too narrowly). Left `check_style` Python-only - PEP8
   rules don't have a direct equivalent in e.g. Go.
4. **Gemini's free tier has a *daily* quota (500 req/day for
   gemini-3.5-flash-lite)**, separate from and not fixed by the
   per-minute pacing already in place. Added an automatic Gemini -> Groq
   fallback (`app/llm/model_config.py`: `get_llm_with_fallback()`,
   `bind_tools_with_fallback()`), triggered only on
   `ModelRateLimitError` (not arbitrary exceptions, so real bugs still
   surface). Verified working end-to-end while Gemini was genuinely
   exhausted. Known accepted inefficiency: because fallback is applied
   per-`.invoke()` call rather than per-conversation, a multi-turn agent
   re-attempts Gemini every turn even after already falling back once,
   which is slower but not incorrect - left as-is (Option A) since it only
   matters during the rare exhausted-quota window.

## Final Results (100/100 scored, 0 errors)

```
match_rate: 3%          (3/100 - LLM judge says it addresses the same issue)
match_or_partial_rate: 4%  (4/100)
avg_word_overlap: 0.0575   (secondary heuristic, consistently low)
```

### By coverage tier

| Tier | n | Match rate | Match-or-partial |
|---|---|---|---|
| Full signal (Python - style+security+tests all real) | 8 | 0% | 12.5% |
| Partial signal (other 8 languages - test+security real, style unavailable) | 92 | 3.3% | 3.3% |

### By language

| Lang | n | Match | Partial |
|---|---|---|---|
| go | 27 | 0 | 0 |
| java | 20 | 2 | 0 |
| rb | 13 | 0 | 0 |
| .cs | 12 | 1 | 0 |
| py | 8 | 0 | 1 |
| c | 7 | 0 | 0 |
| js | 6 | 0 | 0 |
| cpp | 4 | 0 | 0 |
| php | 3 | 0 | 0 |

## Root Cause of the Low Match Rate (this is the real finding)

All 4 MATCH/PARTIAL cases share one thing: **the human reviewer's actual
concern happened to be about test coverage** - e.g. *"do we have positive
test covered somewhere?"*, *"don't we have tests to change after this
breaking change?"*. That's the one dimension our system reliably checks.

Everywhere else, the pattern is consistent across dozens of NO_MATCH
reasons: human reviewers are raising **logic bugs, architecture/API design
questions, and domain-specific correctness concerns** -
*"I don't think this will actually align the indexes..."*,
*"Shouldn't we actually inherit from the kinto-core UUID4 generator..."*,
*"I'm a little concerned about relying on a private module..."* - while our
system's specialist agents can only ever report on the three narrow,
pattern-detectable lanes they were built for (style patterns, security
patterns, presence/absence of test files). No agent in this system is
equipped to reason about whether the *logic* of a change is correct, only
whether it matches a checklist of surface patterns.

This is not a scoring bug or an eval-methodology flaw - it's an honest,
structural finding about the ceiling of this architecture: **a multi-agent
system built on shallow heuristic tools can reliably catch checklist-style
issues (style, security anti-patterns, missing tests), but cannot
replicate the deep code comprehension a human reviewer brings to bear on
correctness and design.** Getting a suspiciously high match rate here
would have been more concerning than this result - it would suggest either
an eval methodology that's too lenient, or a judge prompt that's grading on
vibes rather than substance.

## Files Created/Modified

- `eval/scoring.py`, `eval/run_eval.py` (new)
- `eval/results/eval_results.json` (100 scored examples + summary)
- `app/llm/model_config.py`, `app/llm/__init__.py` (Groq fallback)
- `app/agents/style_agent.py`, `security_agent.py`, `react_agent_factory.py`,
  `supervisor_graph.py` (fallback wiring)
- `app/agents/router.py`, `app/tools/test_detector.py`,
  `app/tools/security_checker.py` (language expansion)
- `requirements.txt` (added `langchain-groq`)

## Next: Phase 7 - Redis Caching

Cache full review results keyed on a normalized diff hash. Also the point
where `POST /review` switches to FastAPI `BackgroundTasks` (see saved
memory `phase7_background_tasks_fix.md`) so the graph starts executing
immediately on submission instead of waiting for `/stream`.
