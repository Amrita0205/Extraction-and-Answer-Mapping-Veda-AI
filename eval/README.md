# Accuracy harness

Three of the six things this project is judged on are accuracy of question
extraction, accuracy of answer mapping, and correct highlighting. None of them
improve by looking at one sheet and squinting. This turns them into numbers
that move when a prompt or a threshold changes.

```bash
python eval/run_eval.py                 # every case
python eval/run_eval.py --case sheet-1  # one case
python eval/run_eval.py --rescore       # re-score cached runs, no API calls
```

Raw pipeline output is cached per case in `eval/out/`. Scoring reads the
cache, so iterating on metrics or thresholds costs no API quota — which
matters on a free tier where one six-page sheet is seven requests. Delete the
cache file to force a fresh run.

## What it reports

| Metric | Meaning |
|---|---|
| question extraction F1 | exact set match on printed labels, so `11(a)` must come out as `11(a)` |
| printed order | adjacent pairs returned in the wrong relative order |
| answers mapped correctly | the mapped answer contains the distinctive phrase you labelled |
| blanks identified | questions you left unanswered that came back `unanswered` |
| highlight on right page | the region landed on the page the answer is actually on |
| highlight overlap | median vertical IoU between the highlighted band and the real one |
| unmatched answers | F1 on answers whose label matches no question |

Vertical IoU rather than a full box: answers run the width of the page, so the
y-extent is what a teacher judges, and a y-band is something you can label by
eye in seconds. That matters when the labelling budget is one evening.

## Labelling a case

Copy `cases/example.json`, point it at your files, and edit. Twenty minutes
for your first sheet, five for each after.

```jsonc
{
  "name": "sheet-1",
  "question_paper": "fixtures/question_paper.pdf",
  "answer_sheet":  "fixtures/sheet-1.pdf",

  // Every label the paper prints, in printed order.
  "questions": ["1", "2", "3", "11(a)", "11(b)"],

  // Only the questions you want scored. Omit one to skip it.
  "expected": {
    // page is 0-based; y is the top and bottom of the answer as a fraction
    // of page height - eyeball it, a rough band is fine.
    // contains is a distinctive word from the answer, so scoring survives
    // transcription wobble.
    "1":     {"page": 0, "y": [0.10, 0.24], "contains": "artery"},
    "3":     {"page": 0, "y": [0.28, 0.46], "contains": "chloroplast"},
    "4":     null,          // deliberately left blank
    "11(b)": {"page": 1, "y": [0.30, 0.94], "contains": "sunlight"}
  },

  // Labels you wrote that match no question on the paper.
  "unmatched": ["Q15"]
}
```

Estimating `y`: open the page image, note where the answer starts and ends as
a fraction from the top. An answer beginning a third of the way down and
ending two-thirds down is `[0.33, 0.66]`. Precision to ±0.03 is plenty — IoU
is being used to catch boxes that are wildly loose or on the wrong block, not
to grade pixels.

## Getting the sheets

`spike/README.md` covers this. Short version: CBSE publishes real scanned
candidate answer booklets free at
<https://www.cbse.gov.in/cbsenew/model-answer.html>, and
`spike/make_question_paper.py` generates a paper designed so one sheet you
write by hand covers every edge case those booklets never contain.

Three sheets is the minimum worth reporting — your own for the edge cases,
two CBSE booklets for genuine handwriting. It is not a statistic, but it
catches catastrophic failure, it gives tuning something to move, and
"measured on three sheets" is honest.

Put the files in `eval/cases/fixtures/`, which is gitignored — CBSE booklets
are not yours to redistribute, and scans are large.
