# 01 — Bug Report (Verified Against the Repository)

All findings below were reproduced against commit `main` of
`github.com/sleepyhead000/prediction-engine`. Each has evidence. Fix them in
the order given; several are the same root cause.

---

## BUG-01 — `html_to_text()` Bijoy-decodes the whole string, including ASCII markup

**Severity: critical. This is the root cause of BUG-02 and most of the
"garbled Bengali" that `classifier.py` tries to patch over.**

In `parser.py::html_to_text()`, MathML is first replaced with the literal
placeholder `" [math:...] "`, and *then* the entire resulting string is passed
through `decode_bijoy()`. The decoder treats the ASCII word `math` as Bijoy
input and converts it.

Evidence — from committed `parsed_questions.json`:

```
"question_text": "... বীমর সববাম  [সধঃয:০]  দ াগ থক ..."
```

`সধঃয` is `decode_bijoy("math")`. Every single math placeholder in the
committed dataset is corrupted this way.

**Fix:** decode per text node. Never pass a mixed ASCII/placeholder string
through the decoder. See `02-ARCHITECTURE.md` § DOM walk.

---

## BUG-02 — All mathematical and chemical content is destroyed

**Severity: critical.**

The source `.mhtml` files contain real MathML inside
`<mjx-assistive-mml><math>…</math></mjx-assistive-mml>`. Confirmed counts in
`Chemistry/C1 MCQ 1.mhtml`: 110 `<math>` elements, 9167 `mjx-*` elements.

`mathml_to_text_simple()` flattens these to bare digit strings, then BUG-01
mangles the wrapper. Net result:

| Source (real MathML) | Current output |
|---|---|
| `C₆H₁₄` | `[সধঃয:৬ ১৪ ঈ ঐ ( )]` |
| `44.8 L` | `[সধঃয:৪৪.৮ খ]` |
| `62.241 g` | `[সধঃয:৬২.২৪১ ম]` |

Note the element symbols have been Bengali-transliterated (`C`→`ঈ`, `H`→`ঐ`,
`L`→`খ`, `g`→`ম`) because BUG-01 fed Latin letters to the Bijoy map.

**Consequence:** Chemistry and Math are effectively unclassifiable. Roughly
every numeric answer option in the dataset is destroyed.

**Fix:** MathML → LaTeX conversion, preserved as a structured field, never
inlined into the Bengali string before decoding. See
`03-DATA-CONTRACTS.md` § `math_blocks`.

---

## BUG-03 — Bengali span selector is too narrow

**Severity: high.**

`parser.py` selects Bengali text with:

```python
r'<span[^>]*class="pt-000001[^"]*"[^>]*>([^<]+)</span>'
```

But the class prefix varies by paragraph style. Observed in the same file:

- `pt-000000` + uuid  ← used inside answer options
- `pt-000001` + uuid  ← body text
- `pt-000002` + uuid  ← quotes / special glyphs
- `pt-000003` + uuid  ← paragraph-level

Only `pt-000001` is captured. This is why every MCQ option in
`parsed_questions.json` contains *only* a math placeholder and no Bengali —
the option text uses `pt-000000`.

**Fix:** match `^pt-\d{6}` (or simply: decode every text node not inside a
`math-tex` / `mjx-*` subtree).

---

## BUG-04 — MCQ option D is systematically lost

**Severity: high.**

Every MCQ in `parsed_questions.json` has exactly 3 options (A, B, C). The
source HTML has 4. The option regex in `extract_questions_regex()`:

```python
r'<span class="input-group-text">([A-D])</span>.*?'
r'<div class="[^"]*questionTable[^"]*">(.*?)</div>'
```

`(.*?)</div>` is non-greedy against *nested* `<div>`s, so matches consume
inconsistent spans and the final option falls outside the iteration.

**Fix:** DOM traversal. Select `div.questionOptions > div.questionOption`,
then read the `.input-group-text` and `.questionTable` children of each.
Assert `len(options) == 4` for MCQ and fail loudly otherwise.

---

## BUG-05 — Bijoy decoder drops pre-base vowels, ja-phala, and reph

**Severity: critical.**

`bijoy_decoder.py::decode_bijoy()` does not implement:

- **`†` (pre-base kar reorder)** — in Bijoy the ে/ো vowel sign is typed
  *before* the consonant; Unicode stores it *after*. Not reordered → dropped.
- **`¨` → `্য` (ja-phala)** — passed through raw.
- **`©` → `র্` (reph)** — must be reordered to before the cluster; passed
  through raw.
- **Multi-byte conjunct glyphs** — `¼`(ঙ্ক), `Ý`(ন্স), `½`, `¤`, `ª` etc.
  pass through raw.

Reproduced test:

```
input:    e¨v‡j‡Ý ex‡gi me©ev‡g †_‡K †gvU
current:  ব¨ালÝ বীমর সব©বাম †থক †মাট
expected: ব্যালেন্সে বীমের সর্ববামে থেকে মোট
```

**Fix:** full rewrite per `05-BIJOY-DECODER-SPEC.md`.

---

## BUG-06 — `classifier.py` contains ~200 hand-written corruption patches

**Severity: high (technical debt / correctness hazard).**

`_GARBLED_MAP` maps corrupted strings to intended Bengali, e.g.
`'িবিqািট' → 'বিক্রিয়াটি'`. These exist solely to compensate for BUG-05.

Once BUG-05 is fixed these mappings become actively harmful: they will match
substrings of *correct* Bengali and rewrite it.

**Fix:** delete `_GARBLED_MAP` and `normalize_bengali()` entirely in the same
commit that lands the new decoder. Do not keep them "just in case."

---

## BUG-07 — Subject labels are wrong

**Severity: high.**

`parsed_questions.json`, file `Chemistry/C1 MCQ 1.mhtml`, question 1:

> "পুল-বুঞ্চ ব্যালেন্সে বীমের সর্ববামে '0' দাগ থেকে … রাইডার … বস্তুর ভর কত?"

This is a **Physics** lever/balance problem, tagged `"subject": "Chemistry"`
because the filename starts with `C`.

Additionally, `classifier.py::_detect_subject_from_text()` includes these as
"Math" patterns:

```python
r'ই',   # matches in a large fraction of Bengali sentences
r'অ',   # same
r'ভর',  # also listed under Physics
r'ফল',  # also common
```

Single-character Bengali patterns scored at weight 2 will dominate. Subject
detection is close to random.

**Fix:** derive subject from the LLM classification pass against a real
syllabus taxonomy. Use filename only as a weak prior, and log disagreements.

---

## BUG-08 — PDF ingestion produces zero questions

**Severity: high.**

`question_count == 0` for all five PDFs:
`Question Bank/math2.pdf`, `Question Bank/Physics2.pdf`,
`WEEK 2 DAILYS/{C2,M2,P2} diff set.pdf`.

`parse_pdf()` requires a `/health` endpoint on the LocalAI proxy and returns
`{"error": "LocalAI not available"}` if the probe fails. `LocalAPI/server.py`
should be checked for whether it exposes `/health` at all. Even when it works,
it renders each page at 200 dpi and asks a vision model to transcribe Bengali
— which is the least reliable option available.

**Fix:** PDFs here are text-based, not scans. Extract the embedded text layer
first (`pymupdf` `page.get_text("dict")`), detect whether the embedded font is
a Bijoy-family font, and if so decode the same way as the MHTML path. Fall
back to OCR only for genuinely scanned pages. See `04-IMPLEMENTATION-PLAN.md`
Phase 2.

---

## BUG-09 — `analyzer.py` "predictions" are not predictions

**Severity: high (design).**

```python
recency_score = max_set * 2
confidence = min(freq_score + temporal_boost + recency_score, 95)
```

Problems:

1. `max_set` is a **file index**, not a date. A topic scores higher purely for
   appearing in a file named "4" rather than "1".
2. Weights (`*2`, `*10`, cap `15`, cap `95`) are unjustified constants fitted
   to nothing.
3. `confidence` is reported as a percentage but has never been compared to an
   outcome, so it is not a probability of anything.
4. `topic_overlap` computes `min(count, daily_count)` while `daily_count` is
   still being accumulated in an earlier loop — order-dependent and wrong.

**Fix:** replace wholesale per `06-PREDICTION-MODEL-SPEC.md`.

---

## BUG-10 — No ground truth, no evaluation

**Severity: critical (process).**

There is no labelled set, no held-out exam, and no script that scores a
prediction against reality. The 70% target is currently unmeasurable.

**Fix:** `07-EVALUATION-PROTOCOL.md`, built in Phase 0 **before** any other
change.

---

## BUG-11 — Dead debug scripts committed

`debug2.py`, `debug3.py`, `debug4.py`, `check_unknowns.py` are ad-hoc scratch
files in the repo root. Move to `scripts/` or delete.

---

## Summary table

| ID | Area | Severity | Blocks |
|----|------|----------|--------|
| BUG-10 | Eval | Critical | Everything |
| BUG-01 | Parser | Critical | BUG-02 |
| BUG-02 | Parser | Critical | All Chem/Math classification |
| BUG-05 | Decoder | Critical | All text classification |
| BUG-03 | Parser | High | Option text |
| BUG-04 | Parser | High | Option D |
| BUG-07 | Classifier | High | Per-subject metrics |
| BUG-08 | Parser | High | Question bank ingestion |
| BUG-09 | Model | High | Prediction quality |
| BUG-06 | Classifier | High | Post-fix regression |
| BUG-11 | Hygiene | Low | — |
