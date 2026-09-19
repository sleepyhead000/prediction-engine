# 02 — Target Architecture

## Design principle

Seven independent stages. Each reads files, writes files, and can be run
alone. No stage imports another stage's internals. This makes every stage
separately testable, which is the only way to attribute an accuracy change to
a cause.

```
  sources/                     ← raw .mhtml, .pdf, book PDFs (read-only)
      │
      ▼
 [1] ingest      →  data/01_raw_nodes.json        text nodes + math, undecoded
      │
      ▼
 [2] decode      →  data/02_questions.json        readable Bengali + LaTeX
      │
      ▼
 [3] taxonomy    →  data/03_taxonomy.json         concept tree from the books
      │                                            (+ chroma/ vector index)
      ▼
 [4] classify    →  data/04_labelled.json         question → concept
      │
      ▼
 [5] features    →  data/05_features.json         per-concept signal matrix
      │
      ▼
 [6] score       →  data/06_ranked.json           ranked concept predictions
      │
      ▼
 [7] generate    →  out/prediction_wN.json|md     30 concrete questions
      │
      ▼
 [8] eval        →  out/scorecard_wN.json         measured against reality
```

## Stage contracts

### [1] `engine/ingest.py`

Reads `sources/`. Produces a flat list of **nodes** per question, preserving
the original encoding. Does **no** decoding.

For `.mhtml`:
- Split MIME parts, find the part containing `class="questionBlock"`.
- Decode quoted-printable → UTF-8.
- Parse with `lxml.html` (not regex).
- For each `div.questionBlock`:
  - `div.questionText` → walk the subtree in document order.
    - A node inside `span.math-tex` → emit `{"kind":"math","mathml": <the
      inner <math> from mjx-assistive-mml>}`. **Skip the `mjx-math` sibling**
      — it is the visual rendering and duplicates the content.
    - Any other text node → emit `{"kind":"text","raw": <string>,
      "cls": <class attr>}`.
  - `div.questionOptions > div.questionOption` → one option each; same node
    walk; letter comes from `.input-group-text`.
- Assert: 20 question blocks for daily MCQ files, 4 options per MCQ question.
  On failure, write the file to `data/_ingest_failures/` and continue.

For `.pdf`:
- `page.get_text("dict")` to get spans with font names.
- If the span's font matches `SutonnyMJ|Sutonny|Bijoy|BijoyEkushey` (case
  insensitive) → `{"kind":"text","raw":…,"encoding":"bijoy"}`.
- If the font is a Unicode Bengali font → `{"kind":"text","raw":…,
  "encoding":"unicode"}`.
- Only if a page yields <20 characters of text → rasterise at 300 dpi and
  route to the vision fallback. Log every page that takes this path.

### [2] `engine/decode.py`

Consumes `01_raw_nodes.json`. For each node:
- `kind == "text"`, `encoding == "bijoy"` → `bijoy.decode(raw)`
- `kind == "text"`, `encoding == "unicode"` → passthrough + NFC normalise
- `kind == "math"` → `mathml_to_latex(mathml)`

Then assembles `question_text` by joining nodes in document order, replacing
each math node with a numbered token `⟦M0⟧`, `⟦M1⟧`, …, and storing the LaTeX
separately in `math_blocks`. **The token must use characters that cannot
appear in Bijoy input** — `⟦ ⟧` (U+27E6/U+27E7) satisfy this. Never use
ASCII brackets or the word "math".

Emits a per-file `decode_report` with:
- `% nodes decoded without residual Latin-1 high bytes`
- `% math blocks converted without falling back to raw text`
- list of unmapped Bijoy glyphs, with counts, sorted descending

That last list is the work queue for improving the decoder.

### [3] `engine/taxonomy.py`

Builds the concept tree from the actual textbooks, not a hardcoded list.

1. Chunk each book PDF by heading structure → `{book, chapter, section,
   page_start, page_end, text}`.
2. For each section, one LLM call (see `08-LLM-PROMPTS.md` § T1) to emit 3–12
   **concepts**: short, testable, in English, with Bengali keyword aliases.
3. Deduplicate concepts by embedding cosine similarity > 0.92.
4. Write `03_taxonomy.json` and index concepts + section text into Chroma.

The taxonomy replaces `classifier.py::TOPICS`, which is a generic
JEE-style list that does not match Udvash's chapter structure.

### [4] `engine/classify.py`

For each question:
1. Embed `question_text + math_blocks` (multilingual model; see § Embeddings).
2. Retrieve top-8 candidate concepts from Chroma.
3. One LLM call (prompt T2) → `{concept_id, subject, difficulty_1_5,
   question_form, confidence}`.
4. If `confidence < 60` or the LLM's concept is not in the candidate set,
   mark `needs_review: true` and write to `data/_review_queue.json`.

Cache on `sha256(question_text + math + model)`.

`question_form` is an enum: `numeric_single_step`, `numeric_multi_step`,
`conceptual_recall`, `graph_interpretation`, `statement_assertion`,
`matching`, `derivation`. This matters for Stage 7 — Udvash reuses *forms*
even when it changes numbers.

### [5] `engine/features.py`

Builds, per concept, the signal matrix consumed by the model. See
`06-PREDICTION-MODEL-SPEC.md` for the exact feature list. This stage does no
scoring — it only measures.

### [6] `engine/score.py`

Applies the scoring model. Outputs a ranked list with calibrated
probabilities. Weights are loaded from `config/weights.json`, which is
produced by the backtest in Stage 8 — never hand-edited.

### [7] `engine/generate.py`

Takes the top-N concepts and writes concrete questions using retrieved book
sections and style exemplars. Temperature 0.7 here (the only stage above 0).

### [8] `engine/eval.py`

See `07-EVALUATION-PROTOCOL.md`.

---

## Embeddings

Questions are Bengali with embedded LaTeX. Use a multilingual model. Candidate
options, in order of preference:

1. `intfloat/multilingual-e5-large` — runs locally, no API cost, good Bengali.
2. `BAAI/bge-m3` — also strong multilingual, larger.
3. DeepSeek/OpenAI embedding API — only if local is too slow.

**Do not use an English-only model.** Verify before committing: embed 20 pairs
of (Bengali question, its English concept label) and confirm the correct pair
ranks first for ≥17 of them. Record the number in the run report. If it fails,
translate questions to English first and embed that instead — but measure, do
not assume.

---

## The signal you are probably missing: the weekly syllabus

The saved MHTML files contain live URLs of the form:

```
https://online.udvash-unmesh.com/Exam/DisplayQuestion
    ?courseId=2993&routineId=158722&examId=127482&examType=1
    &uniqueset=1&solve=1&questionVersion=1&sheetType=solvesheet
```

`routineId` implies a routine endpoint exists. Udvash publishes, in advance,
which chapters each weekly exam covers.

**If that syllabus is retrievable, it is worth more than the entire model.**
Topic-level prediction becomes near-deterministic and the problem reduces to
"which concepts inside the announced chapters," which is both easier and more
useful.

**Task for the agent:** before building Stage 5–6, spend one task
investigating. Log into the portal manually, find the routine/syllabus page,
save it as `.mhtml` into `sources/routine/`, and write an ingest path for it.
If the syllabus is available, add `in_syllabus` as a feature with a dominant
weight and re-run the backtest — the improvement should be large and obvious.

If it is not retrievable, record that fact in the run report and move on. Do
not fabricate a syllabus.

---

## Repository layout after refactor

```
prediction-engine/
├── engine/
│   ├── __init__.py
│   ├── ingest.py
│   ├── decode.py
│   ├── bijoy.py            # decoder, per 05-
│   ├── mathml.py           # MathML → LaTeX
│   ├── taxonomy.py
│   ├── classify.py
│   ├── features.py
│   ├── score.py
│   ├── generate.py
│   ├── eval.py
│   ├── llm.py              # cached client
│   └── schemas.py          # pydantic models from 03-
├── config/
│   ├── weights.json        # produced by backtest
│   └── settings.toml
├── sources/                # read-only raw inputs
│   ├── dailies/
│   ├── weeklies/
│   ├── question_bank/
│   ├── books/
│   └── routine/
├── data/                   # stage outputs (gitignored except reports)
├── ground_truth/
│   ├── labels_v1.jsonl     # hand-labelled, per 07-
│   └── decoder_vectors.tsv # hand-typed, per 05-
├── cache/llm/
├── out/
├── tests/
└── scripts/                # old debug files go here or are deleted
```

## Deprecations

Delete once the replacement is green:

| Old | Replaced by |
|-----|-------------|
| `parser.py` | `engine/ingest.py` + `engine/decode.py` |
| `bijoy_decoder.py` | `engine/bijoy.py` |
| `classifier.py::TOPICS` | `engine/taxonomy.py` output |
| `classifier.py::_GARBLED_MAP` | nothing — delete (BUG-06) |
| `classifier.py::classify_by_keywords` | `engine/classify.py` |
| `classifier.py::classify_by_math_patterns` | same |
| `analyzer.py::generate_predictions` | `engine/score.py` |
| `debug2/3/4.py`, `check_unknowns.py` | `scripts/` or delete |

Keep: `dashboard.py` (rewire to new data), `LocalAPI/` (retarget to DeepSeek).
