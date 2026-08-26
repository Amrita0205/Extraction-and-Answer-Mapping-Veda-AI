"""Measure the pipeline against hand-labelled ground truth.

    python eval/run_eval.py                 # every case in eval/cases
    python eval/run_eval.py --case sheet-1  # just one
    python eval/run_eval.py --rescore       # re-score cached runs, no API calls

Why this exists: "accuracy of question extraction", "accuracy of answer
mapping" and "correct highlighting" are three of the six things this project
is judged on, and none of them can be improved by looking at one sheet and
squinting. This turns them into numbers that move when a prompt or a threshold
changes.

Raw pipeline output is cached per case under eval/out/. Scoring re-reads the
cache, so iterating on the metrics costs no API quota - which matters on a
free tier where a six-page sheet is seven requests.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics as M  # noqa: E402
from pipeline import answers as answers_mod  # noqa: E402
from pipeline import labels as L  # noqa: E402
from pipeline import mapping, render  # noqa: E402
from pipeline import questions as questions_mod  # noqa: E402

CASES = Path(__file__).resolve().parent / "cases"
OUT = Path(__file__).resolve().parent / "out"


def label_of(question) -> str:
    return L.display(question.number, question.part)


def run_pipeline(case: dict, case_dir: Path, cache: Path) -> dict:
    """Run extraction and mapping, and cache the raw result."""
    pages_dir = cache.parent / f"{case['name']}-pages"
    q_pages = render.render(case_dir / case["question_paper"], pages_dir, "q")
    a_pages = render.render(case_dir / case["answer_sheet"], pages_dir, "a")

    questions, _ = questions_mod.extract(q_pages)
    blocks, _ = answers_mod.extract(a_pages)
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    result = {
        "questions": [
            {
                "label": label_of(q),
                "text": q.text,
                "marks": q.marks,
                "status": q.status,
                "answer": (
                    {
                        "text": q.answer.text,
                        "method": q.answer.match_method,
                        "regions": [asdict(r) for r in q.answer.regions],
                    }
                    if q.answer
                    else None
                ),
            }
            for q in questions
        ],
        "unmatched": [
            {"label": b.label, "text": b.text} for b in unmatched
        ],
    }
    cache.write_text(json.dumps(result, indent=2))
    return result


def score(case: dict, result: dict) -> dict:
    expected_order: list[str] = case["questions"]
    expected_set = set(expected_order)
    predicted_order = [q["label"] for q in result["questions"]]
    predicted_set = set(predicted_order)

    precision, recall, f1 = M.prf(predicted_set, expected_set)
    inversions = M.order_errors(predicted_order, expected_order)

    by_label = {q["label"]: q for q in result["questions"]}
    expected_map: dict = case.get("expected", {})

    mapped = M.Score("answers mapped correctly")
    blanks = M.Score("blanks identified")
    page_ok = M.Score("highlight on right page")
    ious: list[float] = []

    for label, truth in expected_map.items():
        got = by_label.get(label)
        if got is None:
            mapped.total += 1
            mapped.notes.append(f"{label}: question was never extracted")
            continue

        if truth is None:  # should be unanswered
            blanks.total += 1
            if got["status"] == "unanswered":
                blanks.hits += 1
            else:
                blanks.notes.append(
                    f"{label}: expected blank, got an answer "
                    f"({got['answer']['text'][:45]!r})"
                )
            continue

        mapped.total += 1
        answer = got["answer"]
        if answer is None:
            mapped.notes.append(f"{label}: expected an answer, got none")
            continue

        needle = M.norm(truth.get("contains", ""))
        if needle and needle not in M.norm(answer["text"]):
            mapped.notes.append(
                f"{label}: mapped to the wrong answer "
                f"(wanted {needle!r}, got {answer['text'][:45]!r})"
            )
            continue
        mapped.hits += 1

        regions = answer["regions"]
        if not regions:
            page_ok.total += 1
            page_ok.notes.append(f"{label}: no region to highlight")
            continue

        page_ok.total += 1
        if any(r["page"] == truth["page"] for r in regions):
            page_ok.hits += 1
            same = [r for r in regions if r["page"] == truth["page"]]
            best = max(
                M.band_iou((r["y0"], r["y1"]), tuple(truth["y"])) for r in same
            )
            ious.append(best)
        else:
            page_ok.notes.append(
                f"{label}: highlighted page {regions[0]['page']}, "
                f"expected {truth['page']}"
            )

    stray_expected = {M.norm(s) for s in case.get("unmatched", [])}
    stray_got = {M.norm(u["label"] or "") for u in result["unmatched"]}
    s_p, s_r, s_f1 = M.prf(stray_got, stray_expected)

    return {
        "extraction": {"precision": precision, "recall": recall, "f1": f1,
                       "order_errors": inversions,
                       "expected": len(expected_set),
                       "got": len(predicted_set),
                       "missed": sorted(expected_set - predicted_set),
                       "invented": sorted(predicted_set - expected_set)},
        "mapped": mapped,
        "blanks": blanks,
        "page_ok": page_ok,
        "iou_median": M.median(ious),
        "iou_n": len(ious),
        "stray": {"precision": s_p, "recall": s_r, "f1": s_f1,
                  "expected": sorted(stray_expected),
                  "got": sorted(stray_got)},
    }


def report(name: str, s: dict) -> list[str]:
    e = s["extraction"]
    out = [
        f"### {name}",
        "",
        f"- question extraction  F1 **{e['f1']:.2f}**  "
        f"(precision {e['precision']:.2f}, recall {e['recall']:.2f}; "
        f"{e['got']}/{e['expected']} labels)",
        f"- printed order        {e['order_errors']} inversion(s)",
        f"- {s['mapped'].line()}",
        f"- {s['blanks'].line()}",
        f"- {s['page_ok'].line()}",
        f"- highlight overlap    median IoU **{s['iou_median']:.2f}** "
        f"over {s['iou_n']} region(s)",
        f"- unmatched answers    F1 {s['stray']['f1']:.2f} "
        f"(expected {s['stray']['expected']}, got {s['stray']['got']})",
    ]
    if e["missed"]:
        out.append(f"- **missed questions**: {', '.join(e['missed'])}")
    if e["invented"]:
        out.append(f"- **questions invented**: {', '.join(e['invented'])}")
    for sc in (s["mapped"], s["blanks"], s["page_ok"]):
        for note in sc.notes:
            out.append(f"  - {note}")
    out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", help="run only this case by name")
    ap.add_argument("--rescore", action="store_true",
                    help="score cached runs without calling the API")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    files = sorted(CASES.glob("*.json"))
    if args.case:
        files = [f for f in files if f.stem == args.case]
    if not files:
        print(f"No cases in {CASES}. See eval/README.md for the format.")
        return 2

    lines = ["# Accuracy report", ""]
    agg = {"f1": [], "mapped": M.Score("answers mapped correctly"),
           "blanks": M.Score("blanks identified"),
           "page": M.Score("highlight on right page"), "iou": []}

    for path in files:
        case = json.loads(path.read_text())
        cache = OUT / f"{case['name']}.raw.json"

        if args.rescore or cache.exists():
            if not cache.exists():
                print(f"  {case['name']}: no cached run, skipping")
                continue
            result = json.loads(cache.read_text())
            print(f"  {case['name']}: scoring cached run")
        else:
            missing = [
                key for key in ("question_paper", "answer_sheet")
                if not (path.parent / case[key]).exists()
            ]
            if missing:
                # The shipped template points at files that only exist once
                # you have labelled a real sheet. Say so instead of crashing.
                print(f"  {case['name']}: skipped, no "
                      + " or ".join(case[k] for k in missing))
                continue
            print(f"  {case['name']}: running pipeline (this costs API quota)")
            result = run_pipeline(case, path.parent, cache)

        s = score(case, result)
        lines += report(case["name"], s)

        agg["f1"].append(s["extraction"]["f1"])
        for key, sc in (("mapped", s["mapped"]), ("blanks", s["blanks"]),
                        ("page", s["page_ok"])):
            agg[key].hits += sc.hits
            agg[key].total += sc.total
        agg["iou"] += [s["iou_median"]] * s["iou_n"]

    lines = lines[:2] + [
        "## Across all cases", "",
        f"- question extraction  mean F1 **{M.median(agg['f1']):.2f}** "
        f"over {len(agg['f1'])} sheet(s)",
        f"- {agg['mapped'].line()}",
        f"- {agg['blanks'].line()}",
        f"- {agg['page'].line()}",
        f"- highlight overlap    median IoU **{M.median(agg['iou']):.2f}**",
        "", "---", "",
    ] + lines[2:]

    text = "\n".join(lines)
    (OUT / "report.md").write_text(text)

    # Machine-readable twin of the aggregate block, so other tooling (the
    # dataset-sweep dashboard) can read real numbers instead of scraping
    # markdown.
    summary = {
        "cases": len(agg["f1"]),
        "extraction_f1_median": M.median(agg["f1"]),
        "mapped_rate": agg["mapped"].value,
        "mapped_hits": agg["mapped"].hits,
        "mapped_total": agg["mapped"].total,
        "blanks_rate": agg["blanks"].value,
        "blanks_hits": agg["blanks"].hits,
        "blanks_total": agg["blanks"].total,
        "page_ok_rate": agg["page"].value,
        "page_ok_hits": agg["page"].hits,
        "page_ok_total": agg["page"].total,
        "highlight_iou_median": M.median(agg["iou"]),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    print()
    print(text)
    print(f"\nwritten to {OUT / 'report.md'} and {OUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
