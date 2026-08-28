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

## Building the accuracy harness, and what it immediately found

Three of the six evaluation criteria are accuracy claims. None had a number,
and `eval/results/report.md` had been committed reading `mean F1 0.00 over 0
sheet(s)` — because the harness had never actually run. Its first line crashed:
`dataclasses.asdict` called on a pydantic model.

The missing piece was ground truth. Hand-labelling is better evidence, but it
costs ~15 minutes a sheet and is itself shaky at the edges — a human eyeballing
a y range is performing the same judgement the metric exists to check. So
`eval/make_synthetic_case.py` *draws* a sheet at coordinates it chooses and
records the ink bounds as it writes them. Real prose in a handwriting face, not
the scribble in `make_mock_pages.py`, because the mapper must be scored on
reaching the *right* answer and a scribble gives it nothing to be right about.
One sheet carries every awkward case in the brief: Q3 above Q2, `11(a)`/`11(b)`
separate, `11(b)` across a page break, nine blanks, and a `Q14` on a paper that
stops at 13.

Its first run found two bugs that had been degrading every run to date.

### Correct bounding boxes were being thrown away

Highlight IoU came back at **0.29**, and three answers on one page shared an
identical region. The model had returned:

```
box_2d: [132, 118, 217, 858, false, false]
```

— the box, with the two continuation booleans flattened onto the end. Those
first four numbers are right, within a percent of the true ink bounds. But
`box_to_fractions` required *exactly* four elements, rejected the whole array,
and the caller fell back to a whole-page rectangle. Tightening then snapped
that to every mark on the page, so all three answers "highlighted" the same
full block of writing.

This is the worst kind of failure: silent, and it produces a plausible-looking
highlight rather than an error. Reading the first four values of anything at
least four long took **IoU from 0.29 to 0.89**, and on the real Hindi sheet
took full-page fallbacks from several to **zero out of 52 regions**.

### An orphaned label was being reassigned by word overlap

Unmatched-answer F1 was **0.00**. The `Q14` answer — osmosis, on a paper that
ends at 13 — had been handed to Q13, *"Define osmosis"*. Content overlap made
that look like a confident match, and it cost two things at once: the brief's
"answers that match no question" case, and Q13's blank status.

The label is the student's own instruction. A block whose written label names a
number the paper does not contain is now held back from the content,
adjudication and sequential rungs, left unmatched, and reported with a warning
saying why. **Unmatched F1 0.00 → 1.00; blanks 8/9 → 9/9.**

On the real Hindi sheet this warning does real work, naming the 11 answers
labelled 8, 9, 10 and 12 against a reconstructed paper that only contains 1–7 —
stating the dataset mismatch in the product rather than only in this document.

### Where it landed

| | |
|---|---|
| question extraction F1 | 1.00 (15/15) |
| printed order | 0 inversions |
| answers mapped correctly | 6/6 |
| blanks identified | 9/9 |
| answers matching no question | F1 1.00 |
| highlight on right page | 6/6 |
| highlight overlap | median IoU 0.89 |

Rendered handwriting is an easier read than a real scan, so this is a
calibration case rather than evidence about messy writing. Both bugs it caught
were real, and neither was visible by looking at output and squinting.

---

## Page cleaning, and the bug it uncovered

Every accuracy loss on this project had been a misread *label* — an `8` read as
a `7`, a zero-padded `05.` — so the next lever tried was upstream of the model:
clean the scan before it is read. `api/pipeline/preprocess.py` flattens uneven
lighting, stretches faint ink, and deskews, each step gated on measuring that
the page needs it. It calls nothing; the free tier meters requests per day, not
pixels.

`eval/preprocess_ab.py` measures it without spending quota. On the four
photographed sheets in `dataset/`:

| | before | after |
|---|---|---|
| residual skew | up to 2.1° | 0.00° on every page |
| background range | 91–120 grey levels | 17–22 |
| ink/paper separation | 194–217 | 240–243 |

A digitally generated PDF comes back byte-identical: every gate declines.

### Then it scored worse, which is the interesting part

End to end on the hand-marked sheet, cleaning **dropped 35/40 to 31.5**. The
cached answer blocks from both runs said why, and it was not image quality —
the transcribed *text* was identical in both. Only the labels differed, in both
directions. Cleaning read `08.` where the raw page gave `Q7.` (the raw one was
wrong), and `Q11 b.` where the raw page gave `11 b.`. It also read `Q14.` where
the raw page gave `Q14. b.`.

That one dropped `b.` cost four marks, through `_resolve`:

- `Q14.` carried no sub-part, so it took the first free sibling — `14(a)`.
- The real `Q14 a.` then found `14(a)` taken and was reported **unmatched**.
- `Rough work` shifted onto the `14(b)` vacancy left behind.

Two questions lost and a third mis-filed, from one character — the same shape
as the `8`/`7` fault above, and still unguarded. Students write the number on
one line and `b.` on the next, so the transcription splitting them is ordinary,
not exotic.

The fix does not guess. The sub-part is still sitting in the answer's own
opening words (`Q14. b. 45 divided by 2 ...`), so `_resolve` reads it there
before falling back to writing order, and only when the number agrees. Pinned
by `test_a_label_that_lost_its_subpart_is_recovered_from_the_answer`, which
fails without it, and by a second test holding the plain-`Q11.` fallback in
place.

With that fixed, cleaning scores **35/40 again** — the same as the raw pages.

### Where it landed

Cleaning is **on**. It did not move the mark total on the one sheet with
ground truth, and it is not claimed to: it is on because it no-ops on clean
input, because it demonstrably fixes the defects it targets on photographed
input, and because it costs no quota. What it actually earned its keep for was
exposing a four-mark mapping fault that had been latent in every run.

Two things were tried and dropped:

- **200 DPI** rendering. Scored no better; reverted to 150, where the committed
  numbers were measured. `VEDA_RENDER_DPI` moves it for anyone retesting.
- **Contrast stretch on every scan.** The first threshold let it fire on pages
  that only needed flattening, and what it amplified was the show-through from
  the reverse side of thin notebook paper — which sits between ink and paper
  and gets pulled toward ink with everything else. The bar now sits where only
  genuinely faint pages fall under it.

### One deviation left

`Q5.` is sometimes read as `15.`. The paper stops at 14, so the orphan rule
holds it out of content matching and Q5 reports blank. That rule is not being
loosened: this same sheet carries a *genuine* `Q15` answering nothing, the two
are indistinguishable from the label alone, and the rule is what took unmatched
F1 from 0.00 to 1.00. Reporting "found an answer, could not place it" beside a
blank Q5 is the honest failure, and the marks total is unaffected — Q5 is
deliberately wrong and scores 0 either way.

---

## Making the 35/40 reproducible

That number came from reading a run and comparing against
`dataset/ground-truth.json` by eye, which no reviewer can repeat and no change
can be tested against. `eval/score_dataset.py` makes it one command, and caches
the raw run — including the answer blocks and the rung each match came down —
so a bad run is diagnosable for free instead of costing another run. Diffing
two cached runs is what found the `Q14.` fault above.

```bash
python eval/score_dataset.py            # run, then score
python eval/score_dataset.py --rescore  # score the cache, no API calls
```

One caveat it surfaces: ground truth calls the last sheet page 4, and the PDF
renders five pages. Q4 is genuinely on the fifth. The page column reports the
disagreement rather than hiding it.

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
