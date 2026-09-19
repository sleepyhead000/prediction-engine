# 07 — Evaluation Protocol

Fixes BUG-10. Build this in Phase 0, before any other change.

## The problem with "70% accuracy"

As stated, the target is unmeasurable — "accuracy" of what, against what?
Three different things could be meant, and they have wildly different
difficulty. Pick one as the headline and report all three.

| Metric | What it measures | Realistic range | Use as |
|---|---|---|---|
| `topic_recall@10` | Did we name the right chapters? | 0.75–0.95 | Sanity check. Too easy to be the target. |
| `concept_recall@30` | Of the concepts actually tested, how many were in our top 30? | 0.40–0.80 | **Headline target: 0.70** |
| `question_hit@30` | How many real questions closely match one we generated? | 0.05–0.30 | Report honestly. Do not target 0.70. |

**`concept_recall@30` is the headline.** It is hard enough to be meaningful
and achievable enough to be worth chasing. Targeting 70% on
`question_hit@30` against a setter who deliberately writes fresh questions
would mean lying to yourself about the number.

---

## Metric definitions

### Stage metrics (Phases 1–3)

```
decode_clean_rate      = clean_questions / total_questions
                         (clean = no unmapped glyphs, no residual high Latin-1)

decode_cer             = mean character error rate vs the 120 human
                         transcriptions (Levenshtein / len(reference))

math_conversion_rate   = math_blocks_ok / math_blocks_total

option_completeness    = fraction of MCQs with exactly 4 non-empty options

subject_accuracy       = correct subject / labelled, vs labels_v1.jsonl

concept_accuracy       = exact concept_id match, vs labels_v1.jsonl
concept_parent_accuracy= parent concept match (partial credit)

retrieval_ceiling      = fraction of labelled questions whose true concept
                         appears in the top-8 retrieved candidates
```

`retrieval_ceiling` is the upper bound on `concept_accuracy`. If concept
accuracy is 0.70 and the ceiling is 0.72, fix retrieval, not the prompt.

### Prediction metrics (Phases 5–6)

Let `A` = set of concepts actually tested in the target weekly (derived by
running Stages 1–4 over the real exam paper once it exists).
Let `P_k` = our top-k predicted concepts.

```
concept_recall@k     = |A ∩ P_k| / |A|
concept_precision@k  = |A ∩ P_k| / k
weighted_recall@k    = Σ_{c∈A∩P_k} n_c / Σ_{c∈A} n_c
                       (n_c = number of real questions on c — weights the
                        concepts that were tested heavily)
mean_reciprocal_rank = mean over c∈A of 1/rank(c), 0 if unranked
brier                = mean( (p_c − y_c)² ) over all concepts
```

Report `concept_recall@10`, `@20`, `@30`, `@50`. A curve is more informative
than a point, and it tells you where to set k in practice.

### Generation metrics (Phase 6)

```
question_hit@30      = fraction of real questions with ≥1 generated question
                       scoring "match" (definition below)
solvability_pass     = fraction of generated questions the independent
                       solver agrees with
style_plausibility   = human 1–5 rating on a sample of 20 (you rate these)
```

**Match definition** — three tiers, report separately:

- **exact** — same concept, embedding cosine ≥ 0.92, same numeric values
- **structural** — same concept, same `question_form`, cosine ≥ 0.85,
  different numbers
- **conceptual** — same concept only

`question_hit@30` uses the **structural** tier. A student who practised a
structurally identical question is prepared; that is the real-world meaning
of a hit.

---

## Backtest protocol

With 4 weekly exams you get 4 folds and no true test set. Be honest about
this in every report.

```
for held_out in weeklies:
    train_weeks = all weeklies except held_out
    fit weights on train_weeks
    build features for held_out using ONLY data with
        captured_at < held_out.captured_at
    score, rank, evaluate
report mean, min, max, std across folds
```

**Leakage checklist — the agent must assert each of these:**

- [ ] No question from the held-out exam appears in the training features
- [ ] `bank_frequency` is computed from the question bank only, not from
      weeklies
- [ ] `daily_signal` uses dailies from the held-out week — this is
      legitimate, they are published before the weekly
- [ ] `appeared_last_weekly` refers to W−1 relative to the held-out week,
      not to absolute week 3
- [ ] Concept taxonomy is built from books only, never from exam questions
- [ ] LLM cache keys include the week, so a cached label from the held-out
      exam cannot leak in

The taxonomy one is the subtle one. If concepts are derived from the exam
questions, the held-out exam has shaped the label space, and recall is
inflated. Build the taxonomy from books only.

---

## Scorecard format

`out/scorecard_wN.json`, and a human-readable `out/scorecard_wN.md`:

```
═══ SCORECARD — target week 5 ═══
weights_version: bt_2026-09-19_loo   fitted: true
syllabus_available: true

STAGE HEALTH
  decode_clean_rate         0.968   (gate 0.95)  PASS
  decode_cer                0.019   (gate 0.03)  PASS
  math_conversion_rate      0.941   (gate 0.90)  PASS
  option_completeness       1.000   (gate 1.00)  PASS
  subject_accuracy          0.983   (gate 0.97)  PASS
  concept_accuracy          0.812   (gate 0.80)  PASS
  retrieval_ceiling         0.925

PREDICTION (leave-one-week-out, n_folds=4)
  concept_recall@10    mean 0.48   [0.41 – 0.55]
  concept_recall@20    mean 0.63   [0.52 – 0.71]
  concept_recall@30    mean 0.72   [0.61 – 0.79]   ← HEADLINE  PASS
  weighted_recall@30   mean 0.78
  brier                     0.112
  MRR                       0.31

GENERATION
  question_hit@30 (structural)   0.21
  question_hit@30 (exact)        0.04
  solvability_pass               0.86

WARNINGS
  ! n_features=6, n_independent_observations=4 — model is
    overparameterised; treat fitted weights as provisional
  ! fold spread on concept_recall@30 is 0.18 — near the 0.25
    instability threshold
```

The WARNINGS block is not optional. A scorecard that reports 0.72 without
noting it came from 4 observations is misleading, including to you.

---

## Per-subject breakdown

Always report metrics split by Physics / Chemistry / Math. Prediction is
Math's weakest case — Math questions are mostly formula, which is exactly
what the current pipeline destroys (BUG-02), and Math concepts are more
combinatorial (a question can span three at once). If the aggregate looks
fine and Math is at 0.45, you need to know that.

---

## Logging real outcomes

`scripts/log_actual.py --week N --paper path/to/real_weekly.mhtml`

1. Runs Stages 1–4 on the real paper.
2. Appends to `ground_truth/outcomes.jsonl`:
   `{week, concept_id, n_questions, subject}`
3. Re-scores the prediction that was made for that week.
4. Appends the scorecard to `out/history.jsonl`.

**Run this after every weekly, without exception.** You have maybe 3–6 more
exams before this matters to you. Each one is 25% of your data.

---

## Anti-gaming rules

The point of the metric is to tell you the truth, so:

1. Predictions for week N must be written to disk **before** week N's paper
   is ingested. `eval.py` refuses to score a prediction whose file mtime is
   later than the paper's. Enforce this in code.
2. Never tune weights on a week you have already scored and reported. Move
   it to the training set and report the new number separately.
3. If you change the concept taxonomy, all historical scores are invalid.
   Re-run the full history, or version the taxonomy and report which version
   each score used.
4. `concept_recall@k` rises trivially with k. Always report the k. "70%
   accuracy" with an unstated k=200 is meaningless.
