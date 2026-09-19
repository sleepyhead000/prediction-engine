"""Extract PDF pages as images for OCR.

Renders each page at configurable DPI using PyMuPDF.
Saves as PNG bytes or returns directly.
"""
from __future__ import annotations

import io
from pathlib import Path

import pymupdf


def extract_page_image(
    pdf_path: str | Path,
    page_num: int,
    dpi: int = 200,
) -> bytes:
    """Render a single PDF page as PNG bytes.

    Args:
        pdf_path: Path to PDF file.
        page_num: 0-indexed page number.
        dpi: Resolution for rendering (200 recommended for OCR).

    Returns:
        PNG image bytes.
    """
    doc = pymupdf.open(str(pdf_path))
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def get_pdf_page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in a PDF."""
    doc = pymupdf.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count


def extract_all_pages(
    pdf_path: str | Path,
    dpi: int = 200,
    max_pages: int | None = None,
) -> list[bytes]:
    """Render all pages (or first N) as PNG bytes.

    Returns:
        List of PNG bytes, one per page.
    """
    doc = pymupdf.open(str(pdf_path))
    n = len(doc)
    if max_pages:
        n = min(n, max_pages)

    pages = []
    for i in range(n):
        pix = doc[i].get_pixmap(dpi=dpi)
        pages.append(pix.tobytes("png"))

    doc.close()
    return pages
