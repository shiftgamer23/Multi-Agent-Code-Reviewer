"""
End-to-end test of the supervisor graph (Phase 4) against real dev-slice
examples: route -> fan out to relevant agents -> merge into one review.

Run: .\\venv\\Scripts\\python.exe test_supervisor_graph.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.supervisor_graph import run_full_review

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
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    examples = load_python_examples(n=n)
    print(f"Loaded {len(examples)} Python examples from dev slice.\n")

    for i, ex in enumerate(examples, start=1):
        print("=" * 70)
        print(f"EXAMPLE {i} (id={ex['id']}, proj={ex['proj']})")
        print("=" * 70)
        print(f"\n--- Diff (patch) ---\n{ex['patch'][:400]}")
        print(f"\n--- Real human comment (ground truth) ---\n{ex['msg']}")

        final_state = run_full_review(
            diff_hunk=ex["patch"], old_file=ex.get("oldf", ""), lang=ex["lang"]
        )

        print(f"\n--- Individual specialist outputs ---")
        print(f"Style:         {final_state.get('style_review')}")
        print(f"Security:      {final_state.get('security_review')}")
        print(f"Test Coverage: {final_state.get('test_review')}")

        print(f"\n--- MERGED FINAL REVIEW ---\n{final_state.get('final_review')}\n")


if __name__ == "__main__":
    main()
