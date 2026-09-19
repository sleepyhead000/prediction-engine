"""Convert MHTML exam files to readable PDFs using Playwright.

Usage:
    python conv.py --src sources --out ground_truth/pdfs

Outputs PDFs mirroring the source directory structure so humans can read
the original exam pages with Bijoy fonts and MathJax rendering.
"""
import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def convert_mhtml_to_pdf(mhtml_filepath: str, pdf_filepath: str, browser, timeout: int = 60) -> bool:
    """Convert a single MHTML file to PDF. Returns True on success."""
    absolute_path = os.path.abspath(mhtml_filepath)
    file_url = f"file://{absolute_path}"

    page = browser.new_page()
    try:
        page.goto(file_url, wait_until="networkidle", timeout=timeout * 1000)
        page.pdf(
            path=pdf_filepath,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        return True
    except Exception as e:
        print(f"    FAILED: {e}")
        return False
    finally:
        page.close()


def find_mhtml_files(src_dir: Path) -> list[Path]:
    """Recursively find all .mhtml files, sorted."""
    return sorted(src_dir.rglob("*.mhtml"))


def compute_output_path(mhtml_path: Path, src_dir: Path, out_dir: Path) -> Path:
    """Map source path to output PDF path preserving directory structure."""
    rel = mhtml_path.relative_to(src_dir)
    return out_dir / rel.with_suffix(".pdf")


def main():
    parser = argparse.ArgumentParser(description="Convert MHTML exam files to readable PDFs")
    parser.add_argument("--src", default=".", help="Source directory to scan (default: .)")
    parser.add_argument("--out", default="ground_truth/pdfs", help="Output directory (default: ground_truth/pdfs)")
    parser.add_argument("--force", action="store_true", help="Reconvert even if PDF exists")
    parser.add_argument("--timeout", type=int, default=60, help="Per-page timeout in seconds (default: 60)")
    args = parser.parse_args()

    src_dir = Path(args.src).resolve()
    out_dir = Path(args.out).resolve()

    if not src_dir.exists():
        print(f"Source directory not found: {src_dir}")
        sys.exit(1)

    mhtml_files = find_mhtml_files(src_dir)
    if not mhtml_files:
        print(f"No .mhtml files found in {src_dir}")
        sys.exit(1)

    # Filter out already-converted files unless --force
    to_convert = []
    for f in mhtml_files:
        out_path = compute_output_path(f, src_dir, out_dir)
        if not args.force and out_path.exists() and out_path.stat().st_mtime > f.stat().st_mtime:
            continue
        to_convert.append(f)

    skipped = len(mhtml_files) - len(to_convert)
    if skipped:
        print(f"Skipping {skipped} already-converted files (use --force to reconvert)")

    print(f"Converting {len(to_convert)} MHTML files -> {out_dir}/")
    print()

    converted = 0
    failed = 0
    failed_files = []
    start_time = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for i, mhtml_file in enumerate(to_convert, 1):
            out_path = compute_output_path(mhtml_file, src_dir, out_dir)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            rel_src = mhtml_file.relative_to(src_dir)
            rel_out = out_path.relative_to(out_dir)
            print(f"  [{i:2d}/{len(to_convert)}] {rel_src} -> {rel_out}", end=" ", flush=True)

            ok = convert_mhtml_to_pdf(str(mhtml_file), str(out_path), browser, timeout=args.timeout)
            if ok:
                size_kb = out_path.stat().st_size / 1024
                print(f"({size_kb:.0f} KB)")
                converted += 1
            else:
                failed += 1
                failed_files.append(str(rel_src))

        browser.close()

    elapsed = time.time() - start_time
    print()
    print(f"Done in {elapsed:.1f}s")
    print(f"  Converted: {converted}/{len(to_convert)}")
    if failed:
        print(f"  Failed: {failed}")
        for f in failed_files:
            print(f"    - {f}")
    if skipped:
        print(f"  Skipped (already up to date): {skipped}")


if __name__ == "__main__":
    main()
