# 09 — Task Backlog

Execute in order. Each ticket is scoped to be completable and verifiable on
its own. Mark done only when the **Verify** step passes.

Format: `ID | title | fixes | verify`

---

## Phase 0 — Instrumentation

### T-001 — Repo skeleton
Create the layout in `02-ARCHITECTURE.md` § Repository layout. Move
`debug2.py`, `debug3.py`, `debug4.py`, `check_unknowns.py` to `scripts/`.
Add `pyproject.toml`, pin deps, add `lxml`, `chromadb`, `pydantic`,
`sentence-transformers`, `rapidfuzz`, `scikit-learn`, `pytest`.
**Fixes:** BUG-11
**Verify:** `python -c "import engine"` succeeds; `pytest` collects 0 tests
without error.

### T-002 — Schemas
Implement every model in `03-DATA-CONTRACTS.md` as pydantic v2 models in
`engine/schemas.py`, with the stated invariants as validators.
**Verify:** round-trip test — construct each model, serialise, deserialise,
assert equality. Invariant violations raise.

### T-003 — Cached LLM client
`engine/llm.py`. Disk cache at `cache/llm/{sha256}.json`. Retry with
exponential backoff on 429/5xx. Tolerant JSON extraction with a counter for
how often the tolerant path fires. Token accounting.
**Verify:** call the same prompt twice; second call makes no network request
and returns identical output.

### T-004 — Ground truth: question labels
Hand-label 120 questions into `ground_truth/labels_v1.jsonl` (40 per
subject, spread across dailies and weeklies). Include the human's own
transcription of the Bengali.
**Note:** this is human work, not agent work. The agent should produce a
labelling helper script that renders each question's source HTML to a
browser-viewable file so the human can read the original.
**Verify:** 120 lines, schema-valid, no duplicate `qid`.

### T-005 — Ground truth: decoder vectors
200 lines in `ground_truth/decoder_vectors.tsv`. Again human work; the agent
provides `scripts/extract_bijoy_strings.py` which dumps candidate Bijoy
strings with their rendered-page context.
**Verify:** 200 lines, 2 tab-separated columns, column 2 is valid Bengali
(all chars in U+0980–U+09FF, space, or punctuation).

### T-006 — Evaluation harness
`engine/eval.py` implementing every metric in `07-EVALUATION-PROTOCOL.md`.
Includes the anti-gaming mtime check and the WARNINGS block.
**Fixes:** BUG-10
**Verify:** `python -m engine.eval --selftest` emits a full scorecard against
the *current* pipeline. Record these baseline numbers in `out/gates.json`.

**GATE 0** — T-001…T-006 complete, baseline recorded.

---

## Phase 1 — Text recovery

### T-010 — MathML to LaTeX
`engine/mathml.py`. Recursive visitor over the tag set in
`04-IMPLEMENTATION-PLAN.md` Phase 1. Read only from `mjx-assistive-mml`.
**Fixes:** BUG-02 (part)
**Verify:** extract all 110 `<math>` elements from
`Chemistry/C1 MCQ 1.mhtml`; ≥ 90% convert without falling back; the
chemical-formula and decimal-number cases from the bug report produce
correct LaTeX. Unit tests for each supported tag.

### T-011 — Bijoy decoder rewrite
`engine/bijoy.py` per `05-BIJOY-DECODER-SPEC.md`. Tokenise → cluster →
reorder → emit. Returns `DecodeResult` with `unmapped`.
**Fixes:** BUG-05
**Verify:** the four worked examples in the spec pass as asserts; all four
properties (no residual high Latin-1, idempotence, no orphan marks, vector
match) are tested; ≥ 0.90 on `decoder_vectors.tsv` at this ticket (0.97 is
the gate, reached via T-014).

### T-012 — DOM-based ingest
`engine/ingest.py`. `lxml`, no regex. Node walk. Option extraction via
`div.questionOption`. Emits `01_raw_nodes.json`.
**Fixes:** BUG-03, BUG-04
**Verify:** all 34 MHTML files parse; every daily MCQ file yields exactly 20
questions; every MCQ question yields exactly 4 options with non-empty text;
`ingest_report.files_failed == 0`.

### T-013 — Per-node decode stage
`engine/decode.py`. `⟦Mn⟧` tokens. Emits `02_questions.json` with
`raw_preserved` and `decode_quality`.
**Fixes:** BUG-01
**Verify:** grep the output for the string `সধঃয` — zero hits. Grep for
`[math:` — zero hits. `raw_preserved` present on every question.

### T-014 — Glyph table closure loop
`scripts/show_glyph_context.py`. Run the unmapped-glyph workflow from the
spec for 10 iterations. Each iteration: top-10 unmapped glyphs, human
confirms, mapping + test vector added.
**Verify:** `decode_report.clean_rate ≥ 0.95`; decoder vector pass rate
≥ 0.97; CER vs the 120 transcriptions ≤ 0.03.

### T-015 — Delete the garbled map
Remove `_GARBLED_MAP`, `normalize_bengali`, `classify_by_math_patterns`, and
`classify_by_keywords` from `classifier.py`. Delete `bijoy_decoder.py`.
**Fixes:** BUG-06
**Verify:** `grep -r "_GARBLED_MAP\|normalize_bengali" engine/` returns
nothing; Gate-1 metrics unchanged or improved after removal. *If metrics
drop, the new decoder is not actually done — go back to T-014.*

### T-016 — PDF text-layer ingest
Font-aware extraction per `05-BIJOY-DECODER-SPEC.md` § PDF. OCR only as
logged fallback.
**Fixes:** BUG-08
**Verify:** all five PDFs yield `question_count > 0`; the fraction of pages
routed to OCR is reported; spot-check 10 extracted questions by eye.

**GATE 1** — all Phase 1 metrics green. Record in `out/gates.json`.
**Do not proceed otherwise.**

---

## Phase 2 — Knowledge base

### T-020 — Book ingest and sectioning
Chunk book PDFs by heading. Count worked examples and exercise problems per
section (these feed `book_weight`).
**Verify:** section count per book is plausible (10–80); no section exceeds
20k characters; page ranges are contiguous and non-overlapping.

### T-021 — Embedding model selection
Run the sanity check in `02-ARCHITECTURE.md` § Embeddings on 2–3 candidate
models. Pick one, record the score.
**Verify:** chosen model scores ≥ 17/20; the number is in `out/gates.json`.

### T-022 — Concept extraction
`engine/taxonomy.py` with prompt T1. Dedupe at cosine > 0.92. Verify
`grounding_quote_bn` appears in the source section; drop and log those that
don't.
**Verify:** 80–400 concepts per subject; every chapter has ≥1 concept;
hallucination drop rate < 5%.

### T-023 — Vector index
Index concepts and section text into Chroma, persistent.
**Verify:** `retrieval_ceiling ≥ 0.90` on the labelled set (true concept in
top-8). If below, revisit chunk size or the embedding model — do not proceed
and hope the LLM compensates.

**GATE 2**

---

## Phase 3 — Classification

### T-030 — Classifier
`engine/classify.py`, prompt T2, retrieve-then-select, cached.
**Fixes:** BUG-07
**Verify:** subject accuracy ≥ 0.97, concept accuracy ≥ 0.80, parent
accuracy ≥ 0.92 against `labels_v1.jsonl`.

### T-031 — Disagreement review
Produce `out/subject_disagreements.md` listing every question where the
classifier's subject differs from the filename. Human reviews the first 20.
**Verify:** the file exists; the human's verdict on those 20 is recorded.
Expect most to be the classifier being right (e.g. the lever problem in the
Chemistry file).

### T-032 — Review queue
Low-confidence routing and a small CLI for a human to resolve them.
**Verify:** `needs_review` rate ≤ 0.15; resolved labels are written back and
merged into `labels_v1.jsonl` as `labelled_by: "human"`.

**GATE 3**

---

## Phase 4 — Repeat-rate measurement

### T-040 — Repeat analysis
`scripts/repeat_analysis.py`. Match weekly questions against bank, same-week
dailies, and previous weeklies. Three tiers (verbatim / same-numbers /
same-structure), per subject.
**Verify:** `out/repeat_analysis.md` exists with all rates and a written
decision on the retrieval-vs-generation branch from
`04-IMPLEMENTATION-PLAN.md` Phase 4.

**This ticket can change the rest of the plan. Read the result before
continuing.**

**GATE 4**

---

## Phase 5 — Prediction model

### T-050 — Syllabus investigation
Timebox 2 hours. Find the Udvash routine/syllabus page for the target
course. Save to `sources/routine/`. If found, write an ingest path and add
`in_syllabus` as a feature.
**Verify:** either `sources/routine/` contains a saved syllabus and
`in_syllabus` is populated, **or** `out/syllabus_investigation.md` records
what was tried and why it failed. Do not leave this ambiguous.

### T-051 — Feature builder
`engine/features.py`. All features in `03-DATA-CONTRACTS.md`.
**Verify:** no NaNs; feature value ranges match the spec table; the leakage
checklist from `07-EVALUATION-PROTOCOL.md` is implemented as assertions that
run on every build.

### T-052 — Scorer
`engine/score.py`. Beta-Binomial base + log-linear adjustment. Emits
`contributions` per concept.
**Fixes:** BUG-09
**Verify:** contributions sum to the final logit within 1e-6; `analyzer.py`'s
old prediction path is deleted.

### T-053 — Backtest and weight fitting
Leave-one-week-out. Writes `config/weights.json` with `weights_version` and
`fitted: true|false`. Applies the instability fallback if spread > 0.25.
**Verify:** reproducible with a fixed seed; the WARNINGS block correctly
fires on overparameterisation; `concept_recall@30 ≥ 0.55`.

### T-054 — TimesFM comparison (optional, non-blocking)
Only if you still want it. Run TimesFM on the per-concept series as a
*separate* column in the scorecard. Keep it out of the scoring path.
**Verify:** scorecard shows both; a written note on whether it beat the
baseline. Expect it not to, for the reasons in `06-PREDICTION-MODEL-SPEC.md`.
If it does beat the baseline at n=4, be suspicious of leakage before being
pleased.

**GATE 5**

---

## Phase 6 — Generation and loop closure

### T-060 — House-style extractor
Compute stem length distribution, numeric ranges, and distractor patterns
from the parsed weeklies. Feeds T3's "OBSERVED HOUSE STYLE" block.
**Verify:** values are computed, not hardcoded; they change when a new exam
is ingested.

### T-061 — Generator
`engine/generate.py`, prompt T3, temperature 0.7.
**Verify:** 30 questions produced for a target week; each cites
`based_on.book_sections`.

### T-062 — Solvability filter
Prompt T4 in a fresh context, answer hidden.
**Verify:** discard rate reported; < 30%.

### T-063 — Output rendering
`prediction_wN.json` plus a readable `prediction_wN.md` with Bengali,
rendered maths, and per-question probability.
**Verify:** the markdown renders correctly; Bengali displays without
mojibake.

### T-064 — Dashboard rewire
Point `dashboard.py` at the new data files.
**Verify:** runs; shows stage health, ranked concepts with contributions,
and the scorecard history.

### T-065 — Outcome logging
`scripts/log_actual.py` per `07-EVALUATION-PROTOCOL.md`.
**Verify:** run it against one existing weekly as a dry run; `out/history.jsonl`
gains a row.

**GATE 6** — `concept_recall@30 ≥ 0.70` on the most recent holdout, two real
weeklies logged.

---

## Standing tasks

- **After every real weekly:** run `log_actual.py`, re-fit, commit the
  scorecard. This is the only mechanism that improves the model over time,
  and you have few exams left before it matters.
- **Never** add a special case to make a metric move. Find the cause.
- **Keep the WARNINGS block visible.** A number without its caveat is worse
  than no number.

---

## Known unknowns — do not fabricate answers to these

These are genuinely open. The agent should investigate and report, not
assume.

1. Whether the Udvash weekly syllabus is retrievable (T-050). This is the
   single highest-leverage unknown.
2. The actual structural repeat rate between question bank and weeklies
   (T-040). The whole premise of "they avoid their own patterns" rests on it.
3. Whether the textbooks are digital-text or scanned. Affects Phase 2 effort
   substantially.
4. The Bijoy mapping for `½` and the rest of the U+00A0–U+00FF conjunct
   block (T-014).
5. Whether Bengali embedding quality is good enough for concept retrieval
   (T-021). If not, an English-translation intermediate step is needed and
   Phase 2 grows.
