"""Extract questions from exam PDFs (rendered from MHTML via conv.py).

Reads PDFs produced by conv.py (Playwright-rendered MHTML). Extracts
question text, options, and math expressions. Handles Bijoy-encoded
Bengali (appears as replacement chars) and English text.

Usage:
    python -m engine.ingest --src ground_truth/pdfs --out data/01_questions.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pymupdf

from engine.schemas import (
    EnglishDocument,
    EnglishIngestReport,
    EnglishOption,
    EnglishQuestion,
    EnglishQuestionsFile,
    ExamKind,
)


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

RE_QUESTION = re.compile(r"^Question\s+(\d+)\s*$", re.MULTILINE)
RE_OPTION = re.compile(r"^[A-E]\s*$", re.MULTILINE)
RE_SOLUTION = re.compile(r"^Solution:", re.MULTILINE)
RE_MATH_INLINE = re.compile(
    r"(?:\^[\({\[]?\d+[\)}\]]?|_[\({\[]?\d+[\)}\]]?|"
    r"\\(?:frac|sqrt|sum|int|prod|lim|log|ln|sin|cos|tan|sec|csc|cot)"
    r"(?:\s*\{[^}]*\})*|"
    r"[∑∫∂∇√∞±×÷≠≤≥≈∝∈∉⊂⊃∪∩∧∨¬])"
)
RE_CHEMICAL = re.compile(
    r"(?:[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*)"  # simple formula like H2O
)

# Header patterns to detect exam metadata
RE_HEADER_EXAM = re.compile(
    r"EAP\s+(Daily|Weekly)\s+(MCQ|WRITTEN)\s+Exam\s+W?-?(\d+)",
    re.IGNORECASE,
)
RE_HEADER_SUBJECT = re.compile(
    r"(Higher Mathematics|Physics|Chemistry)\s*\((\d+)\)",
    re.IGNORECASE,
)
RE_HEADER_SET = re.compile(r"MCQ Master Set:\s*(\d+)")


# ---------------------------------------------------------------------------
# Metadata extraction from filename
# ---------------------------------------------------------------------------

def infer_exam_kind(filename: str) -> ExamKind:
    """Infer exam kind from filename."""
    name = filename.lower()
    if "written" in name:
        if "weekly" in name or "w-" in name:
            return ExamKind.WEEKLY_WRITTEN
        return ExamKind.DAILY_WRITTEN
    if "mcq" in name or "set" in name:
        if "weekly" in name or "w-" in name:
            return ExamKind.WEEKLY_MCQ
        return ExamKind.DAILY_MCQ
    if "diff" in name:
        return ExamKind.DIFF_SET
    return ExamKind.WEEKLY_MCQ  # default


def infer_subject_from_path(source_path: str) -> str:
    """Try to infer subject from the PDF path or content."""
    path_lower = source_path.lower()
    if "math" in path_lower or "m1" in path_lower or "m2" in path_lower:
        return "Math"
    if "chem" in path_lower or "c1" in path_lower or "c2" in path_lower:
        return "Chemistry"
    if "phys" in path_lower or "p1" in path_lower or "p2" in path_lower:
        return "Physics"
    return ""


def infer_week_index(source_path: str) -> int | None:
    """Extract week index from path like 'weeklies/week2/...'."""
    m = re.search(r"week(\d+)", source_path, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def infer_set_number(filename: str) -> int | None:
    """Extract set number from filename like 'MCQ 1.pdf'."""
    m = re.search(r"(?:MCQ|WRITTEN|set)\s*(\d+)", filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Question extraction
# ---------------------------------------------------------------------------

def split_into_questions(full_text: str) -> list[dict[str, Any]]:
    """Split PDF text into individual questions using 'Question N' markers.

    Returns list of dicts with keys: index, text (everything until next Question).
    """
    # Find all question markers
    markers = [(m.start(), int(m.group(1))) for m in RE_QUESTION.finditer(full_text)]

    if not markers:
        return []

    questions = []
    for i, (start, idx) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)
        chunk = full_text[start:end]
        questions.append({"index": idx, "raw": chunk})

    return questions


def extract_options(chunk: str) -> list[EnglishOption]:
    """Extract A-E options from a question chunk.

    Options appear as single letter on a line, followed by the option text
    on subsequent lines until the next option letter or end of chunk.
    """
    options = []
    # Find all option markers
    opt_matches = list(RE_OPTION.finditer(chunk))

    for i, m in enumerate(opt_matches):
        letter = m.group(0).strip()
        # Text is from end of this match to start of next option (or end)
        text_start = m.end()
        text_end = opt_matches[i + 1].start() if i + 1 < len(opt_matches) else len(chunk)
        opt_text = chunk[text_start:text_end].strip()
        # Clean up: remove "Solution:" if it leaked in
        sol_match = RE_SOLUTION.search(opt_text)
        if sol_match:
            opt_text = opt_text[: sol_match.start()].strip()
        if opt_text:
            options.append(EnglishOption(letter=letter, text=opt_text))

    return options


def extract_math_expressions(text: str) -> list[str]:
    """Extract math-like expressions from text."""
    exprs = []
    # Look for equation-like patterns
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # Detect math: contains =, ^, _, or special symbols
        if RE_MATH_INLINE.search(line) or "=" in line and any(c.isdigit() for c in line):
            exprs.append(line)
    return exprs


def extract_question_text(chunk: str) -> str:
    """Extract the question stem (before options)."""
    # Find where options start (first single letter A-E on a line)
    opt_match = RE_OPTION.search(chunk)
    sol_match = RE_SOLUTION.search(chunk)

    end = len(chunk)
    if opt_match:
        end = min(end, opt_match.start())
    if sol_match:
        end = min(end, sol_match.start())

    # Skip the "Question N" line
    q_match = RE_QUESTION.match(chunk)
    start = q_match.end() if q_match else 0

    text = chunk[start:end].strip()
    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_subject_from_text(text: str) -> str:
    """Try to extract subject from page header text."""
    m = RE_HEADER_SUBJECT.search(text)
    if m:
        subject_map = {
            "higher mathematics": "Math",
            "physics": "Physics",
            "chemistry": "Chemistry",
        }
        return subject_map.get(m.group(1).lower(), m.group(1))
    return ""


# ---------------------------------------------------------------------------
# Main ingest
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: Path, src_root: Path) -> EnglishDocument | None:
    """Ingest a single exam PDF. Returns None on failure."""
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as e:
        print(f"  FAILED to open {pdf_path.name}: {e}")
        return None

    source_path = str(pdf_path.relative_to(src_root))
    doc_id = f"sha1:{hashlib.sha1(source_path.encode()).hexdigest()[:12]}"

    # Read all pages
    full_text = ""
    header_text = ""
    for page in doc:
        page_text = page.get_text()
        full_text += page_text + "\n"
        if not header_text:
            header_text = page_text[:500]

    # Extract metadata from header
    subject = extract_subject_from_text(header_text)
    if not subject:
        subject = infer_subject_from_path(source_path)

    exam_kind = infer_exam_kind(pdf_path.name)
    week_index = infer_week_index(source_path)
    unique_set = infer_set_number(pdf_path.name)

    # Extract questions
    raw_questions = split_into_questions(full_text)
    questions = []

    for rq in raw_questions:
        q_text = extract_question_text(rq["raw"])
        options = extract_options(rq["raw"])
        math_exprs = extract_math_expressions(q_text)

        questions.append(
            EnglishQuestion(
                q_index=rq["index"],
                question_text=q_text,
                options=options,
                math_expressions=math_exprs,
            )
        )

    doc_obj = EnglishDocument(
        doc_id=doc_id,
        source_path=source_path,
        exam_kind=exam_kind,
        subject_hint=subject,
        week_index=week_index,
        unique_set=unique_set,
        questions=questions,
    )

    return doc_obj


def run_ingest(src_dir: Path, out_path: Path) -> EnglishQuestionsFile:
    """Ingest all PDFs under src_dir. Returns the full output file."""
    pdf_files = sorted(src_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")

    documents = []
    report = EnglishIngestReport(files_seen=len(pdf_files))

    for pdf_path in pdf_files:
        # Skip diff sets, written exams, and non-exam PDFs
        if "diff" in pdf_path.name.lower():
            report.files_seen -= 1
            continue
        if "written" in pdf_path.name.lower():
            report.files_seen -= 1
            continue

        print(f"  {pdf_path.relative_to(src_dir)}...", end=" ")
        doc_obj = ingest_pdf(pdf_path, src_dir)

        if doc_obj is None:
            report.files_failed += 1
            print("FAILED")
            continue

        n_q = len(doc_obj.questions)
        n_with_opts = sum(1 for q in doc_obj.questions if len(q.options) >= 4)
        report.files_ok += 1
        report.total_questions += n_q
        report.questions_with_options += n_with_opts
        report.questions_missing_options += n_q - n_with_opts
        report.per_file[pdf_path.name] = {
            "questions": n_q,
            "with_options": n_with_opts,
        }
        documents.append(doc_obj)
        print(f"{n_q} questions ({n_with_opts} with 4+ options)")

    result = EnglishQuestionsFile(
        documents=documents,
        ingest_report=report,
    )

    # Write output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest exam PDFs")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("ground_truth/pdfs"),
        help="Source directory with PDFs",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/01_questions.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    result = run_ingest(args.src, args.out)

    r = result.ingest_report
    print(f"\n{'='*50}")
    print(f"Files: {r.files_ok}/{r.files_seen} ok, {r.files_failed} failed")
    print(f"Questions: {r.total_questions} total, {r.questions_with_options} with 4+ options")
    print(f"Missing options: {r.questions_missing_options}")


if __name__ == "__main__":
    main()
