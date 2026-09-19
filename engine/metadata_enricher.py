"""Enrich chunks with metadata: keywords, math detection, difficulty signals.

Reads book_chunks.json, produces book_chunks_enriched.json.

Usage:
    python -m engine.metadata_enricher --input data/book_chunks.json --output data/book_chunks_enriched.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# Bengali question patterns
RE_QUESTION_BN = re.compile(r"(?:কত|কোন|কি|কেন|কী|গণনা|বর্ণনা|তুলনা|নির্ণযং|প্রমাণ)")

# Math indicators
RE_MATH = re.compile(
    r"(?:\d+\s*[+\-×÷=]\s*\d+|"
    r"\^[\{(\[]?\d+[\})\]]?|"
    r"_[\{(\[]?\d+[\})\]]?|"
    r"[∑∫∂∇√∞±]|"
    r"(?:equation|formula|theorem|lemma)"
    r")",
    re.IGNORECASE,
)

# Common Bengali stopwords to exclude from keywords
BN_STOPWORDS = {
    "এবং", "অথবা", "কিন্তু", "তবে", "যে", "যা", "যার", "এটি", "এটা",
    "ও", "এ", "ঐ", "বা", "মধ্যে", "থেকে", "পর্যন্ত", "সম্পর্কে",
    "হয়", "করা", "হতে", "থাকে", "করে", "দিয়ে", "নিয়ে",
}


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Extract top-N Bengali/English keywords by frequency."""
    words = re.findall(r"[\u0980-\u09FF]{3,}|[a-zA-Z]{4,}", text)
    words = [w.lower() for w in words if w.lower() not in BN_STOPWORDS]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_n)]


def detect_math(text: str) -> bool:
    return bool(RE_MATH.search(text))


def detect_questions(text: str) -> bool:
    return bool(RE_QUESTION_BN.search(text))


def classify_difficulty(text: str) -> str:
    """Simple heuristic difficulty classification."""
    if len(text) < 200:
        return "easy"
    if detect_math(text):
        return "medium"
    if detect_questions(text):
        return "medium"
    if len(text) > 800:
        return "hard"
    return "medium"


def enrich_chunk(chunk: dict) -> dict:
    """Add metadata fields to a single chunk."""
    text = chunk["text"]
    enriched = dict(chunk)
    enriched["keywords"] = extract_keywords(text)
    enriched["has_math"] = detect_math(text)
    enriched["has_questions"] = detect_questions(text)
    enriched["difficulty"] = classify_difficulty(text)
    enriched["char_count"] = len(text)
    return enriched


def run_enrichment(input_path: Path, output_path: Path) -> None:
    chunks = json.loads(input_path.read_text(encoding="utf-8"))
    enriched = [enrich_chunk(c) for c in chunks]

    with_math = sum(1 for c in enriched if c["has_math"])
    with_questions = sum(1 for c in enriched if c["has_questions"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Enriched {len(enriched)} chunks")
    print(f"  With math: {with_math}")
    print(f"  With questions: {with_questions}")
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich chunks with metadata")
    parser.add_argument("--input", type=Path, default=Path("data/book_chunks.json"))
    parser.add_argument("--output", type=Path, default=Path("data/book_chunks_enriched.json"))
    args = parser.parse_args()

    run_enrichment(args.input, args.output)


if __name__ == "__main__":
    main()
