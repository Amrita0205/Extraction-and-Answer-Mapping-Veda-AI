# Test data and accuracy checks

Two kinds of sample data are useful here, and they test different things.

> **Both now exist in the repo.** `dataset/` holds a hand-written sheet with
> ground truth, covering the edge cases below; `datasets/` holds 14 subjects of
> real CBSE handwriting. This page records where they came from and how to make
> more.

## 1. Real handwriting — tests accuracy

CBSE publishes **scanned answer sheets written by actual candidates**, free and
without a login, under "Model Answer by Candidate for Examination":

<https://www.cbse.gov.in/cbsenew/model-answer.html>

Class 10 and 12, most subjects, 2019 through 2025. Direct PDFs follow
`https://www.cbse.gov.in/cbsenew/model-answer/<year>/<class>/<subject>.pdf` —
for example the 2019 Class 10 Science paper at
`https://www.cbse.gov.in/cbsenew/model-answer/2019/086_SCIENCE.pdf`.

This is the closest thing to VedaAI's real input: Indian school handwriting on
ruled paper, with the student's own question numbers, diagrams and crossings
out. Pair one with the matching previous-year question paper from the same
site.

What it will **not** test: candidates in these booklets answer in order,
answer everything, and never write a number that isn't on the paper. So it
exercises extraction and highlighting but none of the edge cases.

Other sources worth knowing: the [Student Handwritten Exam Dataset on IEEE
DataPort](https://ieee-dataport.org/documents/student-handwritten-exam-dataset)
and a [Mendeley dataset of digitized exam papers with answer keys and manual
evaluations](https://data.mendeley.com/datasets/sf3kvjwknt/1). Both need
registration.

## 2. A sheet you write yourself — tests the edge cases

```bash
python spike/make_question_paper.py     # writes spike/out/question_paper.pdf
```

Fifteen questions across two pages, with a real text layer, deliberately built
so a single handwritten sheet can cover everything the brief asks for. Print
it or keep it on screen, then write answers on ruled paper doing all of this:

| Write this | What it tests |
|---|---|
| Answer **Q1**, then **Q3**, then **Q2** — in that order down the page | answers written out of order |
| Label two answers **11 (a)** and **11 (b)** | labelled sub-parts as separate entries |
| Start **11 (b)** near the bottom of page 1 and finish it at the top of page 2 | an answer spanning multiple pages |
| Use roman sub-parts for **12 (i)** and **12 (ii)** | a second sub-part style |
| Leave **Q4**, **Q7** and **Q9** blank entirely | unanswered questions |
| Write an answer labelled **Q15** (the paper stops at 13) | an answer matching no question |
| Draw the alveolus for **Q5** rather than writing prose | a diagram as an answer region |

Photograph each page square-on in even light, or scan at 200–300 DPI. Phone
photos are fine and are what a teacher would actually upload — but avoid
shadows across the page, which the ink-detection pass in `tighten.py` will read
as a dark region.

## Running the checks

Box accuracy, before trusting anything else:

```bash
python spike/box_accuracy_spike.py path/to/answer_sheet.pdf
```

Writes `spike/out/overlay-*.png` with the model's raw box in red and the
tightened box in green. Green should hug the handwriting with a hairline of
margin and no band of blank paper underneath.

Full pipeline:

```bash
cd api && uvicorn main:app --reload --port 8001
# then upload both files at http://localhost:3000
```

Logic tests, no API calls and no key needed:

```bash
python api/tests/test_pipeline.py
```
