"""Score the hand-written sheet in `dataset/` against its own ground truth.

    python eval/score_dataset.py            # run the pipeline, then score
    python eval/score_dataset.py --rescore  # score the cached run, no API calls

`dataset/ground-truth.json` was written before the sheet was ever marked, so it
cannot have been fitted to the output. It is the strongest accuracy evidence in
the repo and the source of the "35 / 40" in the README - but until now that
number was produced by reading a run and comparing by eye, which is not
something a reviewer can repeat and not something a change can be tested
against. This makes it one command.

The run costs API quota: one request per page of the paper, one per page of the
sheet, plus grading. The raw output is cached under `eval/out/`, so iterating on
the scoring itself is free.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from pipeline import answers as answers_mod  # noqa: E402
from pipeline import grading, labels, mapping, render  # noqa: E402
from pipeline import preprocess as prep  # noqa: E402
from pipeline import questions as questions_mod  # noqa: E402

DATA = ROOT / "dataset"
OUT = Path(__file__).resolve().parent / "out"
CACHE = OUT / "dataset.raw.json"

# Ground truth numbers the sheets the way a person does, from 1. Everything in
# the pipeline indexes pages from 0.
PAGE_OFFSET = 1


def gt_key(entry: dict) -> str:
    return labels.key(entry["number"], entry.get("sub_part"))


def run() -> dict:
    pages_dir = OUT / "dataset-pages"
    q_pages = render.render(DATA / "test_question_paper.pdf", pages_dir, "q")
    a_pages = render.render(DATA / "test_answer_sheet.pdf", pages_dir, "a")

    questions, _ = questions_mod.extract(q_pages)
    blocks, _ = answers_mod.extract(a_pages)
    # Kept before mapping consumes them: when a run goes wrong it is almost
    # always a label the model misread, and that is only visible here.
    raw_blocks = [
        {
            "id": b.id,
            "label": b.label,
            "pages": sorted({r.page for r in b.regions}),
            "text": b.text[:100],
        }
        for b in blocks
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)
    graded, overall, _ = grading.grade(questions)
    summary = grading.summarise(questions, unmatched, graded, overall)

    result = {
        "answer_pages": len(a_pages),
        "render_dpi": render.RENDER_DPI,
        "preprocess": prep.enabled(),
        "questions": [
            {
                "label": labels.display(q.number, q.part),
                "key": labels.key(q.number, q.part),
                "status": q.status,
                "max_marks": q.marks,
                "branch": q.choice_branch,
                "method": (q.answer.match_method if q.answer else None),
                "confidence": (q.answer.confidence if q.answer else None),
                "awarded": (q.grade.awarded if q.grade else None),
                "verdict": (q.grade.verdict if q.grade else None),
                "pages": sorted(
                    {r.page for r in q.answer.regions} if q.answer else set()
                ),
                "text": (q.answer.text[:120] if q.answer else None),
            }
            for q in questions
        ],
        "blocks": raw_blocks,
        "unmatched": [{"label": b.label, "text": b.text[:80]} for b in unmatched],
        "summary": summary.model_dump() if hasattr(summary, "model_dump") else summary,
    }
    OUT.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def score(truth: dict, result: dict) -> int:
    expected = truth["questions"]
    got = {q["key"]: q for q in result["questions"]}
    breakdown = truth["expected_grading_summary"]["breakdown"]

    print(f"{'question':<10} {'status':<26} {'marks':<12} {'page':<14}")
    print("-" * 66)

    wrong_status = wrong_marks = wrong_page = 0
    seen_13 = 0

    for entry in expected:
        key = gt_key(entry)
        label = entry["id"]
        mine = got.get(key)

        # 13 prints twice as an internal choice, so its label is ambiguous by
        # design. The branch index is not: 0 is the first alternative, 1 is the
        # one after the OR, and ground truth lists them in that printed order.
        if entry["number"] == "13":
            want_branch = seen_13
            seen_13 += 1
            mine = next(
                (
                    q
                    for q in result["questions"]
                    if q["key"] == key and q.get("branch", 0) == want_branch
                ),
                None,
            )

        if mine is None:
            print(f"{label:<10} {'NOT EXTRACTED':<26}")
            wrong_status += 1
            continue

        want_status = {
            "answered": "answered",
            "not_attempted": "unanswered",
            "not_chosen": "not_chosen",
        }[entry["answer_status"]]
        status_ok = mine["status"] == want_status
        wrong_status += not status_ok

        want_marks = breakdown.get(label)
        mine_marks = mine["awarded"]
        marks_ok = want_marks is None or _close(mine_marks, want_marks)
        wrong_marks += not marks_ok
        want_pages = entry.get("answer_page")
        if want_pages is None:
            page_note = "-"
            page_ok = True
        else:
            wanted = {
                p - PAGE_OFFSET
                for p in (want_pages if isinstance(want_pages, list) else [want_pages])
            }
            page_ok = bool(wanted & set(mine["pages"]))
            wrong_page += not page_ok
            page_note = f"{sorted(wanted)} got {mine['pages']}"

        print(
            f"{label:<10} "
            f"{(mine['status'] + ('' if status_ok else f' WANT {want_status}')):<26} "
            f"{(str(mine_marks) + ('' if marks_ok else f' WANT {want_marks}')):<12} "
            f"{('' if page_ok else 'WRONG ') + page_note:<14}"
        )

    expected_total = truth["expected_grading_summary"]["marks_awarded"]
    expected_possible = truth["expected_grading_summary"]["marks_possible"]
    reported = result["summary"].get("marks_awarded")
    possible = result["summary"].get("marks_total")

    print()
    print(f"  questions extracted   {len(result['questions'])}"
          f" / {truth['paper']['expected_question_count']}")
    print(f"  status mismatches     {wrong_status}")
    print(f"  marks mismatches      {wrong_marks}")
    print(f"  highlight wrong page  {wrong_page}")
    print(f"  unmatched blocks      {len(result['unmatched'])}"
          f" / {len(truth['unmatched_blocks'])}"
          f"   {[u['label'] for u in result['unmatched']]}")
    print(f"  config                {result.get('render_dpi', '?')} DPI, "
          f"cleaning {'on' if result.get('preprocess') else 'OFF'}")
    print(f"  score reported        {reported} / {possible}"
          f"   (ground truth {expected_total} / {expected_possible})")

    failures = (
        wrong_status
        + wrong_marks
        + (len(result["questions"]) != truth["paper"]["expected_question_count"])
        + (not _close(reported, expected_total))
        + (not _close(possible, expected_possible))
    )
    print(f"\n  {'PASS' if not failures else str(failures) + ' DEVIATION(S)'}")
    return 1 if failures else 0


def _close(a, b) -> bool:
    if a is None or b is None:
        return a == b
    return abs(float(a) - float(b)) < 0.01


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescore", action="store_true",
                    help="score the cached run instead of calling the API")
    args = ap.parse_args()

    truth = json.loads((DATA / "ground-truth.json").read_text(encoding="utf-8"))

    if args.rescore:
        if not CACHE.exists():
            print(f"no cached run at {CACHE}")
            return 2
        result = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"scoring cached run from {CACHE}\n")
    else:
        print("running the pipeline (this costs API quota)\n")
        result = run()

    return score(truth, result)


if __name__ == "__main__":
    raise SystemExit(main())
