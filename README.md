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
| AI model | Google **Gemini 2.5 Flash** (free tier) |
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

A printed question paper usually arrives as a PDF with a real text layer. When
it does, the text is what gets sent to the model rather than the page image —
OCR error is the dominant source of extraction mistakes and a text layer has
none of it. Scans and photographs fall back to vision, one page per request.

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

### Backend

```bash
cd api
pip install -r requirements.txt
export GEMINI_API_KEY=...            # https://aistudio.google.com/apikey
uvicorn main:app --reload --port 8000
```

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
- **Free-tier rate limits** are real. Extraction is one request per page, so a
  ten-page sheet is ten requests plus grading; a burst can hit the per-minute
  limit and the retry backoff will slow the run rather than fail it.
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
