"""Detect chapter and section boundaries in OCR'd book text.

Processes book_pages.jsonl and outputs book_sections.json with
chapter/section structure for each book.

Usage:
    python -m engine.section_detector --input data/book_pages.jsonl --output data/book_sections.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Bengali chapter patterns
RE_CHAPTER_BN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"অধ্যায়\s*(\d+)"           # অধ্যায় ১, অধ্যায় ২
    r"|ধাপ\s*(\d+)"              # ধাপ ১, ধাপ ২
    r"|পর্ব\s*(\d+)"             # পর্ব ১
    r"|ভাগ\s*(\d+)"              # ভাগ ১
    r")",
    re.IGNORECASE,
)

# English chapter patterns
RE_CHAPTER_EN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"Chapter\s+(\d+)"
    r"|CHAPTER\s+(\d+)"
    r"|Unit\s+(\d+)"
    r"|PART\s+([IVXLC]+)"
    r")",
    re.IGNORECASE,
)

# Section patterns (numbered headings)
RE_SECTION = re.compile(
    r"(?:^|\n)\s*(?:"
    r"(\d+\.\d+(?:\.\d+)?)"      # 1.2, 1.2.3
    r"|(\d+\.\d+\s+.+)"          # 1.2 Title text
    r")",
    re.IGNORECASE,
)

# Bengali section patterns
RE_SECTION_BN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"নির্বাচন\s*[:.]\s*(.+)"    # নির্বাচন: title
    r"|বিশেষ\s*[:.]\s*(.+)"      # বিশেষ: title
    r")",
    re.IGNORECASE,
)


def detect_chapters(pages: list[dict]) -> list[dict]:
    """Detect chapter boundaries from a list of page dicts.

    Each page dict must have: book, page_num, text.

    Returns list of chapter dicts:
        {chapter_no, chapter_title, page_start, page_end, sections: [...]}
    """
    chapters = []
    current_chapter = None

    for page in pages:
        text = page["text"]
        page_num = page["page_num"]

        # Try to find chapter marker
        ch_match = RE_CHAPTER_BN.search(text) or RE_CHAPTER_EN.search(text)
        if ch_match:
            # Extract chapter number (first non-None group)
            groups = ch_match.groups()
            ch_no = next((g for g in groups if g is not None), str(len(chapters) + 1))

            # Extract chapter title (rest of line after chapter number)
            line_start = text.rfind("\n", 0, ch_match.start()) + 1
            line_end = text.find("\n", ch_match.end())
            if line_end == -1:
                line_end = len(text)
            ch_title = text[line_start:line_end].strip()

            if current_chapter:
                current_chapter["page_end"] = page_num - 1
                chapters.append(current_chapter)

            current_chapter = {
                "chapter_no": ch_no,
                "chapter_title": ch_title,
                "page_start": page_num,
                "page_end": page_num,
                "sections": [],
            }

        if current_chapter:
            current_chapter["page_end"] = page_num

            # Try to find sections within this page
            for s_match in RE_SECTION.finditer(text):
                groups = s_match.groups()
                sec_id = next((g for g in groups if g is not None), "")
                if sec_id and len(sec_id) < 100:  # Skip long matches
                    current_chapter["sections"].append({
                        "section_no": sec_id.split()[0] if sec_id else "",
                        "section_title": sec_id,
                        "page_start": page_num,
                        "page_end": page_num,
                    })

    if current_chapter:
        chapters.append(current_chapter)

    return chapters


def detect_sections_in_text(text: str, page_num: int) -> list[dict]:
    """Detect section markers within a single page's text."""
    sections = []

    for match in RE_SECTION.finditer(text):
        groups = match.groups()
        sec_id = next((g for g in groups if g is not None), "")
        if sec_id and len(sec_id) < 100:
            sections.append({
                "section_no": sec_id.split()[0] if sec_id else "",
                "section_title": sec_id,
                "page_start": page_num,
                "page_end": page_num,
            })

    return sections


def process_book(pages: list[dict]) -> dict:
    """Process all pages of a single book. Returns structured output."""
    if not pages:
        return {"book": "", "pages": 0, "chapters": []}

    book_name = pages[0]["book"]
    chapters = detect_chapters(pages)

    # If no chapters detected, create a single chapter spanning all pages
    if not chapters:
        chapters = [{
            "chapter_no": "1",
            "chapter_title": book_name,
            "page_start": pages[0]["page_num"],
            "page_end": pages[-1]["page_num"],
            "sections": [],
        }]

    return {
        "book": book_name,
        "pages": len(pages),
        "chapters": chapters,
    }


def run_section_detection(input_path: Path, output_path: Path) -> None:
    """Read book_pages.jsonl, detect sections, write book_sections.json."""
    # Group pages by book
    books: dict[str, list[dict]] = {}
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            book = page["book"]
            if book not in books:
                books[book] = []
            books[book].append(page)

    # Process each book
    results = []
    for book_name in sorted(books):
        pages = sorted(books[book_name], key=lambda p: p["page_num"])
        result = process_book(pages)
        results.append(result)
        ch_count = len(result["chapters"])
        print(f"  {book_name}: {result['pages']} pages, {ch_count} chapters")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect chapters/sections in OCR'd books")
    parser.add_argument("--input", type=Path, default=Path("data/book_pages.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/book_sections.json"))
    args = parser.parse_args()

    run_section_detection(args.input, args.output)


if __name__ == "__main__":
    main()
