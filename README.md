# AI Assessment Extraction & Answer Mapping

Upload a question paper and one handwritten answer sheet. The app extracts every
question in printed order, reads the student's answers, works out which answer
belongs to which question, highlights the exact region of the answer sheet, and
marks the work.

- **Live app:** _add the Vercel URL here_
- **API:** _add the Render URL here_ · health check at `/api/health`

| | |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind v4 |
| Backend | FastAPI (Python 3.12) |
| AI model | Google **Gemini 3.1 Flash Lite** (free tier), with a fallback rotation |
| Storage | In memory, per job — no database |

---

## How it works

```
upload ─► render pages ─► extract questions ─┐
                                             ├─► map ─► tighten ─► grade ─► UI
          render pages ─► extract answers ───┘
```

Each stage is a module under `api/pipeline/`, and each one is where a specific
requirement from the brief gets met.

### 1. Rendering (`render.py`)

Both uploads can be a PDF or images; everything downstream works on rendered
raster pages at 150 DPI, which is legible for handwriting and small enough to
stay inside the free tier's request budget. PDFs also have their text layer
pulled out, because the next stage uses it when it exists.

### 2. Question extraction (`questions.py`)

A printed question paper usually arrives as a PDF with a real text layer, and
that layer is the best available source for the *wording* of a question — it
carries no OCR error at all. It is a poor source for the paper's *structure*.
PDF text extraction routinely drops the spaces between words and renders
sub-part markers like `(i)` as a replacement glyph, and on the Hindi Core
sample that is exactly what happens: `िदए गए गद्यांश` comes back as
`िदएगएगद्यांश`, and every `(i)`/`(ii)`/`(iii)` arrives as `(￿)`.

Losing those markers is expensive, because they are the thing answers are
matched on. Reading that paper from its text layer produced eleven questions
with `number: null` and `part: null`, and two of eleven answers matched.

So each page goes to the model as an image *and* as its text layer, with the
model told to read numbering, sub-parts and marks off the image and to use the
text only to confirm wording. Papers run to a page or three, so the extra
vision calls are cheap. The same sample then produced questions 1–7 with their
sub-parts intact.

Sub-parts are split at this stage: `11 (a)` and `11 (b)` become two entries,
each carrying `number: "11"` and `part: "a" | "b"` as separate fields. Keeping
them separate rather than as one `"11(b)"` string is what lets the UI render
the number badge and the sub-part pill the way the design specifies, and what
lets the mapper match them independently.

Printed numbering is preserved verbatim — nothing is renumbered. Order comes
from the model, with one guard: if the returned order disagrees badly with the
printed numbering (which happens on two-column layouts, where the text layer
streams out of visual order), it is re-sorted by number and a warning is
surfaced.

### 3. Answer extraction (`answers.py`)

One request per page, asking for *blocks* rather than lines — a block is the
whole run of writing that answers one question, diagram included. For each
block the model returns the student's own label verbatim (`"Q2."`, `"11 b)"`),
a transcription, a bounding box, and two continuation flags.

Boxes are requested as `box_2d` in `[ymin, xmin, ymax, xmax]` normalised to
0–1000. That is the convention Gemini is trained on; asking for a different
ordering or range measurably degrades localisation.

### 4. Box tightening (`tighten.py`) — the accuracy lever

The model's box is treated as a proposal, not an answer. Vision models put a
box roughly in the right place and then miss the edges, usually by including a
band of blank ruled paper below the last line. A teacher sees that immediately,
and "correct highlighting of answers" is on the evaluation list.

So every proposal is snapped onto the actual ink: grow it slightly, threshold
against the local paper colour, discard the printed ruling and the margin line,
and crop to what is left. No OpenCV — Pillow and NumPy keep the deploy image
inside a free tier, and it is a couple of array reductions.

The ruling detection measures the *longest unbroken run* in each row and
column rather than the total count of dark pixels: a printed rule is a near
unbroken line across the page, while a dense line of handwriting breaks up into
words. Both passes read the original mask, because clearing the ruled rows
first would chop the vertical margin line into short segments and the column
pass would then never recognise it.

`spike/box_accuracy_spike.py` renders the raw proposal in red and the tightened
box in green over each page, so this is checkable on a real sheet in about ten
minutes.

### 5. Mapping (`mapping.py`)

A single semantic-similarity pass handles the brief's three awkward cases
badly. This is a ladder instead, in descending order of how much the evidence
is worth:

1. **The student wrote a label.** `Q11(b)` is not a hint, it is an instruction,
   and it is order-independent by construction — which is most of what
   "handle questions answered out of order" actually needs.
2. **The label is embedded in the first words** of the transcription.
3. **Content similarity** — IDF-weighted token overlap between the answer and
   each remaining question, greedily assigned above a floor.
4. **Model adjudication** for whatever is still floating, capped at 12 blocks
   so a messy sheet stays cheap. The prompt says explicitly that returning
   `null` is correct.
5. **Sequential fallback**, only when the sheet carries no labels at all.

Anything unassigned at the end is reported as an unmatched answer; any question
with nothing assigned is reported as unanswered. Neither is treated as an
error — both are outcomes the teacher needs to see.

Answers spanning multiple pages are handled twice over: adjacent blocks merge
when the continuation flags agree, and blocks sharing a label merge wherever
they are, which covers the student who comes back three pages later to add to
an earlier answer.

### 6. Grading (`grading.py`)

Runs last and fails soft. The brief lists grading as optional scope and it is
the stage most likely to hit a rate limit, so a failure here downgrades every
question to `ungraded` and leaves extraction, mapping and highlighting intact.
Unanswered questions are scored zero without a request, but marked `ungraded`
rather than `incorrect` — a blank page and a wrong answer are different things.

---

## Design

Built against the provided Figma file, with values read from the file rather
than eyeballed: Bricolage Grotesque, the `#eeeeee → #dadada` gradient with
blurred blobs behind glass panels, `#ff5623` brand orange, the `#303030` answer
sheet header, the three score-pill states (`#34ac15` at full marks, `#e3600f`
partial, `#c0350a` at zero) and the green highlight (`#5eff35` at 10% fill,
`#3dd218` 2px border, white outer ring, `#34ac15` tag above the corner).

Every token lives in the `@theme` block in `web/src/app/globals.css`, so
restyling is a change there rather than a sweep through components.

**Two states the design does not cover, added deliberately.** The Figma has no
state for an unanswered question or for an answer matching no question, but the
brief requires both. Unanswered questions get the zero-marks red pill, muted
question text, and an explicit line when expanded. Unmatched answers get their
own card at the foot of the list with a red `?` where the number badge would
be. Both are built from the design's own vocabulary rather than invented.

Regions are stored as page fractions (0–1) rather than pixels, so the overlay
is positioned in percent and stays correct at any zoom or container width, with
nothing to recompute on resize.

---

## Accuracy

Three of the six things this is judged on — question extraction, answer
mapping, correct highlighting — are claims that mean nothing without a number,
so they are measured rather than asserted.

`eval/make_synthetic_case.py` draws an answer sheet at coordinates it chooses
and records the ink bounds as it writes them, so the ground truth is exact
rather than eyeballed. The sheet answers the paper in `spike/out/` and puts
every awkward case from the brief on three pages: Q3 answered above Q2, `11(a)`
and `11(b)` as separate answers, `11(b)` running across a page break, nine
questions left blank, and a `Q14` on a paper that stops at 13.

Measured on that case (`eval/out/report.md`):

| | |
|---|---|
| question extraction F1 | **1.00** (precision 1.00, recall 1.00, 15/15) |
| printed order | **0 inversions** |
| answers mapped correctly | **100%** (6/6) |
| unanswered questions identified | **100%** (9/9) |
| answers matching no question | **F1 1.00** |
| highlight on the right page | **100%** (6/6) |
| highlight overlap with true ink | **median IoU 0.89** |

```bash
python eval/make_synthetic_case.py     # regenerate the sheet and its labels
python eval/run_eval.py --case synthetic
python eval/run_eval.py --rescore      # re-score the cache, no API calls
```

**What this is and isn't.** It is a calibration case: rendered handwriting, so
transcription is easier than a real scan, and a run that does not score near
perfect points at the pipeline rather than at the labelling. It is not evidence
about messy handwriting. It caught two real bugs on its first run — a box
format the parser was rejecting, and an orphaned label being reassigned by
content overlap — both of which had been silently degrading real runs.

For breadth over real handwriting, `eval/run_dataset_sweep.py` runs every
subject in `datasets/` and reports coverage against each paper's own printed
numbering. Read the caveat in **Assumptions and limitations** first: those
papers are reconstructions, so end-to-end accuracy over them is not a number
worth quoting.

---

## Running it

### Frontend

```bash
cd web
npm install
npm run dev            # http://localhost:3000
```

With `NEXT_PUBLIC_API_BASE` unset the app serves `src/lib/mock.ts`, a fixture
containing every edge case above — Q3 answered above Q2, `11(a)` and `11(b)` as
separate rows, `11(b)` spanning two pages, seven unanswered questions, and a
stray `Q14` on a paper that ends at 12. The mock page images are generated at
the exact coordinates in the fixture, so the highlight visibly lands on the
right block before any AI is involved.

Point it at the real API with `web/.env.local`:

```
NEXT_PUBLIC_API_BASE=https://your-api.onrender.com
```

### Choosing a model

Model choice is not a detail here — it is the difference between a run that
finishes and one that does not. Measured on a rendered A4 page from this
dataset, asking for the same JSON:

| model | latency | note |
|---|---|---|
| `gemini-3.1-flash-lite` | **2.2s** | with `thinking_budget=0`; the default |
| `gemini-3.5-flash-lite` | **2.5s** | first fallback |
| `gemini-3.1-flash-lite` | 176s | *without* the thinking budget applied |
| `gemini-flash-lite-latest` | 171s | resolves to a thinking model **and** rejects `thinking_budget`, so it cannot be made fast — deliberately not in the rotation |
| `gemini-3.6-flash` | 190s | |

Two things follow from that table. Extraction is a perception task, so
`thinking_budget=0` is set on every extraction call and thinking is turned back
on only for grading. And a model name that looks like the fast one is not
necessarily fast — `flash-lite-latest` is seventy times slower than
`3.1-flash-lite` on the same page.

### Free-tier quota, and the model rotation

The free tier grants **20 requests per day, per model**. Extraction costs one
request per page, so a single 18-page answer sheet very nearly exhausts one
model's entire daily allowance — and a second run that day will fail outright.

Calls therefore walk a rotation of models, each of which has its own quota
bucket. A `RESOURCE_EXHAUSTED` or `UNAVAILABLE` response moves straight to the
next model rather than backing off, because waiting cannot return a daily quota.
Set the list with `GEMINI_MODELS`; it defaults to four models, giving roughly
80 requests a day.

### Local Ollama mode

`AI_PROVIDER=ollama` runs the same pipeline against a local vision model, which
has no quota at all and keeps page images on the machine:

```bash
ollama pull gemma3:12b
```

```text
AI_PROVIDER=ollama
OLLAMA_MODEL=gemma3:12b
OLLAMA_BASE_URL=http://localhost:11434
```

**This needs a GPU.** It was measured on a 16GB CPU-only machine and is not
usable there: `gemma3:12b` read a *small crop* of one page, emitting 24 tokens,
in **394 seconds** (`size_vram: 0` — the whole model runs on CPU). It reads the
handwriting correctly, so this is a throughput problem rather than a quality
one, but a full page with a JSON reply extrapolates to roughly twenty minutes,
and an 18-page sheet to about six hours. `gemma3:4b` is around three times
faster, which is still hours per sheet.

Use this mode when there is a GPU or when data cannot leave the machine.
Otherwise the Gemini rotation above is the working path.

### Backend

```bash
cd api
pip install -r requirements.txt
cp .env.example .env                 # then put your key in it

# Auto-restarting (development):
python -m watchfiles --target-type command \
  "python -m uvicorn main:app --port 8001" pipeline main.py

# Plain (no restart on edit):
uvicorn main:app --port 8001
```

Restart-on-edit matters here: without it the server keeps serving the code it
imported at startup, so an edit to `api/pipeline/` has no effect and a real fix
looks like it changed nothing.

**Use `watchfiles`, not `uvicorn --reload`.** On Windows the built-in reloader
detects the change and logs `Reloading...`, but the restart never completes —
the old worker keeps serving, and it can end up sharing the port with a
newly-started one, so requests hit whichever answers first and behave
inconsistently. `watchfiles` supervises the process from outside and replaces
it in about two seconds, including while a job is mid-run. It ships with
`uvicorn[standard]`, so it is already installed.

Configuration is read from `api/.env` at import time, so a change there is
picked up by the same restart. Port 8001 is what `web/.env.local` expects.

### Tests

```bash
python api/tests/test_pipeline.py
```

Twelve tests over label parsing, question normalisation, box tightening and the
whole mapping ladder — no API calls, so they run free and fast. The tightening
tests are the ones worth keeping: they caught the margin-line bug described
above, which would have stretched every highlight to the left edge of the page.

### Box accuracy spike

```bash
GEMINI_API_KEY=... python spike/box_accuracy_spike.py path/to/answer_sheet.pdf
```

Writes `spike/out/overlay-*.png` with the raw proposal in red and the tightened
box in green. Run this against a real sheet before trusting anything else.

---

## Deploying

**API → Render.** Point Render at this repo, choose Blueprint, and it reads
`api/render.yaml`. Set `GEMINI_API_KEY` in the dashboard. Free instances sleep
after ~15 minutes idle and take 30–60s to wake, so a cron-job.org ping to
`/api/health` every 10 minutes keeps it warm — and the frontend shows an
explicit "waking the server" state so a cold start reads as designed rather
than broken.

**Web → Vercel.** Root directory `web`, set `NEXT_PUBLIC_API_BASE` to the
Render URL. Set `ALLOWED_ORIGINS` on the API to the Vercel URL once it exists.

---

## Assumptions and limitations

- **One student per run.** The brief says one answer sheet; there is no batch
  mode and no roster.
- **In-memory jobs.** Nothing persists. A job is evicted after twelve newer
  ones, and a redeploy loses everything in flight — acceptable given "no
  database required", and it is the reason page images are served from the API
  rather than stored.
- **10MB per upload**, matching the `Max 10MB` caption in the design. Large
  scans should be compressed first.
- **Free-tier quota is the binding constraint**, not rate limiting. The limit is
  20 requests per day *per model*, and extraction is one request per page, so a
  single 18-page sheet is ~19 requests — nearly a model's whole day. The
  rotation across four models raises the ceiling to roughly 80 requests a day,
  which is a handful of sheets, not a classroom. Marking a real class needs a
  paid key; nothing in the code changes for that beyond the quota.
- **Runtime is dominated by the model, not the pipeline.** An 18-page sheet
  takes ~258s end to end, of which answer extraction is ~64s (~3.5s per page)
  and grading is ~180s. The local work — rendering, tightening, mapping — is
  under a second in total.
- **The bundled dataset's papers are reconstructed, and do not fully match
  their booklets.** Every PDF in `datasets/` states on its first page that it
  was *reconstructed from the submitted answer booklet* — only the booklets
  were available, so a model inferred the questions from the visible working.
  They are excellent handwriting samples, but they are weak ground truth for
  mapping: the Hindi Core booklet answers questions 1–12 while its
  reconstructed paper contains only 1–7, and the content does not correspond
  either (answer `1.(i)` is an MCQ option, question `1(i)` asks for an
  explanation). Most of the unmatched answers on that sample are therefore
  correct behaviour rather than mapping error, and no accuracy number taken
  from this dataset should be quoted without that caveat. See
  [`docs/engineering-log.md`](docs/engineering-log.md).
- **Handwriting quality bounds everything.** Transcription drives both matching
  and marking, so a sheet that a human would struggle to read will map poorly.
  Confidence and the matching method are shown per answer so a teacher can see
  when the system was guessing.
- **Marks come from the paper** when it prints them, and default to 2 when it
  does not. There is no rubric or marking scheme input.
- **Grading is a language model's judgement**, not a moderated mark. It is
  shown as an aid, and the per-question feedback is there so a teacher can
  disagree with it quickly.
- **Diagrams are matched, not marked well.** A diagram is transcribed as its
  labels plus a short note, which is enough to map and highlight it but thin
  evidence for awarding marks.
