"""
Phase 6: Evaluate the full pipeline against real human reviewer comments.

Runs every example in the LOCKED final_eval_slice.jsonl (untouched since
Phase 1) through the supervisor graph, then scores the generated review
against the real human `msg` via LLM-as-judge + a word-overlap heuristic.

Rate-limit pacing: each example costs ~8 LLM calls (7 for the full review
- 2 per specialist agent x 3, plus 1 merge - + 1 for judging). Gemini's
free tier allows 15 requests/minute for gemini-3.5-flash-lite, so we pace
one example at a time with a delay between them rather than adding
retry/backoff logic (see PHASE_4_COMPLETE.md for why retry logic was
deliberately deferred).

Results are written to disk after every example (not just at the end), so
an interrupted run can be resumed by re-running with the same --output
file - already-scored examples are skipped.

Run: .\\venv\\Scripts\\python.exe -m eval.run_eval [--limit N] [--delay SECONDS] [--output FILE]
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agents.supervisor_graph import run_full_review
from eval.scoring import judge_review, word_overlap_score

EVAL_SLICE = Path(__file__).parent.parent / "data" / "processed" / "final_eval_slice.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


def load_eval_examples() -> list[dict]:
    examples = []
    with open(EVAL_SLICE, "r", encoding="utf-8") as f:
        for line in f:
            examples.append(json.loads(line))
    return examples


def load_existing_results(results_path: Path) -> dict:
    """Resume support: load already-scored examples (keyed by dataset id) from a prior run."""
    if not results_path.exists():
        return {}
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {r["id"]: r for r in data.get("results", [])}


def compute_summary(results: list[dict]) -> dict:
    total = len(results)
    match_count = sum(1 for r in results if r["judge_verdict"] == "MATCH")
    partial_count = sum(1 for r in results if r["judge_verdict"] == "PARTIAL")
    error_count = sum(1 for r in results if r["judge_verdict"] == "ERROR")
    avg_overlap = sum(r["overlap_score"] for r in results) / total if total else 0.0

    return {
        "total_examples": total,
        "match_count": match_count,
        "partial_count": partial_count,
        "no_match_count": total - match_count - partial_count - error_count,
        "error_count": error_count,
        "match_rate": round(match_count / total, 4) if total else 0.0,
        "match_or_partial_rate": round((match_count + partial_count) / total, 4) if total else 0.0,
        "avg_word_overlap": round(avg_overlap, 4),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_results(results_path: Path, results: list[dict]) -> dict:
    summary = compute_summary(results)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N examples")
    parser.add_argument("--delay", type=float, default=40.0, help="Seconds to wait between examples")
    parser.add_argument("--output", type=str, default="eval_results.json", help="Output filename under eval/results/")
    args = parser.parse_args()

    examples = load_eval_examples()
    if args.limit:
        examples = examples[: args.limit]

    results_path = RESULTS_DIR / args.output
    existing_all = load_existing_results(results_path)
    # Errored examples (e.g. transient rate-limit hits) are dropped here so
    # they get retried on resume, instead of being permanently skipped.
    existing = {k: v for k, v in existing_all.items() if v["judge_verdict"] != "ERROR"}
    results = list(existing.values())

    print(f"Loaded {len(examples)} eval examples ({len(existing)} already scored, resuming from '{results_path.name}').")

    for i, ex in enumerate(examples, start=1):
        ex_id = ex["id"]
        if ex_id in existing:
            print(f"[{i}/{len(examples)}] id={ex_id} - already scored, skipping")
            continue

        print(f"[{i}/{len(examples)}] id={ex_id} (proj={ex['proj']}, lang={ex['lang']}) - running full review...")

        try:
            final_state = run_full_review(
                diff_hunk=ex["patch"], old_file=ex.get("oldf", ""), lang=ex["lang"]
            )
            final_review = final_state.get("final_review") or ""
            human_comment = ex["msg"]

            judge = judge_review(final_review, human_comment)
            overlap = word_overlap_score(final_review, human_comment)

            result = {
                "id": ex_id,
                "proj": ex["proj"],
                "lang": ex["lang"],
                "human_comment": human_comment,
                "final_review": final_review,
                "judge_verdict": judge["verdict"],
                "judge_reason": judge["reason"],
                "overlap_score": round(overlap, 4),
            }
            print(f"    -> judge: {judge['verdict']} ({judge['reason']})")
            print(f"    -> word overlap: {overlap:.2f}")

        except Exception as e:
            print(f"    -> ERROR: {e}")
            result = {
                "id": ex_id,
                "proj": ex["proj"],
                "lang": ex["lang"],
                "human_comment": ex["msg"],
                "final_review": None,
                "judge_verdict": "ERROR",
                "judge_reason": str(e),
                "overlap_score": 0.0,
            }

        results.append(result)
        existing[ex_id] = result

        # Save after every example - crash-safe, resumable.
        summary = save_results(results_path, results)

        if i < len(examples):
            print(f"    sleeping {args.delay}s before next example...")
            time.sleep(args.delay)

    print("\n" + "=" * 70)
    print("EVAL COMPLETE")
    print("=" * 70)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
