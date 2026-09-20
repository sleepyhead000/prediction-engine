"""OCR module — wraps EasyOCR for Bengali + English text extraction.

Supports CUDA, Intel XPU (Arc GPUs), and CPU backends.
Requires EasyOCR models to be on a drive with space (not C:).
Set EASYOCR_MODEL_PATH env var before importing.
"""
from __future__ import annotations

import os
from pathlib import Path

# Ensure model path is set before importing easyocr
if "EASYOCR_MODEL_PATH" not in os.environ:
    os.environ["EASYOCR_MODEL_PATH"] = str(
        Path(__file__).resolve().parent.parent / "cache" / "easyocr"
    )

import torch  # noqa: E402
import easyocr  # noqa: E402


# ---------------------------------------------------------------------------
# GPU detection
# ---------------------------------------------------------------------------

def detect_device() -> str:
    """Detect best available torch device: 'cuda' > 'xpu' > 'cpu'."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return "xpu"
    return "cpu"


# ---------------------------------------------------------------------------
# Reader singleton
# ---------------------------------------------------------------------------

_reader: easyocr.Reader | None = None
_device: str = "cpu"


def set_gpu(use_gpu: bool) -> None:
    """Set GPU mode. Must be called before first OCR call.

    If use_gpu=True, auto-detects best device (CUDA > XPU > CPU).
    """
    global _device, _reader
    if use_gpu:
        _device = detect_device()
    else:
        _device = "cpu"
    _reader = None  # Reset reader to pick up new setting


def get_device() -> str:
    """Return current device string."""
    return _device


def get_reader() -> easyocr.Reader:
    """Lazy-init EasyOCR reader (Bengali + English)."""
    global _reader
    if _reader is None:
        use_gpu = _device != "cpu"
        _reader = easyocr.Reader(
            ["bn", "en"],
            gpu=use_gpu,
            verbose=False,
            model_storage_directory=os.environ["EASYOCR_MODEL_PATH"],
        )
    return _reader


def ocr_image(img_bytes: bytes, min_confidence: float = 0.3) -> dict:
    """OCR a single image (PNG bytes). Returns text + metadata.

    Returns:
        {
            "text": full joined text,
            "blocks": [{"text": str, "confidence": float, "bbox": list}, ...],
            "avg_confidence": float,
            "char_count": int,
            "has_bengali": bool,
        }
    """
    reader = get_reader()
    result = reader.readtext(img_bytes, detail=1)

    blocks = []
    for bbox, text, conf in result:
        if conf >= min_confidence:
            blocks.append({
                "text": text,
                "confidence": round(conf, 4),
                "bbox": [[int(p) for p in pt] for pt in bbox],
            })

    full_text = " ".join(b["text"] for b in blocks)
    avg_conf = (
        sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0.0
    )
    has_bengali = any("\u0980" <= c <= "\u09FF" for c in full_text)

    return {
        "text": full_text,
        "blocks": blocks,
        "avg_confidence": round(avg_conf, 4),
        "char_count": len(full_text),
        "has_bengali": has_bengali,
    }
