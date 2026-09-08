# Phase 3: Style Agent (LangGraph) ✓ COMPLETE

## What We Built

The first LangGraph agent: a **Style Reviewer** that analyzes a diff for
style/readability issues only, using the `check_style` tool from Phase 2.

Files:
- `app/llm/model_config.py` — swappable `get_llm()` provider config
- `app/agents/style_agent.py` — the graph + agent logic
- `test_style_agent.py` — manual run against real dev-slice examples

## The Graph (ReAct pattern)

```
START -> agent -> [tool_calls present?] -> yes -> tools -> agent (loop)
                                          -> no  -> END
```

- **State**: `{"messages": [...]}`, using `add_messages` reducer so each
  node appends rather than overwrites.
- **`agent` node**: one call to `gemini-3.5-flash-lite` with `check_code_style`
  bound as a tool. The LLM itself decides per-turn whether to call the tool
  or answer.
- **`should_continue`**: plain Python — checks `last_message.tool_calls`,
  no second LLM call involved.
- **`tools` node**: LangGraph's prebuilt `ToolNode`, executes the requested
  tool and appends a `ToolMessage` with the result.
- **Loop-back edge**: `tools -> agent` lets the LLM see the tool result and
  produce its final text.

## Bug Found & Fixed: Content-Block Responses

`gemini-3.5-flash-lite` (via `langchain-google-genai` 4.4.0) returns
`.content` as a list of blocks (`[{'type': 'text', 'text': '...'}]`), not a
plain string. Added `extract_text()` helper in `style_agent.py` to normalize
this — otherwise the raw block structure leaked into what should be a plain
review comment.

## Verification Against Dev Slice

Ran on 3 real Python examples from `data/processed/dev_valid_slice.jsonl`:

1. **scapy example** — no real style issues in the diff → agent correctly
   said "No style violations found" (real human comment was an API-usage
   suggestion, correctly outside the Style Agent's scope).
2. **nvda example** — diff has trailing whitespace on a comment line →
   agent correctly caught it via the tool. This matches the exact `W291`
   check from `app/tools/linter.py`, confirming the tool was actually
   invoked (not hallucinated).
3. **kinto example** — clean removal, no style issues → agent correctly
   said so.

**Confirmed:**
- ✓ Agent reliably calls the tool before answering
- ✓ Output reflects real tool results, not guesses
- ✓ Agent stays focused on style only, ignores security/test/architecture
  concerns even when the diff invites broader commentary

## Known Limitation (expected, not a bug)

The dataset's ground-truth `msg` field is one undifferentiated human
comment per diff — it might be about API design, logging, or architecture,
not style. A style-only agent will often not match `msg` even when it's
behaving correctly. This is why Phase 6 eval needs to judge "did the agent
produce a *reasonable* review for its concern," not just string-match
against `msg`. Worth remembering when designing the Phase 6 LLM-judge
prompt.

## Next: Phase 4

Replicate this exact pattern for:
- **Security Agent** (`check_security` tool)
- **Test-Coverage Agent** (`check_test_coverage` tool)

Then build the supervisor graph that routes to relevant agents and merges
their findings into one coherent review.
