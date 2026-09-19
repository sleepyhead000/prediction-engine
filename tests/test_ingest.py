"""Tests for engine.ingest — PDF question extraction."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.ingest import (
    extract_math_expressions,
    extract_options,
    extract_question_text,
    infer_exam_kind,
    infer_subject_from_path,
    infer_week_index,
    split_into_questions,
    run_ingest,
)
from engine.schemas import ExamKind


class TestSplitIntoQuestions:
    def test_basic(self):
        text = "Question 1\nWhat is 2+2?\nA\n3\nB\n4\nC\n5\nD\n6\nQuestion 2\nWhat is 3+3?\nA\n5\nB\n6\nC\n7\nD\n8"
        qs = split_into_questions(text)
        assert len(qs) == 2
        assert qs[0]["index"] == 1
        assert qs[1]["index"] == 2

    def test_no_questions(self):
        qs = split_into_questions("No questions here")
        assert len(qs) == 0

    def test_single_question(self):
        qs = split_into_questions("Question 5\nTest question")
        assert len(qs) == 1
        assert qs[0]["index"] == 5


class TestExtractOptions:
    def test_four_options(self):
        chunk = "Question 1\nA\nopt a\nB\nopt b\nC\nopt c\nD\nopt d"
        opts = extract_options(chunk)
        assert len(opts) == 4
        assert opts[0].letter == "A"
        assert opts[3].letter == "D"

    def test_five_options(self):
        chunk = "Question 1\nA\nalpha\nB\nbeta\nC\ngamma\nD\ndelta\nE\nepsilon"
        opts = extract_options(chunk)
        assert len(opts) == 5
        assert opts[4].letter == "E"

    def test_stops_at_solution(self):
        chunk = "Question 1\nA\nopt a\nSolution:\nSome solution"
        opts = extract_options(chunk)
        assert len(opts) == 1
        assert opts[0].letter == "A"


class TestExtractQuestionText:
    def test_basic(self):
        chunk = "Question 1\nWhat is the answer?\nA\n3\nB\n4\nSolution:\nThe answer is 4"
        text = extract_question_text(chunk)
        assert "Question 1" not in text
        assert "What is the answer?" in text
        assert "Solution:" not in text

    def test_no_options(self):
        chunk = "Question 3\nDescribe the process"
        text = extract_question_text(chunk)
        assert "Describe the process" in text


class TestInferMetadata:
    def test_exam_kind_mcq(self):
        assert infer_exam_kind("MCQ 1.pdf") == ExamKind.DAILY_MCQ
        assert infer_exam_kind("Weekly set 2.pdf") == ExamKind.WEEKLY_MCQ

    def test_exam_kind_written(self):
        assert infer_exam_kind("WRITTEN 1.pdf") == ExamKind.DAILY_WRITTEN
        assert infer_exam_kind("C1 WRITTEN 2.pdf") == ExamKind.DAILY_WRITTEN

    def test_subject_from_path(self):
        assert infer_subject_from_path("dailies/week1/C1 MCQ 1.pdf") == "Chemistry"
        assert infer_subject_from_path("dailies/week1/M1 MCQ 1.pdf") == "Math"
        assert infer_subject_from_path("dailies/week1/P1 MCQ 1.pdf") == "Physics"

    def test_week_index(self):
        assert infer_week_index("weeklies/week2/MCQ 1.pdf") == 2
        assert infer_week_index("weeklies/week3/MCQ 1.pdf") == 3
        assert infer_week_index("dailies/week1/C1 MCQ 1.pdf") == 1


class TestExtractMathExpressions:
    def test_equation(self):
        exprs = extract_math_expressions("x^2 + y^2 = 25")
        assert len(exprs) >= 1

    def test_no_math(self):
        exprs = extract_math_expressions("Hello world")
        assert len(exprs) == 0


class TestIngestIntegration:
    def test_ingest_produces_output(self, tmp_path):
        """Test that ingest runs on real PDFs and produces valid output."""
        src = Path("ground_truth/pdfs")
        if not src.exists():
            pytest.skip("PDFs not available")
        out = tmp_path / "test_questions.json"
        result = run_ingest(src, out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["schema_version"] == 1
        assert len(data["documents"]) > 0
        assert data["ingest_report"]["files_ok"] > 0
