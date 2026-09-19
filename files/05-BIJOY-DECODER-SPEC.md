# 05 — Bijoy → Unicode Decoder Specification

This is the highest-risk component. Every downstream accuracy number is
capped by it. Treat it as a parser with a formal spec and a test suite, not as
a lookup table.

## Scope

Input: a string in **Bijoy Classic / SutonnyMJ ANSI** encoding, as it appears
in the `.mhtml` text nodes and in Bijoy-font PDF spans.

Output: NFC-normalised Unicode Bengali (U+0980–U+09FF).

## Why the current implementation fails

`bijoy_decoder.py` maps character-by-character with no reordering. Bijoy is a
**visual-order** encoding; Unicode is **logical-order**. Three classes of
glyph move. None are handled. See BUG-05.

---

## Verified rules

These were confirmed by decoding real strings from
`Chemistry/C1 MCQ 1.mhtml` and checking the result reads correctly.

### R1 — Pre-base vowel reorder (`†`, `‡`)

Both `†` (U+2020) and `‡` (U+2021) are the vowel sign **ে** (U+09C7). They
are two width-variants of the same glyph. In Bijoy they are typed **before**
the consonant; in Unicode they follow it.

```
Bijoy:    ‡ g            →  Unicode:  ম ে      (মে)
Bijoy:    † _ ‡ K        →  Unicode:  থ ে ক ে  (থেকে)
```

Worked example:

```
input     †_‡K †gvU
tokens    † _ | ‡ K | † g v U
output    থে   কে    মো   ট        →  থেকে মোট   ✓
```

Note `†g` + `v` composes to **মো**: the ে combines with the following া
(U+09BE) to form ো (U+09CB). Handle this composition explicitly — do not
emit `ে` + `া` as two code points, emit U+09CB.

Same for `†` + consonant + `Š` → ৌ (U+09CC).

**Algorithm:** when you encounter `†` or `‡`, buffer it, consume the
following consonant cluster (including any conjuncts and reph), emit the
cluster, then emit the vowel sign.

### R2 — Reph reorder (`©`)

`©` (U+00A9) is **র্** (র + U+09CD). In Bijoy it is typed **after** the
consonant it rides on; in Unicode it precedes it.

```
input     m e © e v ‡ g
naive     স ব র্ ব া ে ম      ← wrong
correct   স র্ব ব া ম ে        → সর্ববামে   ✓
```

**Algorithm:** on `©`, move it to immediately before the consonant cluster
that precedes it, emitting `র` + `্` + cluster.

### R3 — Ja-phala (`¨`)

`¨` (U+00A8) is **্য** (U+09CD + U+09AF). No reorder — it follows its
consonant — but the current code passes it through raw.

```
input     e ¨ v ‡ j ‡ Ý
output    ব ্য া   লে    ন্সে   →  ব্যালেন্সে   ✓
```

### R4 — Conjunct glyphs

Single Bijoy code points that expand to multi-character Unicode clusters.
Confirmed from the sample:

| Bijoy | Unicode | Bengali |
|---|---|---|
| `Ý` (U+00DD) | U+09A8 U+09CD U+09B8 | ন্স |
| `¼` (U+00BC) | U+0999 U+09CD U+0995 | ঙ্ক |
| `©` (U+00A9) | U+09B0 U+09CD | র্ (see R2) |
| `¨` (U+00A8) | U+09CD U+09AF | ্য |

`bijoy_decoder.py` already has a `_CONJUNCTS` dict with many of these. Keep
it, extend it, and make it authoritative — but drive the extension from
measured data (§ Unmapped glyph workflow), not from guessing.

### R5 — Ra-phala, ref-over-conjunct, and vowel-over-conjunct

`r` is hasanta (U+09CD). A sequence `<cons> r <cons>` forms a conjunct. This
must be applied **after** R1/R2 reordering, because the "consonant cluster"
those rules move around includes conjuncts.

---

## Unverified — must be validated before use

I could **not** confirm these from the sample data. Do not assume them.

- `½` (U+00BD) — appears in `eyw½` ("পুল-বুঞ্চ ব্যালেন্স"?). Candidate: ঞ্চ.
  **Unverified.** Add to the test vectors and confirm against the rendered
  page before mapping it.
- `¤ ª « ¬ ­ ® ¯ °–¿` range — these are the conjunct block. The existing
  `_CONJUNCTS` covers some. The rest must be derived empirically.
- Whether Udvash's pages ever use **Bijoy Unicode** (as opposed to Classic)
  for some spans. Check: if a text node already contains U+0980–U+09FF
  characters, it is already Unicode — pass it through, do not decode.

---

## Required algorithm shape

Do **not** write this as `for ch in s: out += MAP[ch]`. Write a tokeniser +
reorderer:

```
def decode(s: str) -> DecodeResult:
    if is_already_unicode_bengali(s):
        return DecodeResult(text=nfc(s), unmapped=[])

    tokens = tokenise(s)          # longest-match over CONJUNCTS, then TWO, then SINGLE
    clusters = group_clusters(tokens)   # consonant + hasanta chains + marks
    reordered = apply_reorder(clusters) # R1 pre-base vowels, R2 reph
    text = emit(reordered)              # compose ে+া → ো etc.
    return DecodeResult(text=nfc(text), unmapped=collect_unmapped(tokens))
```

`DecodeResult` must carry `unmapped: list[tuple[str, int]]`. Silent failure
is what produced the 200-entry `_GARBLED_MAP`.

## Longest-match tokenising

Sort the combined glyph table by key length descending and match greedily.
`K¡` (ক্ষ) must win over `K` (ক). The existing code sorts `_GARBLED_MAP` this
way already — apply the same discipline to the real glyph table.

---

## Test suite

`tests/test_bijoy.py` must contain:

1. **Vector test** — every line of `ground_truth/decoder_vectors.tsv` must
   decode exactly. Target ≥ 0.97 pass rate at Gate 1. Failures print a
   character-level diff.

2. **Property: no residual high Latin-1.** For any input, the output must
   contain no characters in U+0080–U+00FF and no U+2020/U+2021. If it does,
   a glyph went unmapped.

3. **Property: idempotence on Unicode.** `decode(decode(x)) == decode(x)`.

4. **Property: no orphan marks.** Output must not begin with a combining
   mark (U+09BE–U+09CC, U+09CD) — that indicates a failed reorder.

5. **Round-trip spot checks** — the four worked examples above, as explicit
   asserts.

---

## Unmapped glyph workflow

This is how you get from 80% to 97% without hand-patching words.

1. Run the decoder over the whole corpus.
2. `decode_report.unmapped_glyph_frequency` gives every unmapped code point
   with a count, sorted descending.
3. Take the top 10. For each, `scripts/show_glyph_context.py <char>` prints 5
   real sentences containing it, with surrounding decoded text.
4. A human reads the sentences, identifies the Bengali, adds the mapping and
   a test vector.
5. Re-run. Repeat.

Ten iterations of this will close almost all of the gap. Each iteration
produces a mapping that is *verified against context*, not guessed.

**Do not** add entries to a "corrupted string → correct string" map. If you
find yourself wanting to, the glyph table is incomplete — fix that instead.

---

## Fallback: LLM-assisted repair (use sparingly)

For the residual few percent, a DeepSeek call can repair a sentence given
the partially-decoded text plus the raw Bijoy. Rules if you do this:

- Only for questions where `unmapped_glyphs` is non-empty.
- The output must be flagged `repaired_by_llm: true` and excluded from the
  decoder's accuracy metric (otherwise you are measuring the LLM, not the
  decoder).
- Cap at 5% of the corpus. If more than 5% needs repair, Gate 1 has not
  actually been met — go back to the glyph workflow.

---

## PDF-specific note

For PDFs, the same decoder applies, but you must first determine whether the
span uses a Bijoy font. Use `pymupdf`:

```python
for block in page.get_text("dict")["blocks"]:
    for line in block.get("lines", []):
        for span in line["spans"]:
            font = span["font"]              # e.g. "SutonnyMJ", "NikoshBAN"
            is_bijoy = bool(re.search(r"sutonny|bijoy|boishakhi", font, re.I))
```

If the PDF has no text layer at all, it is a scan — route to OCR
(`tesseract` with `-l ben`, or a vision model) and mark
`extraction_method: "ocr"` so those questions can be excluded from strict
metrics.
