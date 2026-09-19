"""Pydantic v2 models for every pipeline stage's JSON contract.

See files/03-DATA-CONTRACTS.md for the authoritative spec.
All files are UTF-8 JSON, ensure_ascii=false, 2-space indent.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExamKind(str, Enum):
    DAILY_MCQ = "daily_mcq"
    DAILY_WRITTEN = "daily_written"
    WEEKLY_MCQ = "weekly_mcq"
    WEEKLY_WRITTEN = "weekly_written"
    DIFF_SET = "diff_set"
    QUESTION_BANK = "question_bank"
    BOOK = "book"


class NodeKind(str, Enum):
    TEXT = "text"
    MATH = "math"


class TextEncoding(str, Enum):
    BIJOY = "bijoy"
    UNICODE = "unicode"


class QuestionForm(str, Enum):
    NUMERIC_SINGLE_STEP = "numeric_single_step"
    NUMERIC_MULTI_STEP = "numeric_multi_step"
    CONCEPTUAL_RECALL = "conceptual_recall"
    GRAPH_INTERPRETATION = "graph_interpretation"
    STATEMENT_ASSERTION = "statement_assertion"
    MATCHING = "matching"
    DERIVATION = "derivation"


class Subject(str, Enum):
    PHYSICS = "Physics"
    CHEMISTRY = "Chemistry"
    MATH = "Math"


# ---------------------------------------------------------------------------
# Stage 1: Raw nodes (01_raw_nodes.json)
# ---------------------------------------------------------------------------

class TextNode(BaseModel):
    kind: NodeKind = NodeKind.TEXT
    raw: str
    encoding: TextEncoding = TextEncoding.BIJOY
    cls: str = ""


class MathNode(BaseModel):
    kind: NodeKind = NodeKind.MATH
    mathml: str


RawNode = TextNode | MathNode


class ImageRef(BaseModel):
    cid: str
    sha1: str
    stored_at: str


class Option(BaseModel):
    letter: str = Field(pattern=r"^[A-D]$")
    nodes: list[RawNode]


class RawQuestion(BaseModel):
    q_index: int = Field(ge=1)
    stem_nodes: list[RawNode] = Field(min_length=1)
    options: list[Option] = Field(min_length=1)
    correct_letter: Optional[str] = Field(None, pattern=r"^[A-D]$")
    images: list[ImageRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def mcq_has_4_options(self) -> "RawQuestion":
        # Invariant: can't enforce exam_kind here, so just check if options exist
        # The ingest stage asserts len(options) == 4 for MCQ
        return self


class RawDocument(BaseModel):
    doc_id: str
    source_path: str
    source_url: str = ""
    captured_at: Optional[str] = None
    course_id: str = ""
    routine_id: str = ""
    exam_id: str = ""
    unique_set: Optional[int] = None
    exam_kind: ExamKind
    week_index: Optional[int] = None
    filename_subject: str = ""
    questions: list[RawQuestion]


class IngestReport(BaseModel):
    files_seen: int = 0
    files_ok: int = 0
    files_failed: int = 0
    questions_total: int = 0
    assert_failures: list[str] = Field(default_factory=list)


class RawNodesFile(BaseModel):
    schema_version: int = 1
    generated_at: str = ""
    documents: list[RawDocument] = Field(default_factory=list)
    ingest_report: IngestReport = Field(default_factory=IngestReport)


# ---------------------------------------------------------------------------
# Stage 2: Decoded questions (02_questions.json)
# ---------------------------------------------------------------------------

class MathBlock(BaseModel):
    token: str  # e.g. "⟦M0⟧"
    latex: str
    mathml: str = ""


class DecodeQuality(BaseModel):
    bijoy_chars_in: int = 0
    unmapped_glyphs: list[list[Any]] = Field(default_factory=list)
    residual_latin1_high: int = 0
    math_blocks_ok: int = 0
    math_blocks_failed: int = 0


class DecodedOption(BaseModel):
    letter: str = Field(pattern=r"^[A-D]$")
    text: str
    math_blocks: list[MathBlock] = Field(default_factory=list)


class DecodedQuestion(BaseModel):
    qid: str
    doc_id: str
    source_path: str
    exam_kind: ExamKind
    week_index: Optional[int] = None
    captured_at: Optional[str] = None
    filename_subject: str = ""
    question_text: str
    math_blocks: list[MathBlock] = Field(default_factory=list)
    options: list[DecodedOption] = Field(min_length=1)
    correct_letter: Optional[str] = None
    raw_preserved: dict[str, Any] = Field(default_factory=dict)
    decode_quality: DecodeQuality = Field(default_factory=DecodeQuality)


class DecodeReport(BaseModel):
    questions_total: int = 0
    clean_questions: int = 0
    clean_rate: float = 0.0
    math_conversion_rate: float = 0.0
    unmapped_glyph_frequency: list[list[Any]] = Field(default_factory=list)


class DecodedQuestionsFile(BaseModel):
    schema_version: int = 1
    questions: list[DecodedQuestion] = Field(default_factory=list)
    decode_report: DecodeReport = Field(default_factory=DecodeReport)


# ---------------------------------------------------------------------------
# Stage 3: Taxonomy (03_taxonomy.json)
# ---------------------------------------------------------------------------

class BookMeta(BaseModel):
    book_id: str
    title: str
    subject: str
    paper: Optional[int] = None
    source_path: str
    pages: int = 0


class Section(BaseModel):
    section_id: str
    book_id: str
    chapter_no: int
    chapter_title: str
    section_no: int
    section_title: str
    page_start: int
    page_end: int
    text_chars: int = 0
    worked_examples: int = 0
    exercise_problems: int = 0


class Concept(BaseModel):
    concept_id: str
    subject: str
    label_en: str
    aliases_bn: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)
    book_weight: float = 0.0
    parent: Optional[str] = None
    typical_forms: list[QuestionForm] = Field(default_factory=list)


class TaxonomyFile(BaseModel):
    schema_version: int = 1
    books: list[BookMeta] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 4: Labelled questions (04_labelled.json)
# ---------------------------------------------------------------------------

class LabelledQuestion(BaseModel):
    qid: str
    subject: str
    concept_id: Optional[str] = None
    concept_candidates: list[str] = Field(default_factory=list)
    difficulty_1_5: int = Field(ge=1, le=5)
    question_form: QuestionForm
    confidence: int = Field(ge=0, le=100)
    needs_review: bool = False
    labeller: str = ""
    subject_disagrees_with_filename: bool = False


class ClassifyReport(BaseModel):
    labelled: int = 0
    needs_review: int = 0
    subject_disagreements: int = 0
    cache_hits: int = 0


class LabelledFile(BaseModel):
    schema_version: int = 1
    labels: list[LabelledQuestion] = Field(default_factory=list)
    classify_report: ClassifyReport = Field(default_factory=ClassifyReport)


# ---------------------------------------------------------------------------
# Stage 5: Features (05_features.json)
# ---------------------------------------------------------------------------

class FeatureSet(BaseModel):
    book_weight: float = 0.0
    bank_frequency: float = 0.0
    in_syllabus: int = 0
    syllabus_available: int = 0
    daily_signal_w: float = 0.0
    daily_signal_w_minus_1: float = 0.0
    weekly_history: list[int] = Field(default_factory=list)
    weeks_since_last_weekly: int = 0
    appeared_last_weekly: int = 0
    diffset_signal: float = 0.0
    form_diversity: int = 0
    prereq_covered: int = 0


class FeatureRow(BaseModel):
    concept_id: str
    subject: str
    features: FeatureSet
    label: Optional[int] = None  # 1 if appeared, filled during backtest


class FeaturesFile(BaseModel):
    schema_version: int = 1
    target_week: int
    rows: list[FeatureRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 6: Ranked predictions (06_ranked.json)
# ---------------------------------------------------------------------------

class RankedConcept(BaseModel):
    rank: int
    concept_id: str
    subject: str
    score: float
    probability: float = Field(ge=0.0, le=1.0)
    expected_count: float = 0.0
    contributions: dict[str, float] = Field(default_factory=dict)
    evidence_qids: list[str] = Field(default_factory=list)


class RankedFile(BaseModel):
    schema_version: int = 1
    target_week: int
    weights_version: str = ""
    ranked: list[RankedConcept] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 7: Final prediction (prediction_wN.json)
# ---------------------------------------------------------------------------

class Prediction(BaseModel):
    pred_id: str
    rank: int
    concept_id: str
    subject: str
    probability: float
    question_bn: str = ""
    math_latex: list[str] = Field(default_factory=list)
    options_bn: list[str] = Field(default_factory=list)
    answer: str = ""
    worked_solution_bn: str = ""
    based_on: dict[str, Any] = Field(default_factory=dict)


class PredictionFile(BaseModel):
    schema_version: int = 1
    target_week: int
    generated_at: str = ""
    predictions: list[Prediction] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

class GroundTruthLabel(BaseModel):
    qid: str
    subject: str
    concept_id: str
    question_text_bn: str
    n_options: int = 4
    labelled_by: str = "human"
    labelled_at: str = ""


# ---------------------------------------------------------------------------
# English PDF ingest (01_questions.json)
# ---------------------------------------------------------------------------

class EnglishOption(BaseModel):
    letter: str = Field(pattern=r"^[A-D]$")
    text: str


class EnglishQuestion(BaseModel):
    q_index: int = Field(ge=1)
    question_text: str
    options: list[EnglishOption] = Field(min_length=1)
    math_expressions: list[str] = Field(default_factory=list)
    correct_letter: Optional[str] = Field(None, pattern=r"^[A-D]$")


class EnglishDocument(BaseModel):
    doc_id: str
    source_path: str
    exam_kind: ExamKind
    subject_hint: str = ""
    week_index: Optional[int] = None
    unique_set: Optional[int] = None
    questions: list[EnglishQuestion]


class EnglishIngestReport(BaseModel):
    files_seen: int = 0
    files_ok: int = 0
    files_failed: int = 0
    total_questions: int = 0
    questions_with_options: int = 0
    questions_missing_options: int = 0
    per_file: dict[str, dict[str, int]] = Field(default_factory=dict)


class EnglishQuestionsFile(BaseModel):
    schema_version: int = 1
    source_type: str = "english_pdf"
    documents: list[EnglishDocument] = Field(default_factory=list)
    ingest_report: EnglishIngestReport = Field(default_factory=EnglishIngestReport)
