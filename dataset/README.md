# Manual test case

A hand-written answer sheet with independent ground truth, built to exercise
every edge case the brief names rather than to flatter the pipeline.

| file | what it is |
|---|---|
| `test_question_paper.pdf` | a 17-entry paper out of 40 marks |
| `answer-writing-script.pdf` | the script the sheet was copied from, by hand |
| `test_answer_sheet.pdf` | four sheets of real handwriting, scanned |
| `ground-truth.json` | the expected result, written **before** the sheet was marked |

The paper prints 14 numbers but contains **17 questions**: 11 and 14 each split
into two labelled sub-parts, and 13 appears twice as an internal choice
(OSI *or* TCP/IP). Both branches must be extracted; only one is meant to be
answered, and only one counts toward the 40.

## What the sheet deliberately gets wrong

The answers are written out of order on purpose, and some are wrong on purpose:

- **Out of order** — Q3 before Q2; Q9 after Q10; Q14(b) before Q14(a); and Q4
  answered on the last sheet, four pages from where it was printed.
- **Unanswered** — Q7 is skipped entirely and must be reported blank, never
  filled with a neighbouring answer.
- **Wrong on purpose** — Q5 answers Quick Sort where the paper wants Merge
  Sort, so a grader that marks everything correct is caught.
- **Partial credit** — Q10 gives one of the two conditions asked for, so a
  grader that only knows right and wrong is caught too.
- **Spanning pages** — Q12 stops mid-sentence at the foot of sheet 3 and
  resumes at the top of sheet 4 with no label, so the highlight must cover
  regions on both.
- **Internal choice** — only the TCP/IP branch of Q13 is answered.
- **Matching nothing** — a "Q15" is answered on a paper that ends at 14, and a
  block of rough working carries no label at all.

## Result

Scored **35 / 40 against a ground truth of 35**, with 16 of 17 questions exactly
right and every structural case above handled. The sheet earned its keep: its
first run exposed two real defects — a misread digit that cost two questions,
and an internal choice resolved to the wrong branch — both since fixed and
pinned by tests in `api/tests/test_pipeline.py`.
