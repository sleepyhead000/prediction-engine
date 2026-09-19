"""Extract raw Bijoy-encoded strings from .mhtml files for decoder vector labeling.

Usage:
    python scripts/extract_bijoy_strings.py [--output ground_truth/candidate_bijoy_strings.tsv]

Outputs a TSV with columns:
    raw_bijoy_string  context_snippet  source_file  question_number

A human reviews this file, types the correct Bengali in a new column,
and saves as ground_truth/decoder_vectors.tsv.
"""
from __future__ import annotations

import argparse
import csv
import quopri
import re
import sys
from pathlib import Path

from lxml import html as lxml_html


def decode_mhtml(filepath: Path) -> str:
    """Extract and decode the HTML body from an .mhtml file."""
    raw = filepath.read_bytes()
    # Find HTML section
    boundary = b"Content-Type: text/html"
    pos = 0
    while True:
        idx = raw.find(boundary, pos)
        if idx == -1:
            break
        header_end = raw.find(b"\r\n\r\n", idx)
        if header_end == -1:
            header_end = raw.find(b"\n\n", idx)
        if header_end == -1:
            pos = idx + 1
            continue
        content_start = header_end + 4
        next_boundary = raw.find(b"Content-Type:", content_start)
        section = raw[content_start:next_boundary] if next_boundary != -1 else raw[content_start:]
        if b"questionBlock" in section:
            return quopri.decodestring(section).decode("utf-8", errors="replace")
        pos = idx + 1
    # Fallback: try last HTML section
    pos = 0
    last_html = b""
    while True:
        idx = raw.find(boundary, pos)
        if idx == -1:
            break
        header_end = raw.find(b"\r\n\r\n", idx)
        if header_end == -1:
            pos = idx + 1
            continue
        content_start = header_end + 4
        next_boundary = raw.find(b"Content-Type:", content_start)
        section = raw[content_start:next_boundary] if next_boundary != -1 else raw[content_start:]
        last_html = section
        pos = idx + 1
    if last_html:
        return quopri.decodestring(last_html).decode("utf-8", errors="replace")
    return ""


def extract_bijoy_strings(html_content: str, source_file: str) -> list[dict]:
    """Walk the DOM and extract raw Bijoy text from pt-0000* class spans."""
    results = []
    try:
        tree = lxml_html.fromstring(html_content)
    except Exception:
        return results

    # Find question blocks
    question_blocks = tree.xpath('//div[contains(@class, "questionBlock")]')
    for block in question_blocks:
        # Get question number
        serial_el = block.xpath('.//div[@class="serial"]//span')
        q_num = 0
        if serial_el:
            m = re.search(r"(\d+)", serial_el[0].text_content())
            if m:
                q_num = int(m.group(1))

        # Walk all spans with pt-0000* classes
        spans = block.xpath('.//span[contains(@class, "pt-0000")]')
        for span in spans:
            cls = span.get("class", "")
            text = span.text_content()
            if not text.strip():
                continue
            # Check if text contains non-ASCII (potential Bijoy)
            has_high_bytes = any(ord(c) >= 128 for c in text)
            has_ascii = any(ord(c) < 128 for c in text)
            if has_ascii and not has_high_bytes:
                # Pure ASCII in pt-0000 span = Bijoy encoded
                # Get context: parent text
                parent = span.getparent()
                context = ""
                if parent is not None:
                    context = parent.text_content()[:100]
                results.append({
                    "raw_bijoy": text,
                    "context": context,
                    "source_file": source_file,
                    "question_number": q_num,
                    "class": cls,
                })
    return results


def main():
    parser = argparse.ArgumentParser(description="Extract Bijoy strings for decoder vector labeling")
    parser.add_argument(
        "--output", "-o",
        default="ground_truth/candidate_bijoy_strings.tsv",
        help="Output TSV path",
    )
    parser.add_argument(
        "sources",
        nargs="?",
        default="sources",
        help="Directory containing .mhtml files (default: sources/)",
    )
    args = parser.parse_args()

    sources_dir = Path(args.sources)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mhtml_files = sorted(sources_dir.rglob("*.mhtml"))
    if not mhtml_files:
        print(f"No .mhtml files found in {sources_dir}")
        sys.exit(1)

    all_results = []
    for f in mhtml_files:
        print(f"  Processing {f.name}...", end=" ", flush=True)
        html = decode_mhtml(f)
        if not html:
            print("(no HTML found)")
            continue
        results = extract_bijoy_strings(html, str(f.relative_to(sources_dir)))
        all_results.extend(results)
        print(f"{len(results)} strings")

    # Write TSV
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["raw_bijoy", "context", "source_file", "question_number", "correct_bengali"])
        for r in all_results:
            writer.writerow([
                r["raw_bijoy"],
                r["context"],
                r["source_file"],
                r["question_number"],
                "",  # human fills this in
            ])

    print(f"\nExtracted {len(all_results)} Bijoy strings to {output_path}")
    print("Review the file, fill in the 'correct_bengali' column, and save as decoder_vectors.tsv")


if __name__ == "__main__":
    main()
