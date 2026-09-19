# 04 — Implementation Plan

Six phases. Each has an **acceptance gate**. Do not start phase N+1 until
phase N's gate is green and the number is recorded in `out/gates.json`.

Rough effort estimates assume one person plus an AI agent. They are estimates,
not commitments.

---

## Phase 0 — Instrumentation (do this first, ~1 day)

You cannot improve what you cannot measure, and right now nothing is measured
(BUG-10).

**Tasks**

1. Create the repo layout from `02-ARCHITECTURE.md`. Move `debug*.py` to
   `scripts/`.
2. Implement `engine/schemas.py` from `03-DATA-CONTRACTS.md`.
3. Implement `engine/llm.py`: OpenAI-compatible client, disk cache keyed on
   `sha256(model + prompt + params)`, retry with backoff, `temperature=0`
   default, records token counts.
4. **Hand-label 120 questions** into `ground_truth/labels_v1.jsonl`:
   40 Physics, 40 Chemistry, 40 Math, drawn across dailies and weeklies.
   Include the human transcription of each question.
5. **Hand-type 200 decoder test vectors** into
   `ground_truth/decoder_vectors.tsv`. Source them from the same questions —
   copy the Bijoy string out of the HTML, type the correct Bengali.
6. Implement `engine/eval.py` with the metrics in
   `07-EVALUATION-PROTOCOL.md`. It must run and print zeros.

**Gate 0**
- `pytest tests/` passes (even with few tests)
- `python -m engine.eval --selftest` prints a full scorecard with the baseline
  numbers from the *current* pipeline, so you have a before/after

This step is boring and you will want to skip it. Don't. Every hour here saves
a day of arguing with an unmeasurable model later.

---

## Phase 1 — Text recovery (the actual blocker, ~3–5 days)

Fixes BUG-01 through BUG-06. Nothing downstream works until this lands.

**Tasks**

1. `engine/mathml.py` — MathML → LaTeX.
   - Handle at minimum: `mn mi mo mrow msub msup msubsup mfrac msqrt mroot
     mtext mspace mtable mtr mtd mover munder munderover mfenced`.
   - Chemistry: `C_{6}H_{14}` must round-trip. Test against the 110 `<math>`
     elements in `Chemistry/C1 MCQ 1.mhtml`.
   - Prefer an existing library if one handles these well; check
     `latexml`-style converters or write it — a recursive visitor over this
     tag set is under 200 lines.
   - **Read from `mjx-assistive-mml`, never from `mjx-math`.**

2. `engine/bijoy.py` — rewrite per `05-BIJOY-DECODER-SPEC.md`.

3. `engine/ingest.py` — DOM walk per `02-ARCHITECTURE.md`. Kills BUG-03 and
   BUG-04.

4. `engine/decode.py` — per-node decoding, `⟦Mn⟧` tokens. Kills BUG-01/02.

5. **Delete** `_GARBLED_MAP` and `normalize_bengali` from `classifier.py`
   in the same PR (BUG-06).

6. PDF text-layer extraction with font detection (BUG-08). Vision OCR becomes
   the rare fallback, and every use of it is logged.

**Gate 1** — measured by `python -m engine.eval --stage decode`
- `decode_report.clean_rate >= 0.95`
- `decode_report.math_conversion_rate >= 0.90`
- Decoder unit tests: `>= 0.97` exact match on `decoder_vectors.tsv`
- All MCQ questions have exactly 4 options
- Question bank PDFs yield `> 0` questions
- Character error rate against the 120 human transcriptions `<= 0.03`

If clean_rate stalls below 95%, look at
`decode_report.unmapped_glyph_frequency` — the top 20 entries will be most of
the remaining error. Fix those, re-run. Do not add per-word patches.

---

## Phase 2 — Knowledge base (~2–3 days)

**Tasks**

1. Ingest the textbooks. Chunk by heading. If the books are scanned, budget
   extra time for OCR and say so explicitly in the run report.
2. Ingest the question bank PDFs the same way.
3. `engine/taxonomy.py` — concept extraction (prompt T1), dedupe by embedding
   similarity, write `03_taxonomy.json`, index into Chroma.
4. Run the embedding sanity check from `02-ARCHITECTURE.md` § Embeddings.
   Record the number.

**Gate 2**
- Every chapter of every book maps to ≥1 concept
- Concept count per subject is between 80 and 400 (below 80 = too coarse to
  be useful; above 400 = fragmented, tighten the dedupe threshold)
- Embedding retrieval sanity check ≥ 17/20
- Spot-check: for 20 random labelled questions, the correct concept is in the
  top-8 retrieved candidates ≥ 18 times. **This is the ceiling on classifier
  accuracy** — if retrieval can't surface it, the LLM can't pick it.

---

## Phase 3 — Classification (~2 days)

**Tasks**

1. `engine/classify.py` — retrieve-then-select (prompt T2), with cache.
2. Route low-confidence items to `data/_review_queue.json`.
3. Run over all questions. Compare subject labels against filenames; log
   disagreements (BUG-07). Manually inspect the first 20 disagreements — they
   should mostly be the classifier being *right*.

**Gate 3** — against `ground_truth/labels_v1.jsonl`
- Subject accuracy ≥ 0.97
- Concept accuracy (exact `concept_id`) ≥ 0.80
- Concept accuracy (correct parent) ≥ 0.92
- `needs_review` rate ≤ 0.15

---

## Phase 4 — Measure the repeat rate (~half a day, high value)

**Do this before building the generator.** It decides whether Phase 6 is even
necessary, and it is the fastest way to learn something true about Udvash.

**Tasks**

1. Fuzzy-match every weekly question against (a) the question bank, (b) the
   dailies of the same week, (c) previous weeklies.
   - Match on: concept_id equality AND embedding cosine ≥ 0.85 AND numeric
     values compared separately.
   - Report three rates: *verbatim*, *same numbers different wording*,
     *same structure different numbers*.
2. Write `out/repeat_analysis.md`.

**Interpretation — decide and record the decision:**

| Structural reuse rate | What it means | What to build |
|---|---|---|
| ≥ 30% | Udvash recycles heavily | Retrieval-first. Rank bank questions. Generation optional. |
| 10–30% | Mixed | Hybrid: retrieve + perturb numbers. |
| < 10% | They genuinely write fresh | Generation-first, and lower your exact-hit expectations accordingly. |

Your stated premise is that Udvash deliberately avoids its own bank's
patterns. **This phase tests that premise.** If it turns out false, the whole
design gets simpler. If it's true, the `appeared_recently` penalty in the
model becomes the most important feature.

**Gate 4** — `out/repeat_analysis.md` exists, contains all three rates per
subject, and a written decision on which branch above you are taking.

---

## Phase 5 — Prediction model (~2–3 days)

**Tasks**

1. Investigate the weekly syllabus (see `02-ARCHITECTURE.md`). Timebox: 2
   hours. Record the outcome either way.
2. `engine/features.py` per `03-DATA-CONTRACTS.md`.
3. `engine/score.py` per `06-PREDICTION-MODEL-SPEC.md`.
4. Backtest: leave-one-week-out over the available weeklies. Fit weights.
   Write `config/weights.json` with a `weights_version` stamp.

**Gate 5**
- Backtest runs and is reproducible (same seed → same weights)
- `concept_recall@30` on the held-out week ≥ 0.55 (interim target)
- Calibration: predictions bucketed at 0.2/0.4/0.6/0.8 have observed
  frequencies within ±0.15 of the bucket
- **Overfit check:** with only ~4 weekly observations, a model with 10 free
  parameters will fit perfectly and predict nothing. Report the number of
  effective parameters alongside the score. If params > observations/2,
  reduce the model, do not celebrate the score.

---

## Phase 6 — Generation and loop closure (~2–3 days)

**Tasks**

1. `engine/generate.py` (prompt T3). Style exemplars pulled from the parsed
   weeklies — phrasing, numeric ranges, distractor construction.
2. Solvability check: a second LLM call solves each generated question
   independently (prompt T4). Discard any question the solver can't solve or
   where the solver's answer disagrees with the stated one.
3. `dashboard.py` rewired to new data.
4. `scripts/log_actual.py` — after each real weekly, ingest it and append to
   the outcome log.
5. Re-fit weights on each new observation.

**Gate 6**
- `concept_recall@30 >= 0.70` on the most recent held-out week
- Solvability filter rejects < 30% (higher means generation quality is poor)
- Two consecutive real weeklies logged and scored

---

## Ordering rationale

Phase 4 sits between classification and modelling on purpose: it is cheap,
and its result can cancel Phase 6. Phase 0 sits first because every later
phase's gate depends on it.

## What to do when a gate fails

1. Do not proceed.
2. Do not add a special-case patch to make the number go up.
3. Look at the per-item failures, find the largest cluster, fix that cause.
4. Re-run. Record both numbers.

The previous codebase failed by doing the opposite — `_GARBLED_MAP` is 200
special-case patches papering over one decoder bug.
