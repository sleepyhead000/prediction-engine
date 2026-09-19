# 10 — Revised Phased Implementation Plan

## Context

The original plan assumed Bijoy-encoded Bengali MHTML files as the primary
source. This has been revised:

- **Exam sources:** English-translated PDFs (text-selectable, PyMuPDF-readable)
- **Textbook sources:** Bengali board book scans (image-based PDFs, need OCR)
- **Bijoy decoder:** Eliminated entirely
- **Knowledge base:** NotebookLM-style with entity extraction and strict
  grounding verification

## What's Already Built

| Component | Status | File |
|-----------|--------|------|
| Pydantic schemas (Bengali stages) | ✅ Complete | `engine/schemas.py` |
| Cached LLM client | ✅ Complete | `engine/llm.py` |
| Schema round-trip tests | ✅ 3 test classes | `tests/test_schemas.py` |
| pyproject.toml + deps | ✅ All installed | `pyproject.toml` |
| ChromaDB 1.5.9 | ✅ Installed | — |
| EasyOCR 1.7.2 | ✅ Installed | — |
| sentence-transformers 6.1.0 | ✅ Installed | — |

**Not built:** No pipeline stage implementations. No `data/` directory. No
ChromaDB persistent store. New English schemas not yet added to `engine/schemas.py`
alongside existing Bengali schemas.

## Critical Infrastructure Warning

C: drive has **0.71 GB free**. Model caches (HuggingFace, EasyOCR) default to
C:. Must set environment variables before first run:

```powershell
$env:HF_HOME = "G:\prediction-engine\cache\huggingface"
$env:EASYOCR_MODEL_PATH = "G:\prediction-engine\cache\easyocr"
```

These are set in `setup_env.ps1` (root of repo). Run it before any Python work.

---

## Revised Pipeline Architecture (Collapsed to 8 Stages)

```
sources/
  exams/           ← English PDF text (PyMuPDF)
  books/           ← Bengali board book scans
      |
      v
[1] ingest exams     →  data/01_questions.json       English question text
[2] OCR books        →  data/book_pages.jsonl         Bengali scans → text
[3] chunk+anchor     →  data/book_chunks.json         Structured chunks with locations
[4] enrich chunks    →  data/book_enriched.json       Entities + concepts + metadata (single LLM call)
[5] index            →  ChromaDB (persistent)          Embed enriched chunks
[6] classify         →  data/03_labelled.json          Question → concept
[7] score            →  data/05_ranked.json            Features + ranked predictions
[8] generate+eval    →  out/prediction_wN.json         Verified predictions + scorecard
```

**Rationale for collapse:** With only 4 weekly exams to train on, a 12-stage
pipeline introduces too many failure modes. Entity graph (bridge detection,
co-occurrence) can be added later once 10+ weekly exams exist to validate it.
ChromaDB uses a single collection instead of two — cross-referencing adds
complexity that isn't justified at this scale.

---

## Blocking Dependency

**Before Gate 2:** Create a labelled sample set (minimum 20 questions from
English exam PDFs) to verify retrieval ceiling. The previous 120-question
labelled set (T-004) was never created. Use English questions for easier labelling.

---

## Phase 0 — Foundation (already done, verify)

**Tasks:**
- T-001: Repo skeleton ✅
- T-002: Schemas ✅
- T-003: LLM client ✅
- T-006: Eval harness ← **TODO**

**Verify:** `pytest tests/` passes. `python -m engine.eval --selftest` prints baseline.

---

## Phase 1 — Exam PDF Ingest (T-100 to T-103)

### T-100: English PDF text extractor

`engine/ingest.py` — reads English exam PDFs via PyMuPDF.

**Logic:**
1. Open PDF with `pymupdf.open(path)`
2. For each page: `page.get_text()`
3. Split by `Question N` pattern (regex: `Question\s+\d+`)
4. Extract options: lines starting with `A`, `B`, `C`, `D`
5. Extract math: detect LaTeX-like patterns (`\frac`, `^`, `_`, `\sqrt`)
6. Output: `data/01_questions.json`

**Output schema:** New `EnglishQuestionFile` in `engine/schemas.py`:

```json
{
  "schema_version": 1,
  "source_type": "english_pdf",
  "documents": [
    {
      "doc_id": "sha1:...",
      "source_path": "sources/exams/C1 MCQ 1.pdf",
      "exam_kind": "daily_mcq",
      "subject_hint": "Chemistry",
      "questions": [
        {
          "q_index": 1,
          "question_text": "At temperatures 30°C and 55°C...",
          "options": [
            {"letter": "A", "text": "10.12 g"},
            {"letter": "B", "text": "11.45 g"},
            {"letter": "C", "text": "12.62 g"},
            {"letter": "D", "text": "13.33 g"}
          ],
          "math_expressions": ["Δ = |x-y| / (100+x) × V"],
          "correct_letter": null
        }
      ]
    }
  ]
}
```

**Verify:** Run on all 29 exam PDFs. Every MCQ yields exactly 4 non-empty
options. Every daily MCQ yields 20 questions. `ingest_report.files_failed == 0`.

### T-101: Schema update for English questions

Add `EnglishQuestionFile`, `EnglishQuestion`, `EnglishOption` to
`engine/schemas.py`. Keep backward compatibility with existing Bengali schemas
(old models stay as reference).

**Verify:** Round-trip test for new models.

### T-102: Unit tests for ingest

`tests/test_ingest.py` — test on 2-3 sample PDFs:
- Correct question count per file
- Correct option count per question
- Math expression extraction
- Edge cases: written questions (1 per file), diff sets

**Verify:** All tests pass.

### T-103: Ingest report

Generate `data/ingest_report.json` with:
- `files_seen`, `files_ok`, `files_failed`
- `total_questions`, `questions_with_options`, `questions_missing_options`
- Per-file breakdown

**Verify:** Report is complete and accurate.

**GATE 1:** All 29 exam PDFs ingested. All MCQs have 4 options. Report is clean.

---

## Phase 2 — Board Book OCR + Chunking (T-200 to T-207)

### T-200: EasyOCR Bengali engine

`engine/ocr.py` — wraps EasyOCR for Bengali + English.

```python
import easyocr
reader = easyocr.Reader(['bn', 'en'], gpu=False)  # CPU mode

def ocr_page(page_image):
    """OCR a single page image. Returns text + confidence."""
    result = reader.readtext(page_image, detail=1)
    text = ' '.join([r[1] for r in result])
    confidence = sum([r[2] for r in result]) / len(result) if result else 0
    return text, confidence
```

**Redirect model cache:**

```python
import os
os.environ['EASYOCR_MODEL_PATH'] = os.environ.get('EASYOCR_MODEL_PATH', 'cache/easyocr')
```

Read from environment, don't hardcode drive letters.

**Verify:** OCR one sample page. Bengali text is readable. Confidence > 0.7.

### T-201: Board book PDF page extractor

`engine/page_extractor.py` — renders each page as an image via PyMuPDF.

```python
for page_num in range(len(doc)):
    pix = doc[page_num].get_pixmap(dpi=200)  # 200 DPI for OCR quality
    img_bytes = pix.tobytes("png")
    # Save to data/_book_images/{book}/page_{num}.png
```

**Verify:** Extract 10 sample pages. Images are clear enough for OCR.

### T-202: Full OCR pipeline

`scripts/ocr_books.py` — processes all board book PDFs.

**Logic:**
1. For each book PDF in `sources/books/`
2. For each page: check `data/ocr_overrides/{book}/page_{num}.txt` first
3. If no override: extract image → OCR → store text
4. Output: `data/book_pages.jsonl` (one line per page)

```json
{
  "book": "Chemistry Paper 1",
  "chapter": 2,
  "page_num": 45,
  "text": "দ্রাব্যতা গুণফল (Ksp) হলো...",
  "confidence": 0.87,
  "has_formulas": true,
  "has_diagrams": false
}
```

**Verify:** All book PDFs processed. Total pages processed matches PDF page
count. Average confidence > 0.7. Pages with <20 chars flagged.

### T-203: Chapter/section detector

`engine/section_detector.py` — identifies chapter and section boundaries
in OCR'd text.

**Heuristics:**
- Bengali chapter patterns: `অধ্যায় X`, `Chapter X`, `CHAPTER X`
- Section patterns: `X.X`, `X.X.X`, numbered headings
- Bold text detection (if available from OCR confidence)
- Page-based fallback: assume uniform chapter distribution if no headings

**Verify:** On 3 books, detected sections match manual inspection. No section
exceeds 20k chars.

### T-204: Chunk splitter

`engine/chunker.py` — splits book pages into retrievable chunks.

**Token counting:** Use the embedding model's auto-loaded tokenizer
(`sentence-transformers` handles this). Document which tokenizer is used.

**Strategy:**
1. **Structured books** (headings detected): Split on section boundaries.
   Each section = one chunk (or split if >800 tokens).
2. **Dense books** (few headings): Fixed-size window: 500 tokens, 150-token
   overlap. Split on paragraph boundaries where possible.
3. **Atomic units**: Keep worked examples and exercise problems as whole
   chunks (don't split mid-solution).

**Output:** `data/book_chunks.json`

```json
{
  "chunk_id": "chem_ch2_sec3_p45-47",
  "book": "Chemistry Paper 1",
  "chapter": 2,
  "section": "2.3",
  "section_title": "দ্রাব্যতা গুণফল",
  "page_start": 45,
  "page_end": 47,
  "chunk_type": "theory",
  "token_count": 520,
  "text": "...",
  "anchor_text": "Section 2.3: দ্রাব্যতা গুণফল (Solubility Product)"
}
```

**Verify:** No chunk exceeds 1000 tokens. No section is split mid-paragraph.
`chunk_type` is accurate for sample chunks. Total chunk count is plausible
(5-50 per chapter).

### T-205: Chunk metadata enricher

`engine/metadata_enricher.py` — adds entity tags and concept hints to chunks.

For each chunk, extract:
- Bengali keywords (top-10 by TF-IDF)
- Math formula presence
- Question-like patterns (কত?, কোন?, গণনা করো)
- Difficulty signals (worked example vs exercise vs theory)

**Verify:** Keywords are accurate for sample chunks.

### T-206: OCR quality report

`scripts/ocr_report.py` — generates quality metrics.

**Report includes:**
- Per-book: pages processed, average confidence, low-confidence pages (<0.6)
- Per-chapter: chunk count, token distribution
- Flagged pages: blank, diagram-only, low confidence

**Verify:** Report exists. Low-confidence pages are flagged for review.

### T-207: Unit tests for chunking

`tests/test_chunker.py`:
- Chunk size bounds (no chunk >1000 tokens)
- Section boundaries are respected
- Worked examples are atomic
- Anchor metadata is complete

**Verify:** All tests pass.

**GATE 2:** All board books OCR'd. Chunks created with anchor metadata. Quality
report clean. `retrieval_ceiling >= 0.90` on labelled sample (20 questions
minimum).

---

## Phase 3 — Chunk Enrichment + Indexing (T-300 to T-304)

Single combined phase: extract entities + concepts per chunk in one LLM call,
then index into ChromaDB.

### T-300: Chunk enricher (entities + concepts combined)

`engine/enrich.py` — single LLM call per chunk (batched 5 per call) that
extracts both entities AND testable concepts.

```
SYSTEM: You are a curriculum analyst for Bangladeshi HSC-level science
textbooks. Extract key entities and testable concepts from this section.

USER: {chunk_text}

Output:
{
  "entities": [
    {"name": "Ksp", "type": "formula", "bengali": "দ্রাব্যতা গুণফল"},
    {"name": "common ion effect", "type": "concept", "bengali": "সাধারণ আয়ন প্রভাব"}
  ],
  "concepts": [
    {
      "concept_id": "chem_solution_solubility",
      "name_en": "Solubility product calculation",
      "name_bn": "দ্রাব্যতা গুণফল নির্ণয়",
      "keywords_bn": ["দ্রাব্যতা", "গুণফল", "Ksp"],
      "difficulty": 3,
      "typical_forms": ["numeric_multi_step", "conceptual_recall"],
      "bridge_score": 0.0
    }
  ]
}
```

**Bridge detection:** For each entity/concept, count distinct chapters it
appears in. `bridge_score = (distinct_chapters - 1) / max(total_chapters - 1, 1)`.
Guard: if total_chapters = 1, bridge_score = 0.

**Cost control:** ~2000 chunks / 5 per call = ~400 LLM calls (was ~800 in old
plan with separate entity+concept phases). Cache results.

**Output:** `data/book_enriched.json`

**Verify:** 3-12 concepts per section. Entity precision > 0.80 on 20 samples.
Concept IDs unique. Bridge scores correct.

### T-301: Concept deduplication

Deduplicate across chunks at cosine > 0.92. Merge into canonical concepts.

**Verify:** Semantically identical concepts are merged. Niche distinctions
preserved.

### T-302: ChromaDB indexer

`engine/indexer.py` — embeds and stores enriched chunks.

**Single collection (`chunks`)** — one entry per enriched chunk:
- Embedding: `intfloat/multilingual-e5-large` on chunk text
- Metadata: book, chapter, section, page_range, anchor_text, chunk_type,
  entity_names, concept_ids, difficulty, bridge_score

**Verify:** Collection populated. Query returns relevant results.

### T-303: Retrieval test

`scripts/test_retrieval.py` — measures retrieval ceiling.

1. Take 20 labelled questions (English, from Phase 1)
2. Embed each question
3. Query ChromaDB top-8 chunks
4. Check if true concept is in top-8

**Verify:** `retrieval_ceiling >= 0.90`.

### T-304: Unit tests for indexing

`tests/test_index.py`:
- Embeddings correct dimension
- Query returns expected results
- Metadata filtering works
- Incremental update works (skip already-indexed chunks)

**Verify:** All tests pass.

**GATE 3:** ChromaDB indexed. `retrieval_ceiling >= 0.90`. Incremental updates
supported.

---

## Phase 4 — Classification (T-400 to T-402)

### T-400: Classifier

`engine/classify.py` — classifies exam questions into concepts.

1. Embed question text
2. Query ChromaDB → top-8 candidate chunks
3. LLM call → `{concept_id, subject, difficulty, question_form, confidence}`
4. If confidence < 60 or concept not in candidates → `needs_review: true`

**Verify:** Subject accuracy ≥ 0.97. Concept accuracy ≥ 0.80.

### T-401: Review queue

`engine/review_queue.py` — low-confidence questions flagged for review.

**Verify:** `needs_review` rate ≤ 0.15.

### T-402: Disagreement report

`scripts/disagreement_report.py` — classifier vs filename disagreements.

**Verify:** Report exists. Human reviews first 20.

**GATE 4:** Classification metrics meet thresholds.

---

## Phase 5 — Features + Scoring (T-500 to T-502)

### T-500: Feature builder

`engine/features.py` — per-concept signal matrix.

**Features:**
- `book_weight_c` (section depth + entity salience + bridge score from Phase 3)
- `bank_frequency_c` (from question bank)
- `daily_frequency_c` (from dailies this week)
- `recency_c` (weeks since last appearance)
- `bridge_score_c` (from Phase 3)
- `in_syllabus_c` (if syllabus retrievable)

**Verify:** No NaNs. Feature ranges match spec.

### T-501: Scorer

`engine/score.py` — Beta-Binomial + log-linear adjustment.

**Verify:** Contributions sum to final logit within 1e-6.

### T-502: Backtest

Leave-one-week-out. Writes `config/weights.json`.

**Verify:** `concept_recall@30 >= 0.55`.

**GATE 5:** Scoring metrics meet thresholds.

---

## Phase 6 — Generation + Verification (T-600 to T-604)

### T-600: House-style extractor

`engine/style_extractor.py` — stem length, numeric ranges, distractor patterns.

**Verify:** Values computed from data, not hardcoded.

### T-601: Generator

`engine/generate.py` — LLM generates 30 questions from top concepts + source.

**Verify:** 30 questions produced. Each cites `based_on.book_sections`.

### T-602: Solvability filter

LLM verifies each question is solvable from source material.

**Verify:** Discard rate < 30%.

### T-603: Grounding verification (NotebookLM-style)

`engine/verify.py` — self-check that each predicted concept has source text.

1. For each predicted concept, retrieve source chunks
2. LLM verifies: "Is this concept answerable from the provided source?"
3. If hallucination or insufficient context → discard

**Verify:** All output concepts are grounded.

### T-604: Output rendering

`prediction_wN.json` + `prediction_wN.md` with English questions + probabilities.

**Verify:** Markdown renders correctly.

**GATE 6:** `concept_recall@30 >= 0.70` on holdout. Two real weeklies logged.

---

## Phase 7 — Eval + Loop Closure (T-700 to T-702)

### T-700: Eval harness

`engine/eval.py` — all metrics from `07-EVALUATION-PROTOCOL.md`.

**Verify:** `python -m engine.eval --selftest` emits full scorecard.

### T-701: Outcome logger

`scripts/log_actual.py` — logs real weekly results.

**Verify:** Run against one existing weekly.

### T-702: Dashboard

`dashboard.py` — stage health, ranked concepts, scorecard history.

**Verify:** Runs. Shows all metrics.

---

## Future Enhancement: Entity Knowledge Graph

Once 10+ weekly exams exist to validate against, add entity graph layer:

- Entity co-occurrence graph (`engine/graph_builder.py`)
- Bridge detection with higher confidence
- Cross-chapter entity tracking
- Entity-based book weight calculation

This replaces the simple `bridge_score` in T-300 with a richer signal.

---

## Incremental Design

Each stage must support incremental updates:

1. **Detect already-processed files:** Check `data/` outputs for existing
   entries before re-processing.
2. **Skip unchanged chunks:** Chunks are keyed on `(book, page_start, page_end)`.
   If a chunk exists with the same key and text hash, skip.
3. **Append, don't replace:** JSONL outputs append new lines. JSON outputs
   merge by key.

---

## Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|-----------|------------|
| R1 | OCR quality on Bengali scans | Bad chunks → bad concepts | High | Test OCR on sample first. Flag low-confidence pages. `ocr_overrides/` for manual fixes. |
| R2 | C: drive fills up (0.71 GB free) | Model downloads fail | High | Set HF_HOME and EASYOCR_MODEL_PATH to G: in setup_env.ps1. |
| R3 | Multi-concept questions not retrieved | Low retrieval ceiling | Medium | Bridge score boosts cross-chapter entities. Smaller chunks. |
| R4 | Entity extraction hallucinations | Bad concepts | Medium | Validate against source text. High cosine threshold (0.92). |
| R5 | LLM cost for 10k pages of OCR | Expensive | Medium | Batch 5 chunks per call (was 5, now single call saves ~400). Cache aggressively. Local model. |
| R6 | Embedding model doesn't handle Bengali | Poor retrieval | Medium | Test with 20 pairs first. Fallback: translate before embedding. |
| R7 | Concept dedup over-merges | Loses niche distinctions | Low | High cosine threshold. Human spot-check. |

---

## Estimated Effort

| Phase | Tasks | Estimated Effort |
|-------|-------|-----------------|
| Phase 0 | T-006 only | 0.5 day |
| Phase 1 (Exam PDFs) | T-100 to T-103 | 1 day |
| Phase 2 (OCR + Chunking) | T-200 to T-207 | 3-4 days |
| Phase 3 (Enrich + Index) | T-300 to T-304 | 2-3 days |
| Phase 4 (Classification) | T-400 to T-402 | 1-2 days |
| Phase 5 (Features + Scoring) | T-500 to T-502 | 1-2 days |
| Phase 6 (Generation) | T-600 to T-604 | 2 days |
| Phase 7 (Eval + Loop) | T-700 to T-702 | 1 day |
| **Total** | | **~12-15 days** |

---

## Open Questions

1. **Book sample** — Can you share 1-2 sample pages (photos/screenshots) so I
   can calibrate chunking strategy?
2. **Math in books** — Do the board book formulas contain complex diagrams, or
   mostly inline math?
3. **Book language** — Entirely Bengali, or English terms mixed in?
4. **Syllabus** — Is the Udvash weekly syllabus retrievable from their website?
   This would be the highest-leverage signal.
5. **Priority** — Start with Phase 1 (exam PDFs, simpler) or Phase 2 (OCR +
   knowledge base, higher value)?
