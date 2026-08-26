# Engineering log

A record of how the pipeline went from never producing output to finishing a
real answer sheet in 258 seconds, and why each decision was made the way it
was. Every number here was measured on this machine against the bundled
dataset; nothing is estimated.

---

## The symptom

The UI sat on **"Extracting…"** indefinitely. No job had ever produced a
result, on any subject.

Both servers were running and healthy, so the failure was inside the pipeline
rather than in wiring. `/api/health` reported:

```json
{"ok":true,"provider":"ollama","model":"gemini-3.6-flash","ollama_model":"gemma3:12b"}
```

Four independent faults were found. Any one of them alone was enough to stall
or ruin a run, which is why fixing them one at a time kept producing a run that
completed but was still wrong.

---

## Fault 1 — the provider was pointed at a model this machine cannot run

`AI_PROVIDER` was set to `ollama`, with `gemma3:12b`.

Ollama *was* running and the model *was* pulled, so this looked fine. It is
not. Two measurements:

| request | result |
|---|---|
| 17-token text prompt, 2-token reply | **51s** (30s of it just evaluating 17 prompt tokens) |
| small crop of one page, 24-token reply | **394s** |

`/api/ps` explains it: `"size_vram": 0`. There is no NVIDIA GPU on this
machine, so all 8GB of the quantised model runs on CPU within 16GB of RAM.

Vision itself works — gemma3:12b correctly described the crop as *"a page from
a Hindi exam paper with handwritten text and a question about the country's
youth"*. This is a throughput problem, not a quality one. But extrapolating
394s for 294 prompt tokens and 24 output tokens to a full page plus a few
hundred tokens of JSON gives roughly twenty minutes per page, and about six
hours for an 18-page sheet.

`gemma3:4b` was pulled and considered. At roughly 3× faster it is still hours
per sheet, so local inference was abandoned on this hardware rather than tuned.

**Decision:** switch to Gemini. Ollama support is kept and documented, because
it is the right answer on a GPU box or where scans cannot leave the machine —
but the README now states the hardware requirement instead of recommending it
blindly.

---

## Fault 2 — thinking was never actually disabled

`gemini.py` set a thinking budget like this:

```python
if thinking_budget is not None:
    try:
        config["thinking_config"] = gt.ThinkingConfig(thinking_budget=thinking_budget)
    except Exception:
        pass
```

The pinned SDK was `google-genai==0.8.0`, released before `thinking_budget`
existed:

```
ThinkingConfig fields: ['include_thoughts']
```

So the constructor raised `ValidationError` on **every single call**, the bare
`except` swallowed it, and every request ran with thinking fully enabled. The
comment above it claimed thinking was off for extraction. It never had been.

This is the single largest latency item in the project:

| model | thinking | latency on one A4 page |
|---|---|---|
| `gemini-3.1-flash-lite` | budget = 0 | **3.0s** |
| `gemini-3.1-flash-lite` | default (on) | **175.6s** |

**Fixes:** unpinned the SDK (`google-genai>=2.20.0`, which exposes
`thinking_budget` and `thinking_level`), and replaced the silent `except: pass`
with explicit handling — a model that genuinely rejects the parameter is
recorded in a `_no_thinking` set and retried once without it, so a real
incompatibility is handled deliberately instead of being hidden.

---

## Fault 3 — the free tier cannot serve one sheet from one model

The first successful call after the SDK upgrade returned `429`:

```
Quota exceeded for metric: generate_content_free_tier_requests,
limit: 20, model: gemini-3.6-flash
quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
```

The limit is **20 requests per day, per model**. Extraction costs one request
per page, so an 18-page answer sheet is ~19 requests — a single run consumes
almost an entire model's daily allowance, and the second run of the day fails.

Two things were checked before designing around this:

- **The API key is valid.** It had been reported as malformed. It is not — it
  lists models and completes requests correctly.
- **Each model name has its own quota bucket.** Confirmed by calling nine
  models in sequence after `gemini-3.6-flash` was exhausted; the others
  answered normally.

**Decision:** rotate across models rather than back off. A `RESOURCE_EXHAUSTED`
or `UNAVAILABLE` response advances to the next model immediately, because
waiting cannot return a daily quota. Four models give roughly 80 requests a
day. This fired for real during testing and recovered without intervention:

```
WARNING pipeline.gemini: gemini-3.1-flash-lite is exhausted or unavailable — trying the next model
INFO    pipeline.gemini: gemini-flash-lite-latest rejects thinking_budget — retrying without it
```

### Choosing which models, and in which order

Latency across candidate models is not a rounding difference — it spans two
orders of magnitude on the identical request:

| model | latency | questions found | note |
|---|---|---|---|
| `gemini-3.1-flash-lite` (budget 0) | **2.2s** | 7 | default |
| `gemini-3.5-flash-lite` | **2.5s** | 11 | first fallback |
| `gemini-flash-lite-latest` | **171.4s** | 11 | excluded |
| `gemini-3.6-flash` | ~190s | — | excluded |

`gemini-flash-lite-latest` is the trap. The name suggests the fast lite model;
it resolves to a thinking model **and** rejects `thinking_budget`, so its
thinking cannot be switched off at all. It was originally second in the
rotation, and it was responsible for question extraction taking **176 seconds
for a single page** while the 18-page answer sheet took only 64 seconds.
Removing it cut end-to-end runtime from 430s to 258s.

---

## Fault 4 — mapping could not match, for three stacked reasons

With the pipeline finishing, output was still poor: 4 of 11 questions matched,
38 answers unmatched.

### 4a. The text layer destroys structure on Indic scripts

Questions were read from the PDF's text layer, on the reasoning that a text
layer has no OCR error. That is true of *wording* and false of *structure*.

Every question paper in the dataset has a real text layer (1,280–3,038
characters; the answer sheets have 14–28, i.e. none). But on the Hindi Core
paper the extractor drops every inter-word space and cannot represent the
sub-part markers:

```
िदएगएगद्यांश          ← should be  िदए गए गद्यांश
(￿) (￿￿) (￿￿￿)        ← should be  (i) (ii) (iii)
```

Result: eleven questions extracted, all with `number: null`, `part: null`,
`marks: null`. Sub-part markers are precisely what answers are matched on, so
losing them removes the top rung of the mapping ladder entirely.

**Fix:** send each page as an image *and* its text layer in one call, with the
model instructed to read numbering, sub-parts and marks off the image and use
the text only to confirm wording. Question papers are 1–3 pages, so this costs
1–3 extra vision calls. Questions 1–7 then came back correctly numbered with
`(i)/(ii)/(iii)` intact, and the Hindi text properly spaced.

### 4b. Bare sub-part labels matched nothing

A student writes `4. (i)` once and then just `(ii)`, `(iii)` underneath — so
most of a booklet's labels carry no question number. The label regex requires
one, so `(ii)` parsed to `(None, None)` and could never match.

**Fix:** `_inherit_numbers()` carries the last full question number forward
onto bare sub-parts, before continuation-merging while blocks are still in
reading order. Over the 40 labels on the Hindi sample this resolves 39; the one
left is the page header `Hindi Core (302)`, which is correctly *not* a label.
Inherited labels are flagged, since they are weaker evidence than a number the
student actually wrote.

### 4c. The two sides of the comparison were punctuated differently

This one hid behind 4b. After inheritance the labels looked right in the
output — `1 (ii)`, `1 (iii)` — and still did not match.

Questions stored the sub-part as the paper prints it, `"(i)"`. Answers parsed
to bare `"i"`. So the join key compared:

```
"1|(i)"   vs   "1|i"
```

The same bug silently broke ordering: `sort_key` looks the part up in a roman
numeral table, and `"(i)"` is not in it, so every bracketed sub-part sorted to
the bottom.

**Fix:** a single `clean_part()` helper strips non-alphanumerics, and both
`key()` and `sort_key()` route through it, so no future caller can reintroduce
the mismatch by punctuating one side differently.

---

## Results

Each row is a full run of the same 18-page Hindi Core sheet through the API.

| after fixing | runtime | questions matched | unmatched | marks |
|---|---|---|---|---|
| *(baseline)* | never finished | — | — | — |
| provider + SDK + rotation | 280s | 4 / 11 | 38 | 5.0 |
| question extraction (4a) | 470s | 2 / 11 | 40 | 3.0 |
| label inheritance (4b) | 450s | 2 / 11 | 40 | 3.0 |
| part normalisation (4c) | 430s | **8 / 11** | 33 | 9.0 |
| rotation reorder | **258s** | **8 / 11** | 34 | 9.0 |

All 8 matched answers carry a highlight region. The dip to 2/11 in the middle
rows is real and expected: recovering correct sub-part numbering (4a) meant
questions stopped matching by accident and started needing 4b and 4c to match
properly.

Runs are not bit-identical — 33 vs 34 unmatched across two runs of identical
code is model non-determinism at `temperature=0`.

Stage breakdown of the 258s run: rendering 15s, question extraction ~3s,
answer extraction **64s for 18 pages** (~3.5s/page), mapping under a second,
grading ~180s. Grading is now the dominant cost and the obvious next target.

The 12 existing unit tests pass throughout.

---

## Why 34 answers remain unmatched — a dataset finding

This is not mapping error, and it caps any accuracy number taken from this
dataset.

Every PDF in `datasets/` declares on its first page that it is a
**"Reconstructed Question Paper — reconstructed from the submitted answer
booklet."** Only the booklets were available; a model inferred the questions
from the visible working.

On the Hindi Core sample that produces a genuine mismatch:

- the booklet answers questions **1–12**; the reconstructed paper contains **1–7**
- the content does not correspond — answer `1.(i)` is an MCQ option
  (`(D) जब समझ से सीखा और अभ्यास किया जाए`), while question `1(i)` asks the
  student to explain an author's meaning

No matcher can join those. Most of the unmatched answers are the system
correctly reporting that an answer has no corresponding question.

This also makes the dataset unsuitable for scoring mapping accuracy in the
write-up: the questions were derived *from* the answers, so testing
content-similarity matching against them is partly circular. It remains
excellent for testing **transcription** on real handwriting, across 389 pages
and 14 subjects.

**To quote a defensible mapping accuracy number**, one subject is needed where
the paper genuinely corresponds to the booklet. CBSE publishes *Topper's Answer
Sheets* for some subjects — real handwriting, the real official paper, and the
examiner's own marks on the script, which would also allow grading to be
validated against real marks.

---

## Things measured and rejected

Recorded so they are not re-attempted.

- **Skipping blank pages** to save quota. Answer booklets were assumed to
  contain many unused pages. Measured across all 389 pages by ink coverage:
  **only 8 are blank (2%)**. These booklets are densely written and there is
  nothing to skip.
- **`gemma3:4b` instead of `gemma3:12b`.** ~3× faster, still hours per sheet on
  a CPU-only machine. Pulled and left in place; safe to `ollama rm`.
- **Batching several pages per request** to cut quota use. Not implemented. The
  one-page-per-request rule exists because page indices and coordinates drift
  when pages share a request, and correct bounding boxes are a graded
  requirement — this trades the wrong thing away.

---

## Changes to the environment

Made while debugging, and worth knowing about:

- `api/.env`: `AI_PROVIDER` `ollama` → `gemini`; `GEMINI_MODEL` →
  `gemini-3.1-flash-lite`; `GEMINI_MODELS` added for the rotation.
- `google-genai` upgraded globally, 0.8.0 → 2.20.0. `pip` warns that an
  unrelated package (`litellm`) pins an older `pydantic`.
- `gemma3:4b` pulled into Ollama (~3GB).
- The backend now runs under `--reload`. It previously did not, which meant
  edits to `api/pipeline/` had no effect until a manual restart — worth
  flagging, because it can make a real fix look like it did nothing.
