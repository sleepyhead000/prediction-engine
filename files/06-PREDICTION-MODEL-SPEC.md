# 06 — Prediction Model Specification

Replaces `analyzer.py::generate_predictions` (BUG-09).

## What the model predicts

For a target week *W* and each concept *c* in the taxonomy:

> **P(concept c is tested in weekly exam W)**

and a secondary estimate of **expected number of questions** on *c*.

It does **not** predict exact question text. That is Stage 7's job, and it is
conditioned on this ranking.

---

## On TimesFM — a recommendation against

You asked about using TimesFM as an auxiliary model. My honest read: it will
not help here, and I'd rather tell you that than build something that looks
sophisticated.

**The reasons:**

1. **Series length.** You have 4 weekly exams. TimesFM is a foundation model
   for time series with context windows measured in hundreds to thousands of
   points. A length-4 input is below the regime it was trained for. It will
   return a number, and that number will be shaped by the model's priors
   rather than by your data.

2. **Wrong target.** TimesFM forecasts a continuous quantity. Your per-concept
   series is a sparse binary vector, mostly zeros — about 200 concepts × 4
   weeks, of which maybe 60 cells are 1. That is a rare-event classification
   problem, not a forecasting problem.

3. **No exogenous inputs.** The signals that actually matter here — the
   announced syllabus, what the dailies drilled this week, whether the concept
   appeared last week — are covariates. TimesFM's value is in extrapolating
   endogenous temporal structure. There isn't any yet.

4. **Undebuggable.** When a prediction is wrong you need to know which signal
   misfired. A foundation model gives you no handle on that, and at your data
   volume you cannot diagnose it statistically either.

**What to do instead:** a Beta-Binomial per concept does the same job in
~20 lines, is calibrated, and every parameter is inspectable. Specified below.

**When to revisit:** once you have ~20+ weekly exams logged, there may be
genuine seasonality (revision weeks, pre-exam consolidation) worth modelling.
At that point, evaluate TimesFM against the linear baseline on a proper
holdout. Adopt it only if it wins. Right now there is nothing for it to learn.

If you want to use it anyway for your own curiosity, fine — but keep it
**strictly out of the scoring path** and compare it against the baseline in
the scorecard. Don't let it silently influence the number you report.

---

## Model

### Layer 1 — Base rate (Beta-Binomial)

Each concept gets a prior from static evidence and a posterior from observed
exams.

```
prior_strength   = κ                    (tune; start κ = 8)
prior_mean_c     = normalise( α·book_weight_c + β·bank_frequency_c )
a_c              = κ · prior_mean_c
b_c              = κ · (1 − prior_mean_c)

observed:  n_c = number of past weeklies in which c appeared
           N   = number of past weeklies

posterior_mean_c = (a_c + n_c) / (a_c + b_c + N)
```

With N=4 the prior dominates, which is correct — you genuinely do not have
enough observations to override the book.

`book_weight_c`: share of the book devoted to the concept, computed as
`0.5·(pages_share) + 0.5·(exercise_problems_share)`. Exercises are the better
signal; pages include prose the examiner ignores.

`bank_frequency_c`: share of question-bank questions labelled with *c*.

### Layer 2 — Contextual adjustment (log-linear)

```
logit(p_c) = logit(posterior_mean_c)
           + w_syl  · in_syllabus_c
           + w_dly  · daily_signal_c
           + w_rep  · appeared_last_weekly_c        (expected negative)
           + w_gap  · log1p(weeks_since_last_c)
           + w_dif  · diffset_signal_c
           + w_pre  · prereq_covered_c
```

### Feature definitions

| Feature | Definition | Range | Expected sign |
|---|---|---|---|
| `in_syllabus` | concept's chapter is in the announced syllabus for week W | 0/1 | **strongly +** |
| `daily_signal` | share of week-W daily questions labelled *c* | 0–1 | + |
| `appeared_last_weekly` | *c* appeared in weekly W−1 | 0/1 | **−** (see below) |
| `weeks_since_last` | weeks since *c* last appeared in any weekly | 0–N | + |
| `diffset_signal` | *c* appeared in the diff set for this week | 0/1 | + |
| `prereq_covered` | all prerequisite concepts already taught | 0/1 | + |
| `form_diversity` | distinct `question_form`s seen for *c* | int | + (weak) |

### The avoidance term

Your premise — that Udvash does not follow its own question-bank patterns —
is encoded as `w_rep` and `w_gap`. **Do not hardcode these as negative. Fit
them and look at the sign.**

- If `w_rep` comes out clearly negative, your premise is confirmed and this
  is the most interesting thing the model has learned.
- If it comes out near zero or positive, your premise is wrong and you should
  say so in the run report rather than forcing it.

Phase 4 (`out/repeat_analysis.md`) gives an independent read on the same
question. The two should agree. If they don't, something is wrong with the
labelling — investigate before trusting either.

### `in_syllabus` gating

If the syllabus is retrievable, do not treat it as one feature among seven.
Apply it as a **hard filter with a soft escape**:

```
if syllabus_available:
    if not in_syllabus_c:
        p_c *= 0.08        # not zero — setters do include revision items
```

Fit that 0.08 from the backtest if you have enough data; otherwise state it
as an assumption in the report. A gated model with a good syllabus will beat
an ungated model with a clever score, every time.

---

## Fitting

**Method:** L2-regularised logistic regression on the Layer-2 features, with
`logit(posterior_mean_c)` as a fixed offset (not a fitted coefficient).

**Data:** one row per `(concept, past_week)`. With 4 weeklies and ~200
concepts per subject that is ~2400 rows, but only ~60 positives. Heavily
imbalanced; use class weighting.

**Validation:** leave-one-week-out. Fit on weeks {1,2,3}, evaluate on {4};
then {1,2,4}→{3}; etc. Report mean and spread across folds. **The spread
matters more than the mean at this sample size** — if fold scores range
0.35–0.85, you have learned nothing stable, and you should say so.

**Regularisation:** strong. Start `C = 0.1`. With 6 features and 4 weekly
observations, the effective sample size is closer to 4 than to 2400 —
concepts within a week are not independent.

**Guardrail:** report `n_features` and `n_independent_observations` in every
scorecard. If `n_features > n_independent_observations / 2`, print a warning
in the output. Do not suppress it.

---

## Fallback when fitting is unstable

If leave-one-out spread exceeds 0.25, abandon fitting and use fixed weights
based on reasoning rather than data:

```json
{
  "w_syl": 2.5, "w_dly": 0.9, "w_rep": -0.5,
  "w_gap": 0.3, "w_dif": 0.6, "w_pre": 0.4,
  "kappa": 8, "alpha": 0.6, "beta": 0.4,
  "weights_version": "hand_v1_unfitted"
}
```

Mark these `"fitted": false` in `config/weights.json`. Hand-set weights that
are honestly labelled are better than fitted weights that are secretly noise.
Re-attempt fitting after every 4 new weekly observations.

---

## Calibration

After scoring, check reliability: bucket predictions at 0.0–0.2, 0.2–0.4, …
and compare predicted vs observed frequency. Apply isotonic regression only
once you have ≥ 8 weeks of outcomes; before that there isn't enough data to
calibrate against and you will just fit noise.

---

## Output

`06_ranked.json` per `03-DATA-CONTRACTS.md`. The `contributions` object is
mandatory — for each concept, the additive contribution of each term to the
final logit. Without it you cannot answer "why is this ranked first," which
is the question you will actually want to ask.

---

## Question-count estimate

```
expected_count_c = p_c × (avg_questions_per_weekly / expected_distinct_concepts)
```

Keep it simple. This number is advisory, for deciding how many questions to
generate per concept in Stage 7. Do not report it as a prediction.
