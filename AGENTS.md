# AGENTS.md — prediction-engine

Everything an AI agent needs to work on this codebase from scratch.

## Project Overview

**prediction-engine** predicts questions for Udvash/Unmesh weekly exams
(Bangladesh, HSC admission prep, Physics / Chemistry / Math).

The pipeline has 7 independent stages, each reading files, writing files,
and runnable alone. Stages communicate only through JSON contracts.

```
sources/                     ← raw .mhtml, .pdf (read-only)
    |
    v
[1] ingest      →  data/01_raw_nodes.json
[2] decode      →  data/02_questions.json
[3] taxonomy    →  data/03_taxonomy.json
[4] classify    →  data/04_labelled.json
[5] features    →  data/05_features.json
[6] score       →  data/06_ranked.json
[7] generate    →  out/prediction_wN.json|md
[8] eval        →  out/scorecard_wN.json
```

## Quick Start

```bash
# 1. Install dependencies
pip install -e .

# 2. Start LocalAPI proxy (for LLM calls)
cd LocalAPI && python server.py
# Runs on http://localhost:8000/v1

# 3. Run tests
pytest tests/

# 4. Run evaluation
python -m engine.eval --holdout weekly_4
```

## Non-Negotiable Rules

1. Do not work on the prediction model before the parser passes its gate.
2. Never delete raw data. Persist raw extracted strings (pre-decode).
3. Every stage writes to disk and is independently runnable.
4. No regex parsing of HTML. Use lxml or selectolax.
5. Cache all LLM calls keyed on sha256(prompt + model).
6. If you cannot verify something, say so as UNVERIFIED comment.
7. Determinism: temperature=0 for classification/extraction. Only generation uses temp>0.

## Environment

- Python 3.11+
- LLM: LocalAPI proxy at http://localhost:8000/v1, model localapi/mimo-v2.5-free
- All LLM calls go through engine/llm.py
- Cache at cache/llm/{sha256}.json
- Vector store: ChromaDB, local persistent
- No GPU assumed
