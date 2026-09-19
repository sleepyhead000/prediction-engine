# 08 — LLM Prompt Templates

Model: DeepSeek (or any OpenAI-compatible endpoint) via `engine/llm.py`.

**Global rules**

- `temperature = 0` everywhere except T3 (generation).
- Every prompt demands raw JSON. No markdown fences, no preamble. Parse with
  a tolerant extractor anyway, but log every time the tolerant path fires —
  a rising rate means the prompt is degrading.
- Cache key: `sha256(model + system + user + json.dumps(params, sort_keys=True))`.
- All prompts must state that input is Bengali with LaTeX in `⟦Mn⟧` tokens,
  and that tokens must be preserved verbatim.
- On a parse failure, retry once with `"Your previous reply was not valid
  JSON. Reply with JSON only."` appended. Then give up and mark
  `needs_review`.

---

## T1 — Concept extraction from a textbook section

**System**

```
You are a curriculum analyst for Bangladeshi HSC-level science textbooks.
You read a section of a textbook and list the distinct testable concepts it
contains. Output JSON only.
```

**User**

```
SUBJECT: {subject}
BOOK: {book_title}
CHAPTER {chapter_no}: {chapter_title}
SECTION {section_no}: {section_title}
PAGES: {page_start}-{page_end}
WORKED EXAMPLES IN SECTION: {n_examples}
EXERCISE PROBLEMS IN SECTION: {n_exercises}

SECTION TEXT:
---
{section_text}
---

List every distinct concept an exam setter could write a question about.

Rules:
- A concept is a specific testable idea, not a chapter heading.
  GOOD: "Moment balance on a beam with a movable rider"
  BAD:  "Newtonian mechanics"
- Between 3 and 12 concepts. If the section supports fewer, give fewer.
- label_en: English, under 12 words.
- aliases_bn: 2-5 Bengali terms as they appear in the text. Copy them
  exactly from the section; do not translate or invent.
- typical_forms: from {numeric_single_step, numeric_multi_step,
  conceptual_recall, graph_interpretation, statement_assertion, matching,
  derivation}
- If the section is front-matter, an index, or contains no testable
  content, return {"concepts": []}.

Output JSON:
{"concepts":[{"label_en":"...","aliases_bn":["..."],
  "typical_forms":["..."],"difficulty_1_5":3,
  "grounding_quote_bn":"..."}]}
```

`grounding_quote_bn` is a short phrase copied from the section. It exists to
catch hallucinated concepts — if the quote is not present in the source text,
drop the concept and log it.

---

## T2 — Question classification (retrieve-then-select)

**System**

```
You classify Bangladeshi HSC exam questions into a fixed concept list.
You must choose from the candidates given. Output JSON only.
```

**User**

```
The question is in Bengali. Mathematical expressions have been replaced by
tokens like ⟦M0⟧ and are listed separately in LaTeX. Use both.

QUESTION:
{question_text}

MATH:
{for each: ⟦M0⟧ = <latex>}

OPTIONS:
A) {option_a}   B) {option_b}   C) {option_c}   D) {option_d}

CANDIDATE CONCEPTS (choose exactly one):
{for each of top-8:}
  [{concept_id}] {subject} — {label_en}
      Bengali terms: {aliases_bn}

TASK:
1. Determine the subject: Physics, Chemistry, or Math.
   Judge by the content of the question, NOT by any filename or
   surrounding context. A balance-and-lever problem is Physics even if it
   appears in a Chemistry paper.
2. Pick the single best concept_id from the candidates.
3. If none of the candidates fit, set concept_id to null and explain in
   "reason". Do not invent a concept_id.
4. Classify question_form and difficulty.

Output JSON:
{"subject":"Physics","concept_id":"phy.mech.lever_rider_balance",
 "question_form":"numeric_multi_step","difficulty_1_5":3,
 "confidence":88,"reason":"one short sentence"}
```

Point 1 is the direct fix for BUG-07 — never give the model the filename.

---

## T3 — Question generation

**Temperature 0.7.** The only stage above 0.

**System**

```
You write exam questions in the exact style of Udvash-Unmesh weekly exams
(Bangladesh, HSC admission preparation). You write in Bengali. Output JSON
only.
```

**User**

```
TARGET CONCEPT: {label_en}
SUBJECT: {subject}
BENGALI TERMS USED IN THE TEXTBOOK: {aliases_bn}

TEXTBOOK SOURCE (the question must be answerable from this):
---
{section_text}
---

STYLE EXEMPLARS — real Udvash questions on related concepts. Match their
register, sentence structure, numeric magnitudes, and how the wrong options
are constructed. Do NOT copy their content.
---
{3 real questions with their options}
---

OBSERVED HOUSE STYLE:
- typical stem length: {n} Bengali words
- numeric values usually in range: {range}
- distractors are usually: {e.g. "sign errors, unit-conversion errors, and
  the value obtained by omitting one force"}

Write {n} NEW multiple-choice questions on the target concept.

Rules:
- Bengali stem. Mathematics in LaTeX inside \( \).
- Exactly 4 options. Exactly one correct.
- Distractors must be the result of a plausible specific mistake, not
  random numbers. State the mistake for each in "distractor_logic".
- Include a worked solution in Bengali.
- The question must be solvable from the textbook source alone.
- Do not reproduce any exemplar question with only the numbers changed.

Output JSON:
{"questions":[{"question_bn":"...","options_bn":["...","...","...","..."],
 "answer":"B","worked_solution_bn":"...",
 "distractor_logic":{"A":"...","C":"...","D":"..."},
 "question_form":"numeric_multi_step"}]}
```

Extract the "OBSERVED HOUSE STYLE" values from your parsed weeklies
programmatically. Do not write them by hand — they should update as you
ingest more exams.

---

## T4 — Independent solvability check

Run in a **fresh context**. Do not show the model the intended answer — that
defeats the purpose.

**System**

```
You are a careful HSC-level {subject} solver. Solve the question. Output
JSON only.
```

**User**

```
{question_bn}

A) {a}  B) {b}  C) {c}  D) {d}

Solve step by step, then give your answer.
If the question is ambiguous, unanswerable, or has more than one correct
option, say so.

Output JSON:
{"answer":"B","reasoning_bn":"...","solvable":true,"issues":[]}
```

Discard any generated question where `solvable == false`, or where the
solver's answer differs from the intended one. Log the discard rate — if it
exceeds 30%, T3 needs work, not the filter.

---

## T5 — Decoder repair (fallback, capped at 5% of corpus)

Only for questions with unmapped glyphs. See `05-BIJOY-DECODER-SPEC.md`.

**User**

```
The following Bengali text was decoded from the legacy Bijoy/SutonnyMJ
encoding and some glyphs failed to map. They appear as Latin-1 symbols
(e.g. ½ ¼ Ý ©) embedded in otherwise readable Bengali.

PARTIALLY DECODED:
{partial}

ORIGINAL BIJOY BYTES:
{raw}

Reconstruct the intended Bengali. Change ONLY the corrupted regions; leave
correctly-decoded Bengali untouched. For each fix, report which Latin-1
character you replaced and with what.

Output JSON:
{"repaired_bn":"...","fixes":[{"glyph":"½","replacement":"ঞ্চ",
 "context":"..."}]}
```

The `fixes` array feeds back into the glyph-table workflow. If the model
consistently maps `½ → ঞ্চ` across many contexts, that is strong evidence to
add it to the static table — after a human confirms one instance against the
rendered page.

---

## Cost control

Per full corpus run, at roughly 300 questions and 1500 book sections:

| Prompt | Calls | Notes |
|---|---|---|
| T1 | ~1500 | once per book section; cached forever |
| T2 | ~300 | cached per question hash |
| T3 | ~40 | per prediction run |
| T4 | ~120 | 3 per generated question |
| T5 | ≤15 | capped |

T1 dominates and runs once. After the first run, an end-to-end re-run should
be almost entirely cache hits. If it isn't, your cache key is wrong —
probably because it includes a timestamp or a dict with non-deterministic
ordering.
