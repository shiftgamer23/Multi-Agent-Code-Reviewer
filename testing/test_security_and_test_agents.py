"""
Manual test of the Security Agent and Test-Coverage Agent (Phase 4) against
real dev-slice examples. Same sanity-check approach as test_style_agent.py:
not scoring against ground truth yet (Phase 6), just confirming each agent
calls its tool and produces focused, in-lane feedback.

Run: .\\venv\\Scripts\\python.exe test_security_and_test_agents.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.security_agent import run_security_review
from app.agents.test_coverage_agent import run_test_coverage_review

DEV_SLICE = Path(__file__).parent.parent / "data" / "processed" / "dev_valid_slice.jsonl"


def load_python_examples(n: int = 3):
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
    examples = load_python_examples(n=3)
    print(f"Loaded {len(examples)} Python examples from dev slice.\n")

    for i, ex in enumerate(examples, start=1):
        print("=" * 70)
        print(f"EXAMPLE {i} (id={ex['id']}, proj={ex['proj']})")
        print("=" * 70)
        print(f"\n--- Diff (patch) ---\n{ex['patch'][:400]}")
        print(f"\n--- Real human comment (ground truth) ---\n{ex['msg']}")

        security_review = run_security_review(
            diff_hunk=ex["patch"], old_file=ex.get("oldf", ""), lang=ex["lang"]
        )
        print(f"\n--- Security Agent output ---\n{security_review}")

        test_review = run_test_coverage_review(
            diff_hunk=ex["patch"], old_file=ex.get("oldf", ""), lang=ex["lang"]
        )
        print(f"\n--- Test-Coverage Agent output ---\n{test_review}\n")


if __name__ == "__main__":
    main()
