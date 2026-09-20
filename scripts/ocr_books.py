"""OCR all board book PDFs and output page-level text.

Supports resume: if the output file already exists, completed books are skipped.
Progress bar with ETA shown via tqdm.

Usage:
    python -m scripts.ocr_books --gpu --src sources/books --out data/book_pages.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore", message=".*quantize_per_tensor.*")

from tqdm import tqdm

from engine.ocr import ocr_image, set_gpu, get_device
from engine.page_extractor import extract_page_image, get_pdf_page_count


def scan_existing(output_path: Path) -> dict[str, int]:
    """Scan existing JSONL to find how many pages each book has completed.

    Returns: {book_name: completed_page_count}
    """
    done: dict[str, int] = defaultdict(int)
    if not output_path.exists():
        return done

    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done[rec["book"]] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def ocr_pdf(
    pdf_path: Path,
    src_root: Path,
    dpi: int = 200,
    min_confidence: float = 0.3,
    start_page: int = 0,
    progress: tqdm | None = None,
) -> list[dict]:
    """OCR pages of a single PDF starting from start_page (0-indexed).

    If progress is given, it's updated per page.
    """
    book_name = pdf_path.relative_to(src_root).with_suffix("").as_posix()
    page_count = get_pdf_page_count(pdf_path)
    pages = []

    for page_num in range(start_page, page_count):
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

        if progress is not None:
            progress.update(1)

    return pages


def format_eta(seconds: float) -> str:
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m"


def run_ocr(src_dir: Path, out_path: Path, dpi: int = 200, gpu: bool = False) -> None:
    """OCR all PDFs under src_dir. Writes JSONL output. Resumes from existing progress."""
    set_gpu(gpu)
    device = get_device()
    pdf_files = sorted(src_dir.rglob("*.pdf"))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Scan existing output for resume
    done_books = scan_existing(out_path)
    total_pdf_pages = sum(get_pdf_page_count(p) for p in pdf_files)

    skipped = []
    to_process = []
    for pdf_path in pdf_files:
        book_name = pdf_path.relative_to(src_dir).with_suffix("").as_posix()
        page_count = get_pdf_page_count(pdf_path)
        completed = done_books.get(book_name, 0)
        if completed >= page_count:
            skipped.append((book_name, page_count))
        else:
            to_process.append((pdf_path, book_name, page_count, completed))

    remaining_pages = sum(pc - done for _, _, pc, done in to_process)

    print(f"Device: {device}")
    print(f"Total PDFs: {len(pdf_files)} ({total_pdf_pages} pages)")
    if skipped:
        print(f"Skipped (already done): {len(skipped)} PDFs")
    print(f"To process: {len(to_process)} PDFs ({remaining_pages} pages)")
    if skipped:
        for name, pc in skipped:
            print(f"  [done] {name} ({pc} pages)")
    print()

    total_pages = sum(done_books.values())
    low_conf_pages = 0
    start_time = time.time()
    books_done_this_run = 0

    # Open in append mode to preserve existing data
    with open(out_path, "a", encoding="utf-8") as f:
        with tqdm(total=remaining_pages, unit="page", desc="OCR", ncols=80) as pbar:
            for pdf_path, book_name, page_count, start_page in to_process:
                pbar.set_postfix_str(book_name[:30], refresh=True)

                pages = ocr_pdf(
                    pdf_path, src_dir, dpi=dpi,
                    start_page=start_page, progress=pbar,
                )
                for page in pages:
                    f.write(json.dumps(page, ensure_ascii=False) + "\n")
                    total_pages += 1
                    if page["avg_confidence"] < 0.5:
                        low_conf_pages += 1
                f.flush()

                books_done_this_run += 1
                elapsed = time.time() - start_time
                done_this_run = pbar.n
                if done_this_run > 0:
                    rate = elapsed / done_this_run
                    remaining = remaining_pages - done_this_run
                    eta = format_eta(rate * remaining)
                    pbar.set_postfix_str(
                        f"ETA {eta} | {rate:.1f}s/page", refresh=False
                    )

    elapsed = time.time() - start_time
    print(f"\nDone in {format_eta(elapsed)}")
    print(f"Total pages: {total_pages}")
    print(f"This run: {books_done_this_run} PDFs, {remaining_pages} pages")
    print(f"Low confidence (<0.5): {low_conf_pages}")
    print(f"Output: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR board book PDFs")
    parser.add_argument("--src", type=Path, default=Path("sources/books"))
    parser.add_argument("--out", type=Path, default=Path("data/book_pages.jsonl"))
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--gpu", action="store_true", help="Use GPU (auto-detects CUDA/XPU)")
    args = parser.parse_args()

    run_ocr(args.src, args.out, dpi=args.dpi, gpu=args.gpu)


if __name__ == "__main__":
    main()
