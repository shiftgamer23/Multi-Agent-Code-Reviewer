"""
Manual test of the Style Agent (Phase 3) against real dev-slice examples.

This is NOT scoring against ground truth yet (that's Phase 6). It's a
sanity check: does the agent call the tool, and does it produce focused,
sensible style feedback?

Run: python testing/test_style_agent.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.style_agent import run_style_review

DEV_SLICE = Path(__file__).parent.parent / "data" / "processed" / "dev_valid_slice.jsonl"


def load_python_examples(n: int = 5):
    """Load the first n Python examples from the dev slice."""
    examples = []
    with open(DEV_SLICE, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record.get("lang") == "py":
                examples.append(record)
            if len(examples) >= n:
                break
    return examples


def main():
    examples = load_python_examples(n=5)
    print(f"Loaded {len(examples)} Python examples from dev slice.\n")

    for i, ex in enumerate(examples, start=1):
        print("=" * 70)
        print(f"EXAMPLE {i} (id={ex['id']}, proj={ex['proj']})")
        print("=" * 70)
        print(f"\n--- Diff (patch) ---\n{ex['patch'][:400]}")
        print(f"\n--- Real human comment (ground truth) ---\n{ex['msg']}")

        review = run_style_review(
            diff_hunk=ex["patch"],
            old_file=ex.get("oldf", ""),
            lang=ex["lang"],
        )

        print(f"\n--- Style Agent output ---\n{review}\n")


if __name__ == "__main__":
    main()
