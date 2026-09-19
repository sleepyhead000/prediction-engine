# 03 — Data Contracts

Implement these as pydantic models in `engine/schemas.py`. Every stage
validates its input on load and its output before writing. A stage that emits
invalid data must fail, not warn.

All files are UTF-8 JSON, `ensure_ascii=false`, 2-space indent.

---

## `01_raw_nodes.json`

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-09-19T10:00:00+06:00",
  "documents": [
    {
      "doc_id": "sha1:3f2a…",              // sha1 of the source file bytes
      "source_path": "sources/dailies/week1/C1 MCQ 1.mhtml",
      "source_url": "https://online.udvash-unmesh.com/Exam/DisplayQuestion?…",
      "captured_at": "2026-09-03T23:15:01+06:00",   // from MHTML Date: header
      "course_id": "2993",
      "routine_id": "158722",
      "exam_id": "127482",
      "unique_set": 1,

      "exam_kind": "daily_mcq",   // daily_mcq|daily_written|weekly_mcq|
                                  // weekly_written|diff_set|question_bank|book
      "week_index": 1,            // 1..N, from folder; null if unknown
      "filename_subject": "Chemistry",   // WEAK PRIOR ONLY. See BUG-07.

      "questions": [
        {
          "q_index": 1,
          "stem_nodes": [
            {"kind": "text", "raw": "cj-eyw½ e¨v‡j‡Ý ",
             "encoding": "bijoy", "cls": "pt-000001…"},
            {"kind": "math", "mathml": "<math …><mn>0</mn></math>"},
            {"kind": "text", "raw": " `vM †_‡K", "encoding": "bijoy",
             "cls": "pt-000001…"}
          ],
          "options": [
            {"letter": "A", "nodes": [ /* same node shape */ ]},
            {"letter": "B", "nodes": [ … ]},
            {"letter": "C", "nodes": [ … ]},
            {"letter": "D", "nodes": [ … ]}
          ],
          "correct_letter": "B",     // null if not present in the source
          "images": [                 // figures/diagrams, if any
            {"cid": "cid:…", "sha1": "…", "stored_at": "data/_images/….png"}
          ]
        }
      ]
    }
  ],
  "ingest_report": {
    "files_seen": 39,
    "files_ok": 39,
    "files_failed": 0,
    "questions_total": 0,
    "assert_failures": []
  }
}
```

**Invariants**
- `exam_kind == "daily_mcq"` ⇒ `len(questions) == 20`
- any MCQ question ⇒ `len(options) == 4`
- `stem_nodes` is never empty
- node order is document order; do not sort

---

## `02_questions.json`

```jsonc
{
  "schema_version": 1,
  "questions": [
    {
      "qid": "sha1:9c1e…",            // sha1(doc_id + q_index) — stable key
      "doc_id": "sha1:3f2a…",
      "source_path": "…",
      "exam_kind": "daily_mcq",
      "week_index": 1,
      "captured_at": "2026-09-03T23:15:01+06:00",
      "filename_subject": "Chemistry",

      "question_text": "পুল-বুঞ্চ ব্যালেন্সে বীমের সর্ববামে ⟦M0⟧ দাগ থেকে …",
      "math_blocks": [
        {"token": "⟦M0⟧", "latex": "0",        "mathml": "<math…>"},
        {"token": "⟦M1⟧", "latex": "44.8\\,L", "mathml": "<math…>"}
      ],
      "options": [
        {"letter": "A", "text": "⟦M2⟧", "math_blocks": [ … ]},
        {"letter": "B", "text": "⟦M3⟧", "math_blocks": [ … ]},
        {"letter": "C", "text": "⟦M4⟧", "math_blocks": [ … ]},
        {"letter": "D", "text": "⟦M5⟧", "math_blocks": [ … ]}
      ],
      "correct_letter": "B",

      "raw_preserved": {
        "stem_nodes": [ /* verbatim copy from stage 1 */ ]
      },

      "decode_quality": {
        "bijoy_chars_in": 412,
        "unmapped_glyphs": [],          // e.g. [["\u00bd", 3]]
        "residual_latin1_high": 0,      // count of chars in U+0080–U+00FF left
        "math_blocks_ok": 6,
        "math_blocks_failed": 0
      }
    }
  ],
  "decode_report": {
    "questions_total": 0,
    "clean_questions": 0,               // unmapped_glyphs == [] and residual == 0
    "clean_rate": 0.0,
    "math_conversion_rate": 0.0,
    "unmapped_glyph_frequency": [["\u00bd", 47], ["\u00dd", 31]]
  }
}
```

`raw_preserved` is mandatory. It is what lets you re-run a decoder fix
without re-scraping the portal (rule 2 in `00-START-HERE.md`).

---

## `03_taxonomy.json`

```jsonc
{
  "schema_version": 1,
  "books": [
    {"book_id": "phy1", "title": "…", "subject": "Physics", "paper": 1,
     "source_path": "sources/books/physics_1st.pdf", "pages": 412}
  ],
  "sections": [
    {"section_id": "phy1.c03.s02", "book_id": "phy1",
     "chapter_no": 3, "chapter_title": "নিউটনীয় বলবিদ্যা",
     "section_no": 2, "section_title": "…",
     "page_start": 88, "page_end": 96,
     "text_chars": 14210,
     "worked_examples": 11, "exercise_problems": 34}
  ],
  "concepts": [
    {
      "concept_id": "phy.mech.lever_rider_balance",
      "subject": "Physics",
      "label_en": "Moment balance on a beam with a movable rider",
      "aliases_bn": ["পুল-বুঞ্চ ব্যালেন্স", "রাইডার", "ভরকেন্দ্র"],
      "section_ids": ["phy1.c03.s02"],
      "book_weight": 0.031,          // share of book pages+exercises
      "parent": "phy.mech.moments",
      "typical_forms": ["numeric_multi_step"]
    }
  ]
}
```

`concept_id` must be a stable dotted slug. Never renumber; if a concept is
merged, keep the old id in an `aliases_of` field so historical labels survive.

---

## `04_labelled.json`

```jsonc
{
  "schema_version": 1,
  "labels": [
    {
      "qid": "sha1:9c1e…",
      "subject": "Physics",           // authoritative, overrides filename
      "concept_id": "phy.mech.lever_rider_balance",
      "concept_candidates": ["phy.mech.moments", "phy.mech.centre_of_mass"],
      "difficulty_1_5": 3,
      "question_form": "numeric_multi_step",
      "confidence": 88,
      "needs_review": false,
      "labeller": "deepseek-chat@2026-09-19",
      "subject_disagrees_with_filename": true
    }
  ],
  "classify_report": {
    "labelled": 0,
    "needs_review": 0,
    "subject_disagreements": 0,
    "cache_hits": 0
  }
}
```

---

## `05_features.json`

One row per `(concept_id, target_week)`.

```jsonc
{
  "schema_version": 1,
  "target_week": 5,
  "rows": [
    {
      "concept_id": "phy.mech.lever_rider_balance",
      "subject": "Physics",
      "features": {
        "book_weight": 0.031,
        "bank_frequency": 0.018,
        "in_syllabus": 1,
        "syllabus_available": 1,
        "daily_signal_w": 0.25,
        "daily_signal_w_minus_1": 0.00,
        "weekly_history": [0, 1, 0, 0],
        "weeks_since_last_weekly": 3,
        "appeared_last_weekly": 0,
        "diffset_signal": 0.0,
        "form_diversity": 2,
        "prereq_covered": 1
      },
      "label": null      // filled in during backtest: 1 if it appeared
    }
  ]
}
```

---

## `06_ranked.json`

```jsonc
{
  "schema_version": 1,
  "target_week": 5,
  "weights_version": "bt_2026-09-19_loo",
  "ranked": [
    {
      "rank": 1,
      "concept_id": "phy.mech.lever_rider_balance",
      "subject": "Physics",
      "score": 4.12,
      "probability": 0.71,
      "expected_count": 1.3,
      "contributions": {
        "in_syllabus": 2.40, "book_weight": 0.62, "bank_frequency": 0.45,
        "daily_signal_w": 0.90, "appeared_last_weekly": -0.25
      },
      "evidence_qids": ["sha1:9c1e…", "sha1:aa02…"]
    }
  ]
}
```

`contributions` is mandatory. Every score must be attributable to named
features, or you cannot debug it. This is the direct fix for BUG-09.

---

## `prediction_wN.json` (final output)

```jsonc
{
  "schema_version": 1,
  "target_week": 5,
  "generated_at": "…",
  "predictions": [
    {
      "pred_id": "w5-p001",
      "rank": 1,
      "concept_id": "phy.mech.lever_rider_balance",
      "subject": "Physics",
      "probability": 0.71,
      "question_bn": "…",
      "math_latex": ["…"],
      "options_bn": ["…", "…", "…", "…"],
      "answer": "B",
      "worked_solution_bn": "…",
      "based_on": {
        "book_sections": ["phy1.c03.s02"],
        "similar_qids": ["sha1:…"]
      }
    }
  ]
}
```

---

## `ground_truth/labels_v1.jsonl`

One JSON object per line, hand-written by a human:

```jsonc
{"qid":"sha1:9c1e…","subject":"Physics",
 "concept_id":"phy.mech.lever_rider_balance",
 "question_text_bn":"পুল-বুঞ্চ ব্যালেন্সে বীমের সর্ববামে '0' দাগ থেকে …",
 "n_options":4,"labelled_by":"human","labelled_at":"2026-09-19"}
```

`question_text_bn` is the human's own transcription of the question as it
appears on screen. It is the reference for scoring the decoder.

---

## `ground_truth/decoder_vectors.tsv`

Tab-separated, two columns, no header. Used by the decoder unit tests.

```
e¨v‡j‡Ý ex‡gi me©ev‡g	ব্যালেন্সে বীমের সর্ববামে
†_‡K †gvU `vMv¼b msL¨v	থেকে মোট দাগাঙ্কন সংখ্যা
```

Minimum 200 lines before Phase 1 can be declared green.
