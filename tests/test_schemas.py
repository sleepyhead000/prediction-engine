"""Tests for engine.schemas — round-trip serialization and invariant checks."""
from __future__ import annotations

import json

import pytest

from engine.schemas import (
    DecodeQuality,
    DecodedOption,
    DecodedQuestion,
    DecodedQuestionsFile,
    DecodeReport,
    MathBlock,
    RawDocument,
    RawNodesFile,
    RawQuestion,
    TextNode,
    MathNode,
    Option,
    IngestReport,
    ExamKind,
    NodeKind,
    TextEncoding,
    Subject,
)


class TestRawNodesFile:
    def test_roundtrip(self):
        doc = RawDocument(
            doc_id="sha1:abc123",
            source_path="sources/dailies/week1/C1 MCQ 1.mhtml",
            exam_kind=ExamKind.DAILY_MCQ,
            week_index=1,
            filename_subject="Chemistry",
            questions=[
                RawQuestion(
                    q_index=1,
                    stem_nodes=[
                        TextNode(raw="test text", encoding=TextEncoding.BIJOY),
                        MathNode(mathml="<math><mn>0</mn></math>"),
                    ],
                    options=[
                        Option(letter="A", nodes=[TextNode(raw="opt a", encoding=TextEncoding.BIJOY)]),
                        Option(letter="B", nodes=[TextNode(raw="opt b", encoding=TextEncoding.BIJOY)]),
                        Option(letter="C", nodes=[TextNode(raw="opt c", encoding=TextEncoding.BIJOY)]),
                        Option(letter="D", nodes=[TextNode(raw="opt d", encoding=TextEncoding.BIJOY)]),
                    ],
                )
            ],
        )
        raw_file = RawNodesFile(
            documents=[doc],
            ingest_report=IngestReport(files_seen=1, files_ok=1, questions_total=1),
        )
        serialized = raw_file.model_dump_json()
        restored = RawNodesFile.model_validate_json(serialized)
        assert restored.documents[0].doc_id == "sha1:abc123"
        assert len(restored.documents[0].questions) == 1
        assert restored.documents[0].questions[0].q_index == 1


class TestDecodedQuestionsFile:
    def test_roundtrip(self):
        q = DecodedQuestion(
            qid="sha1:abc:q1",
            doc_id="sha1:abc",
            source_path="test.mhtml",
            exam_kind=ExamKind.DAILY_MCQ,
            question_text="test question ⟦M0⟧",
            math_blocks=[MathBlock(token="⟦M0⟧", latex="0")],
            options=[
                DecodedOption(letter="A", text="⟦M1⟧", math_blocks=[MathBlock(token="⟦M1⟧", latex="1")]),
                DecodedOption(letter="B", text="2"),
                DecodedOption(letter="C", text="3"),
                DecodedOption(letter="D", text="4"),
            ],
            raw_preserved={"stem_nodes": [{"kind": "text", "raw": "test"}]},
            decode_quality=DecodeQuality(bijoy_chars_in=10, math_blocks_ok=1),
        )
        report = DecodeReport(questions_total=1, clean_questions=1, clean_rate=1.0)
        dqf = DecodedQuestionsFile(questions=[q], decode_report=report)
        serialized = dqf.model_dump_json()
        restored = DecodedQuestionsFile.model_validate_json(serialized)
        assert restored.questions[0].qid == "sha1:abc:q1"
        assert restored.decode_report.clean_rate == 1.0


class TestRawQuestionInvariants:
    def test_min_options(self):
        q = RawQuestion(
            q_index=1,
            stem_nodes=[TextNode(raw="x", encoding=TextEncoding.BIJOY)],
            options=[Option(letter="A", nodes=[TextNode(raw="a", encoding=TextEncoding.BIJOY)])],
        )
        assert len(q.options) >= 1

    def test_empty_stem_rejected(self):
        with pytest.raises(Exception):
            RawQuestion(q_index=1, stem_nodes=[], options=[])
