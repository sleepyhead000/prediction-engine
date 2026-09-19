# START HERE — Orientation for the AI Agent

You are working on **prediction-engine**, a system that predicts questions for
Udvash weekly exams (Bangladesh, HSC admission prep, Physics / Chemistry / Math,
Bengali language).

## Read the documents in this order

| # | File | What it is |
|---|------|-----------|
| 00 | `00-START-HERE.md` | This file |
| 01 | `01-BUG-REPORT.md` | Verified defects in the current code, with evidence |
| 02 | `02-ARCHITECTURE.md` | Target system design |
| 03 | `03-DATA-CONTRACTS.md` | JSON schemas every stage must emit/consume |
| 04 | `04-IMPLEMENTATION-PLAN.md` | Phased plan with acceptance gates |
| 05 | `05-BIJOY-DECODER-SPEC.md` | Spec for the text decoder (highest-risk component) |
| 06 | `06-PREDICTION-MODEL-SPEC.md` | The scoring model |
| 07 | `07-EVALUATION-PROTOCOL.md` | How "accuracy" is defined and measured |
| 08 | `08-LLM-PROMPTS.md` | Prompt templates for DeepSeek |
| 09 | `09-TASK-BACKLOG.md` | Ticket-by-ticket work queue — execute from here |

## Non-negotiable rules for this project

1. **Do not work on the prediction model before the parser passes its gate.**
   The current pipeline produces corrupted text. Every downstream metric is
   meaningless until Phase 1 is green. If you are asked to "improve accuracy"
   and the parser gate is red, fix the parser.

2. **Never delete raw data.** Parsed output is derived and disposable. The
   `.mhtml` and `.pdf` sources are not. Also persist the *raw extracted
   strings* (pre-decode) so a decoder fix can be replayed without re-scraping.

3. **Every stage writes to disk and is independently runnable.** No stage may
   call another stage's internals. Stages communicate only through the JSON
   contracts in `03-DATA-CONTRACTS.md`.

4. **No regex parsing of HTML.** Use `lxml` or `selectolax`. The current
   regex approach is the direct cause of three separate bugs (see 01).

5. **Cache all LLM calls** keyed on `sha256(prompt + model)`. Re-runs must be
   free. Store in `cache/llm/`.

6. **If you cannot verify something, say so in the code as a `# UNVERIFIED:`
   comment and surface it in the run report.** Do not silently guess. The
   previous version of this codebase accumulated ~200 hand-written "fix this
   garbled string" mappings that were compensating for one upstream bug; that
   pattern must not repeat.

7. **Determinism.** `temperature=0` for all classification and extraction
   calls. Only generation (Phase 5) may use temperature > 0.

## Glossary

- **Udvash / Unmesh** — the coaching institution whose exams we predict.
- **Daily** — short daily practice exam (MCQ 20 questions, or 1 written).
- **Weekly** — the target exam we are trying to predict.
- **Diff set** — an alternate version of the same exam, given to a different batch.
- **Question Bank** — Udvash's published book of past/practice questions.
- **Bijoy / SutonnyMJ** — legacy ASCII encoding for Bengali. Source pages use it.
- **Concept** — a leaf-level testable idea (e.g. "moment of a force about a
  point on a lever with a movable rider"), finer-grained than a chapter.

## Environment

- Python 3.11+
- LLM: DeepSeek via OpenAI-compatible endpoint. Existing local proxy at
  `LocalAPI/server.py` (`LOCALAI_URL` env var). Keep the proxy; swap the model.
- Vector store: ChromaDB, local persistent.
- No GPU assumed.

## What success looks like

`python -m engine.eval --holdout weekly_4` prints a scorecard, and
`concept_recall_at_30 >= 0.70` on that holdout, with the number reproducible
across runs.
