# prediction-engine

Predicts questions for Udvash/Unmesh weekly exams (Bangladesh, HSC admission
prep, Physics / Chemistry / Math).

## Quick Start (new PC)

```powershell
# 1. Clone
git clone https://github.com/sleepyhead000/prediction-engine.git
cd prediction-engine

# 2. Run setup (installs deps, sets env vars, creates dirs)
.\setup_env.ps1

# 3. Place your data
#    - English exam PDFs → sources/exams/
#    - Bengali board book PDFs → sources/books/

# 4. Run tests
python -m pytest tests/ -v

# 5. Start the pipeline
python -m engine.ingest
```

## Architecture

```
sources/
  exams/           ← English PDF text (PyMuPDF)
  books/           ← Bengali board book scans
      |
[1] ingest exams  →  data/01_questions.json
[2] OCR books     →  data/book_pages.jsonl
[3] chunk+anchor  →  data/book_chunks.json
[4] entities      →  data/book_entities.json
[5] concepts      →  data/book_concepts.json
[6] graph         →  data/book_graph.json
[7] index         →  ChromaDB
[8] classify      →  data/03_labelled.json
[9] features      →  data/04_features.json
[10] score        →  data/05_ranked.json
[11] generate     →  out/prediction_wN.json
[12] eval         →  out/scorecard_wN.json
```

## Project Structure

```
prediction-engine/
  engine/           ← Pipeline stage modules
    __init__.py
    schemas.py      ← Pydantic models for all JSON contracts
    llm.py          ← Cached LLM client (LocalAPI proxy)
  tests/            ← Test suite
  scripts/          ← Helper scripts
  files/            ← Design docs and specs
    00-START-HERE.md       ← Read this first
    01-BUG-REPORT.md
    02-ARCHITECTURE.md
    03-DATA-CONTRACTS.md
    04-IMPLEMENTATION-PLAN.md
    05-BIJOY-DECODER-SPEC.md
    06-PREDICTION-MODEL-SPEC.md
    07-EVALUATION-PROTOCOL.md
    08-LLM-PROMPTS.md
    09-TASK-BACKLOG.md
    10-REVISED-IMPLEMENTATION-PLAN.md  ← Current plan
  sources/          ← Raw data (read-only)
    exams/          ← English exam PDFs
    books/          ← Bengali board book scans
  ground_truth/     ← Labels and test data
  data/             ← Pipeline outputs (regenerated, git-ignored)
  cache/            ← LLM and model caches (git-ignored)
  out/              ← Final predictions (git-ignored)
  config/           ← Weights and config
  LocalAPI/         ← LLM proxy server (separate)
```

## Environment Variables

**Critical:** Model caches must NOT be on C: drive (space issues). The setup
script sets these automatically:

```powershell
$env:HF_HOME = "G:\prediction-engine\cache\huggingface"
$env:EASYOCR_MODEL_PATH = "G:\prediction-engine\cache\easyocr"
```

## Non-Negotiable Rules

1. Parser must pass gate before prediction model work
2. Never delete raw data
3. Every stage writes to disk independently
4. Cache all LLM calls keyed on sha256(prompt + model)
5. `temperature=0` for classification/extraction; only generation uses temp>0

## Dependencies

Python 3.11+ with: chromadb, easyocr, sentence-transformers, pymupdf,
pydantic, httpx, lxml, selectolax, rapidfuzz, pytest, ruff

## Design Docs

Read `files/00-START-HERE.md` for the full orientation. All design decisions
are documented in `files/`.
