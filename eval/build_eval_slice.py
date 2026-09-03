"""
Stream-load CodeReviewer dataset and create small working slices.

Key principle: DO NOT load entire files into memory (260MB+).
Instead:
1. Stream-read line by line
2. Filter early (optional: by language)
3. Sample a small slice
4. Save to disk for fast iteration

This keeps free-tier LLM calls minimal during development.
"""
import json
from pathlib import Path
from typing import Optional, Generator
import random

# Paths
REPO_ROOT = Path(__file__).parent.parent
COMMENT_GEN_DIR = REPO_ROOT / "Comment_Generation"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Ensure output directory exists
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def stream_jsonl(filepath: str) -> Generator[dict, None, None]:
    """
    Stream-read a JSONL file line by line.
    Yields one parsed JSON object per iteration.

    Why streaming? The real eval set (~260MB) can't fit in memory.
    This generator pattern is memory-efficient.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Line {line_num} not valid JSON: {e}")


def inspect_and_slice(
    input_file: str,
    output_file: str,
    sample_size: int = 50,
    lang_filter: Optional[str] = None,
    seed: int = 42
) -> None:
    """
    Stream through JSONL, inspect structure, sample a subset, save to disk.

    Args:
        input_file: Path to msg-*.jsonl
        output_file: Path to save sliced output
        sample_size: How many examples to keep
        lang_filter: Optional language filter (e.g., 'python', 'javascript')
        seed: Random seed for reproducibility
    """
    random.seed(seed)
    examples = []
    field_keys = set()
    total_lines = 0
    filtered_lines = 0

    print(f"\n📖 Streaming {Path(input_file).name}...")

    # Stream through the entire file
    for record in stream_jsonl(input_file):
        total_lines += 1

        # Inspect structure
        field_keys.update(record.keys())

        # Filter by language if specified
        if lang_filter and record.get('lang') != lang_filter:
            continue

        filtered_lines += 1

        # Reservoir sampling: keep random sample of size `sample_size`
        if len(examples) < sample_size:
            examples.append(record)
        else:
            # Randomly replace with decreasing probability
            j = random.randint(0, filtered_lines - 1)
            if j < sample_size:
                examples[j] = record

    # Save sliced dataset
    with open(output_file, 'w', encoding='utf-8') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

    print(f"  Total records: {total_lines}")
    print(f"  Filtered records: {filtered_lines} {f'(lang={lang_filter})' if lang_filter else ''}")
    print(f"  Sampled subset: {len(examples)} examples")
    print(f"  Output: {output_file}")
    print(f"  Fields detected: {sorted(field_keys)}")

    # Display a sample record for inspection
    if examples:
        print(f"\n📄 Sample record:")
        sample = examples[0]
        for key, val in sample.items():
            if isinstance(val, str) and len(val) > 100:
                print(f"  {key}: {val[:100]}...")
            else:
                print(f"  {key}: {val}")


def main():
    print("=" * 70)
    print("PHASE 1: Data Setup - Building Evaluation Slices")
    print("=" * 70)

    # Step 1: Build development/validation slice from msg-valid.jsonl
    # This is for iterating on prompts and agent logic
    valid_file = COMMENT_GEN_DIR / "msg-valid.jsonl"
    if valid_file.exists():
        inspect_and_slice(
            input_file=str(valid_file),
            output_file=str(DATA_PROCESSED_DIR / "dev_valid_slice.jsonl"),
            sample_size=50,
            lang_filter=None,  # Use all languages for now
        )
    else:
        print(f"❌ File not found: {valid_file}")
        return

    # Step 2: Build final evaluation slice from msg-test.jsonl
    # This stays untouched until Phase 6!
    test_file = COMMENT_GEN_DIR / "msg-test.jsonl"
    if test_file.exists():
        inspect_and_slice(
            input_file=str(test_file),
            output_file=str(DATA_PROCESSED_DIR / "final_eval_slice.jsonl"),
            sample_size=100,
            lang_filter=None,  # Use all languages for now
        )
    else:
        print(f"❌ File not found: {test_file}")
        return

    print("\n" + "=" * 70)
    print("✓ Data setup complete! Ready for Phase 2 (Tools)")
    print("=" * 70)
    print(f"\n📊 Next steps:")
    print(f"  1. Review samples in {DATA_PROCESSED_DIR}")
    print(f"  2. Verify field structure matches expectations")
    print(f"  3. Move to Phase 2: Tool implementation")


if __name__ == "__main__":
    main()
