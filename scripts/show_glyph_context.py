"""Show context for unmapped Bijoy glyphs to help close the glyph table.

Usage:
    python scripts/show_glyph_context.py <character> [--data data/02_questions.json]

Prints 5 example sentences containing the glyph, with surrounding decoded text.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Show context for unmapped Bijoy glyphs")
    parser.add_argument("glyph", help="The character to search for (e.g. ½)")
    parser.add_argument(
        "--data", "-d",
        default="data/02_questions.json",
        help="Path to decoded questions JSON",
    )
    parser.add_argument(
        "--max-examples", "-n",
        type=int,
        default=5,
        help="Number of examples to show",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        print("Run the decode stage first to produce this file.")
        sys.exit(1)

    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    glyph = args.glyph
    found = 0

    questions = data.get("questions", [])
    for q in questions:
        if found >= args.max_examples:
            break

        # Search in raw_preserved
        raw_preserved = q.get("raw_preserved", {})
        stem_nodes = raw_preserved.get("stem_nodes", [])

        for node in stem_nodes:
            raw = node.get("raw", "")
            if glyph in raw:
                # Found! Show context
                decoded = q.get("question_text", "")
                source = q.get("source_path", "unknown")
                qid = q.get("qid", "unknown")
                print(f"--- Example {found + 1} ---")
                print(f"  QID:        {qid}")
                print(f"  Source:     {source}")
                print(f"  Raw Bijoy:  {raw}")
                print(f"  Decoded:    {decoded[:200]}")
                print()
                found += 1
                break

        # Also search in options
        if found < args.max_examples:
            for opt in q.get("options", []):
                for node in opt.get("math_blocks", []):
                    if glyph in node.get("mathml", ""):
                        raw_preserved_opts = q.get("raw_preserved", {}).get("options", [])
                        print(f"--- Example {found + 1} (in option {opt.get('letter', '?')}) ---")
                        print(f"  QID:        {q.get('qid', 'unknown')}")
                        print(f"  Source:     {q.get('source_path', 'unknown')}")
                        print(f"  Decoded:    {opt.get('text', '')[:200]}")
                        print()
                        found += 1
                        break

    if found == 0:
        print(f"Glyph '{glyph}' (U+{ord(glyph):04X}) not found in any question.")
        print("Try running the decode stage first, or check a different glyph.")
    else:
        print(f"Found {found} example(s). Use these to identify the correct Bengali mapping.")


if __name__ == "__main__":
    main()
