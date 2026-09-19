"""OCR all board book PDFs and output page-level text.

Usage:
    python -m scripts.ocr_books --src sources/books --out data/book_pages.jsonl

Output: one JSON line per page with book, page_num, text, confidence, etc.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from engine.ocr import ocr_image
from engine.page_extractor import extract_page_image, get_pdf_page_count


def ocr_pdf(
    pdf_path: Path,
    src_root: Path,
    dpi: int = 200,
    min_confidence: float = 0.3,
) -> list[dict]:
    """OCR all pages of a single PDF. Returns list of page dicts."""
    book_name = pdf_path.relative_to(src_root).with_suffix("").as_posix()
    page_count = get_pdf_page_count(pdf_path)
    pages = []

    for page_num in range(page_count):
        img_bytes = extract_page_image(pdf_path, page_num, dpi=dpi)
        result = ocr_image(img_bytes, min_confidence=min_confidence)

        pages.append({
            "book": book_name,
            "page_num": page_num + 1,  # 1-indexed
            "text": result["text"],
            "char_count": result["char_count"],
            "avg_confidence": result["avg_confidence"],
            "has_bengali": result["has_bengali"],
            "block_count": len(result["blocks"]),
        })

    return pages


def run_ocr(src_dir: Path, out_path: Path, dpi: int = 200) -> None:
    """OCR all PDFs under src_dir. Writes JSONL output."""
    pdf_files = sorted(src_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} book PDFs")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_pages = 0
    low_conf_pages = 0
    start_time = time.time()

    with open(out_path, "w", encoding="utf-8") as f:
        for pdf_idx, pdf_path in enumerate(pdf_files):
            book_name = pdf_path.relative_to(src_dir)
            page_count = get_pdf_page_count(pdf_path)
            print(f"  [{pdf_idx + 1}/{len(pdf_files)}] {book_name} ({page_count} pages)...", end=" ", flush=True)

            pages = ocr_pdf(pdf_path, src_dir, dpi=dpi)
            for page in pages:
                f.write(json.dumps(page, ensure_ascii=False) + "\n")
                total_pages += 1
                if page["avg_confidence"] < 0.5:
                    low_conf_pages += 1

            avg_conf = sum(p["avg_confidence"] for p in pages) / len(pages) if pages else 0
            print(f"avg_conf={avg_conf:.2f}")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Total pages: {total_pages}")
    print(f"Low confidence (<0.5): {low_conf_pages}")
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR board book PDFs")
    parser.add_argument("--src", type=Path, default=Path("sources/books"))
    parser.add_argument("--out", type=Path, default=Path("data/book_pages.jsonl"))
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    run_ocr(args.src, args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
