# HANDOVER.md

Read this first. Everything you need to continue from where we left off.

## Project

Predicts questions for Udvash/Unmesh weekly exams (Bangladesh, HSC admission prep).

GitHub: `https://github.com/sleepyhead000/prediction-engine`

## Quick Start

```powershell
git clone https://github.com/sleepyhead000/prediction-engine.git
cd prediction-engine
pip install -e .

# Redirect model caches to a drive with space
$env:HF_HOME = "G:\prediction-engine\cache\huggingface"
$env:EASYOCR_MODEL_PATH = "G:\prediction-engine\cache\easyocr"

# Or run the setup script
.\setup_env.ps1
```

## Environment

- Python 3.14+
- LLM: LocalAPI proxy at `http://localhost:8000/v1`, model `localapi/mimo-v2.5-free`
- All LLM calls go through `engine/llm.py`
- ChromaDB 1.5.9, EasyOCR 1.7.2, sentence-transformers 6.1.0, PyMuPDF, pydantic 2.12

## What's Built

| Stage | Status | File | Notes |
|-------|--------|------|-------|
| Schemas | Done | `engine/schemas.py` | Bengali (old) + English (new) models side by side |
| LLM client | Done | `engine/llm.py` | Cached, retry, sha256 keys |
| Eval harness | Done | `engine/eval.py` | `python -m engine.eval --selftest` |
| Exam PDF ingest | Done | `engine/ingest.py` | 18 files, 359 questions, 358 with 4+ options |
| OCR infra | Done | `engine/ocr.py`, `engine/page_extractor.py` | EasyOCR wrapper + PDF renderer |
| OCR script | Done | `scripts/ocr_books.py` | Full pipeline, JSONL output |

## What's NOT Built (next steps)

| Stage | File to create | Depends on |
|-------|---------------|-----------|
| Run full OCR | Just run `scripts/ocr_books.py` | GPU recommended (~2h vs ~34h CPU) |
| Chapter detector | `engine/section_detector.py` | OCR output |
| Chunk splitter | `engine/chunker.py` | Section detector |
| Chunk enricher | `engine/enrich.py` | Chunks + LLM |
| ChromaDB indexer | `engine/indexer.py` | Enriched chunks |
| Classifier | `engine/classify.py` | Indexer + exam questions |
| Features + scoring | `engine/features.py`, `engine/score.py` | Classifier |
| Generation | `engine/generate.py` | Scoring |

## Data Layout

```
sources/
  books/                        # Bengali board book scans (image PDFs, NOT in git)
    chemistry_paper1/           # 2 chapters (Ch2: 173pp, Ch3: 319pp)
    math_paper1/                # 10 chapters (M-01 to M-10, 725pp total)
    math_paper2/                # 10 chapters (M-01 to M-10, 656pp total)
  dailies/week1/                # 18 daily MCQ MHTML files
  dailies/week2/                # 3 daily PDFs (analysis reports, skipped by ingest)
  weeklies/week1/               # 8 weekly MHTML files
  weeklies/week2/               # 8 MHTML + 3 diff set PDFs
  weeklies/week3/               # 8 MHTML files
  question_bank/                # Math2.pdf, Physics2.pdf

ground_truth/pdfs/              # Rendered PDFs from MHTML (git-ignored)
data/                           # Pipeline outputs (git-ignored, regenerate)
  01_questions.json             # 359 questions from 18 MCQ PDFs
  book_pages.jsonl              # (to be created) OCR output, 1873 pages
```

## Pipeline Architecture (8 stages)

```
[1] ingest exams     ->  data/01_questions.json       DONE
[2] OCR books        ->  data/book_pages.jsonl         READY TO RUN
[3] chunk+anchor     ->  data/book_chunks.json         TODO
[4] enrich chunks    ->  data/book_enriched.json       TODO (entities + concepts, single LLM call)
[5] index            ->  ChromaDB (persistent)         TODO
[6] classify         ->  data/03_labelled.json         TODO
[7] score            ->  data/05_ranked.json           TODO
[8] generate+eval    ->  out/prediction_wN.json        TODO
```

## Running Full OCR (first thing to do)

```powershell
# Install CUDA PyTorch for GPU acceleration
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Run OCR (with GPU)
$env:EASYOCR_MODEL_PATH = "G:\prediction-engine\cache\easyocr"
python -m scripts.ocr_books --src sources/books --out data/book_pages.jsonl
```

Takes ~2h on RTX 5060 Ti GPU, ~34h on CPU.

## Key Design Decisions

1. **Bijoy decoder eliminated** — using English-translated exam PDFs instead
2. **Collapsed 12 stages to 8** — entity graph deferred until 10+ weekly exams exist
3. **Single ChromaDB collection** — chunks with concept metadata, not two separate collections
4. **Analysis reports skipped** — C2, M2, P2 daily week2 PDFs are student performance reports, not raw exams
5. **Book PDFs not in git** — 450MB of binary scans, transfer separately
6. **Old Bengali schemas kept** — alongside new English schemas for reference

## Non-Negotiable Rules

1. Never delete raw data
2. Every stage writes to disk independently
3. Cache LLM calls on sha256(prompt + model)
4. temperature=0 for classification/extraction
5. All LLM calls through engine/llm.py
6. Mark uncertain things with UNVERIFIED comment

## Files to Read

- `files/10-REVISED-IMPLEMENTATION-PLAN.md` — full plan with 8 phases
- `files/07-EVALUATION-PROTOCOL.md` — metrics and scoring protocol
- `files/08-LLM-PROMPTS.md` — prompt templates
- `AGENTS.md` — agent reference doc
- `engine/schemas.py` — all data models
- `engine/ingest.py` — how PDF extraction works
- `engine/ocr.py` — how OCR works
- `scripts/ocr_books.py` — how to run full OCR
