"""Split OCR'd book pages into retrievable chunks.

Reads book_pages.jsonl and book_sections.json, produces book_chunks.json
with overlapping chunks sized by token count.

Usage:
    python -m engine.chunker --pages data/book_pages.jsonl --sections data/book_sections.json --output data/book_chunks.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_MAX_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 100
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n{2,}", text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_text(
    text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[str]:
    if estimate_tokens(text) <= max_tokens:
        return [text]

    paragraphs = split_paragraphs(text)
    chunks = []
    current = ""

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        current_tokens = estimate_tokens(current)

        if current_tokens + para_tokens <= max_tokens:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            if para_tokens > max_tokens:
                sentences = re.split(r"(?<=[.!?।\n])\s+", para)
                current = ""
                for sent in sentences:
                    if estimate_tokens(current) + estimate_tokens(sent) <= max_tokens:
                        current = (current + " " + sent).strip() if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                current = para

    if current:
        chunks.append(current)

    if overlap_tokens > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            overlap_chars = overlap_tokens * CHARS_PER_TOKEN
            if len(prev) > overlap_chars:
                overlap_text = prev[-overlap_chars:]
                for sep in ["\n", " ", "।"]:
                    idx = overlap_text.find(sep)
                    if idx > 0:
                        overlap_text = overlap_text[idx + 1:]
                        break
                overlapped.append(overlap_text + " " + chunks[i])
            else:
                overlapped.append(chunks[i])
        chunks = overlapped

    return chunks


def make_chunk_id(book: str, idx: int) -> str:
    safe = book.replace("/", "_").replace(" ", "_")
    return f"{safe}_chunk_{idx:04d}"


def process_book(
    book_name: str,
    pages: list[dict],
    sections: list[dict] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict]:
    chunks = []
    chunk_idx = 0

    if sections:
        for section in sections:
            sec_text_parts = []
            for page in pages:
                if section["page_start"] <= page["page_num"] <= section.get("page_end", section["page_start"]):
                    sec_text_parts.append(page["text"])
            sec_text = "\n\n".join(sec_text_parts)
            if not sec_text.strip():
                continue
            text_chunks = chunk_text(sec_text, max_tokens=max_tokens)
            for tc in text_chunks:
                chunks.append({
                    "chunk_id": make_chunk_id(book_name, chunk_idx),
                    "book": book_name,
                    "section_no": section.get("section_no", ""),
                    "section_title": section.get("section_title", ""),
                    "page_start": section["page_start"],
                    "page_end": section.get("page_end", section["page_start"]),
                    "chunk_type": "theory",
                    "token_count": estimate_tokens(tc),
                    "text": tc,
                    "anchor_text": f"{book_name} {section.get('section_title', '')}",
                })
                chunk_idx += 1
    else:
        full_text = "\n\n".join(p["text"] for p in pages)
        page_start = pages[0]["page_num"] if pages else 1
        page_end = pages[-1]["page_num"] if pages else 1
        text_chunks = chunk_text(full_text, max_tokens=max_tokens)
        for tc in text_chunks:
            chunks.append({
                "chunk_id": make_chunk_id(book_name, chunk_idx),
                "book": book_name,
                "section_no": "",
                "section_title": "",
                "page_start": page_start,
                "page_end": page_end,
                "chunk_type": "theory",
                "token_count": estimate_tokens(tc),
                "text": tc,
                "anchor_text": book_name,
            })
            chunk_idx += 1

    return chunks


def run_chunking(
    pages_path: Path,
    sections_path: Path | None,
    output_path: Path,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> None:
    books: dict[str, list[dict]] = {}
    with open(pages_path, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            book = page["book"]
            if book not in books:
                books[book] = []
            books[book].append(page)

    sections_map: dict[str, list[dict]] = {}
    if sections_path and sections_path.exists():
        sections_data = json.loads(sections_path.read_text(encoding="utf-8"))
        for book_data in sections_data:
            sections_map[book_data["book"]] = book_data.get("chapters", [])

    all_chunks = []
    for book_name in sorted(books):
        pages = sorted(books[book_name], key=lambda p: p["page_num"])
        book_sections = sections_map.get(book_name)
        book_chunks = process_book(book_name, pages, book_sections, max_tokens)
        all_chunks.extend(book_chunks)
        print(f"  {book_name}: {len(pages)} pages -> {len(book_chunks)} chunks")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nTotal: {len(all_chunks)} chunks")
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk OCR'd book pages")
    parser.add_argument("--pages", type=Path, default=Path("data/book_pages.jsonl"))
    parser.add_argument("--sections", type=Path, default=Path("data/book_sections.json"))
    parser.add_argument("--output", type=Path, default=Path("data/book_chunks.json"))
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    run_chunking(args.pages, args.sections, args.output, args.max_tokens)


if __name__ == "__main__":
    main()
