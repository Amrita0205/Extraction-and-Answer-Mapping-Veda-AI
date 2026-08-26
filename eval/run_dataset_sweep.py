"""Run the extraction + mapping pipeline across a whole dataset of real
subject folders and report per-subject, non-circular accuracy signals.

    python eval/run_dataset_sweep.py                   # every subject in datasets/
    python eval/run_dataset_sweep.py --subject physics  # just one
    python eval/run_dataset_sweep.py --grade            # also run grading (extra API calls)

Why "non-circular" matters here: every question paper under
datasets/<subject>/ is an AI *reconstruction* from the answer booklet
itself — each PDF says so on its own first page ("Reconstructed Question
Paper... reconstructed from the submitted answer booklet"). That's fine as
a source of real handwriting to transcribe, but it is not an independently
set exam paper, so scoring "did the mapper pick the right question for this
answer" against it would partly be grading our own reconstruction against
itself — the question wording was derived from the answer in the first
place, which flatters content-similarity matching in particular.

What stays legitimate on this data:
  - question *extraction* completeness against the paper's own printed
    numbering — checked with an independent regex over the PDF's own text
    layer, never against anything the pipeline produced
  - answer *transcription* and *highlighting* — both depend only on the
    real scanned handwriting, never on the reconstructed question text
  - the *label* and *sequential* rungs of the mapping ladder, which key off
    the student's own handwriting, not question content
  - pipeline robustness: warnings, failures, timing, confidence

What is flagged rather than trusted:
  - the *semantic* mapping rung (content-similarity / model adjudication),
    which leans on question wording that was itself derived from the
    answer it is now being matched against

See eval/run_eval.py for the hand-labelled, genuinely non-circular
precision/recall/F1 numbers this sweep is deliberately not trying to
replace — that harness is the one to quote as "accuracy" in the write-up.
This one is the breadth story: "ran clean across N real CBSE subjects."
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from pipeline import answers as answers_mod  # noqa: E402
from pipeline import gemini  # noqa: E402
from pipeline import grading  # noqa: E402
from pipeline import mapping, render  # noqa: E402
from pipeline import questions as questions_mod  # noqa: E402

DATASETS = ROOT / "datasets"
OUT = Path(__file__).resolve().parent / "out"

# Matches "Q.21", "Q 21", "Q21" and the Hindi "प्रश्न1." marker used in the
# Hindi Core paper. Deliberately simple: this is a cross-check, not a parser.
MARKER = re.compile(r"(?:Q\.?\s*|प्रश्न\s*)(\d{1,3})\b")


def oracle_markers(pdf_path: Path) -> list[int]:
    """Independent count of question markers in the paper's own text layer."""
    import fitz

    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return sorted({int(n) for n in MARKER.findall(text)})


def region_sanity(regions: list) -> dict:
    if not regions:
        return {"count": 0, "degenerate": 0, "avg_area_fraction": 0.0}
    areas = [max(0.0, r.x1 - r.x0) * max(0.0, r.y1 - r.y0) for r in regions]
    # A highlight covering under 0.1% or over 60% of the page is almost
    # certainly a box that slipped, not a real answer region.
    degenerate = sum(1 for a in areas if a < 0.001 or a > 0.6)
    return {
        "count": len(regions),
        "degenerate": degenerate,
        "avg_area_fraction": sum(areas) / len(areas),
    }


def run_subject(name: str, subject_dir: Path, do_grade: bool) -> dict:
    q_files = list(subject_dir.glob("*Question_Paper.pdf"))
    a_files = list(subject_dir.glob("*Answer_Sheet.pdf"))
    if not q_files or not a_files:
        return {"error": f"missing question paper or answer sheet in {subject_dir}"}

    q_path, a_path = q_files[0], a_files[0]
    started = time.monotonic()

    try:
        pages_dir = OUT / f"{name}-pages"
        q_pages = render.render(q_path, pages_dir, "q")
        a_pages = render.render(a_path, pages_dir, "a")

        questions, w1 = questions_mod.extract(q_pages)
        blocks, w2 = answers_mod.extract(a_pages)
        questions, unmatched, w3 = mapping.map_answers(questions, blocks)
        warnings = [*w1, *w2, *w3]

        graded_summary = None
        if do_grade:
            graded, overall, w4 = grading.grade(questions)
            warnings += w4
            verdicts: dict[str, int] = {}
            for q in graded:
                if q.grade:
                    verdicts[q.grade.verdict] = verdicts.get(q.grade.verdict, 0) + 1
            graded_summary = {"verdicts": verdicts, "overall_feedback": overall}
            questions = graded
    except Exception as exc:  # noqa: BLE001 - one bad subject must not sink the sweep
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": round(time.monotonic() - started, 1),
        }

    oracle = oracle_markers(q_path)
    extracted_numbers = sorted({int(q.number) for q in questions if q.number.isdigit()})
    coverage = (
        len(set(extracted_numbers) & set(oracle)) / len(oracle) if oracle else None
    )

    by_method: dict[str, int] = {}
    confidences: list[float] = []
    all_regions = []
    for q in questions:
        if q.answer:
            by_method[q.answer.match_method] = by_method.get(q.answer.match_method, 0) + 1
            confidences.append(q.answer.confidence)
            all_regions += q.answer.regions

    answered = sum(1 for q in questions if q.status == "answered")
    total = len(questions)
    method_total = sum(by_method.values())

    return {
        "question_paper": q_path.name,
        "answer_sheet": a_path.name,
        "elapsed_s": round(time.monotonic() - started, 1),
        "questions": {
            "extracted": total,
            "with_subparts": sum(1 for q in questions if q.part),
            "oracle_markers": oracle,
            "coverage_vs_oracle": coverage,
        },
        "answers": {"blocks_extracted": len(blocks)},
        "mapping": {
            "answered": answered,
            "unanswered": total - answered,
            "unmatched": len(unmatched),
            "resolution_rate": answered / total if total else None,
            "by_method": by_method,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
            "semantic_share": (by_method.get("semantic", 0) / method_total
                                if method_total else None),
        },
        "highlight": region_sanity(all_regions),
        "grading": graded_summary,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", help="run only this subject folder")
    ap.add_argument("--grade", action="store_true",
                     help="also run grading (extra API calls; no ground-truth "
                          "marks exist for this data, so treat verdicts as a "
                          "sanity check, not an accuracy number)")
    args = ap.parse_args()

    if not DATASETS.exists():
        print(f"No datasets/ folder at {DATASETS}")
        return 2

    OUT.mkdir(exist_ok=True)
    subjects = sorted(p for p in DATASETS.iterdir() if p.is_dir())
    if args.subject:
        subjects = [p for p in subjects if p.name == args.subject]
    if not subjects:
        print("No matching subject folders.")
        return 2

    results: dict[str, dict] = {}
    for subject_dir in subjects:
        print(f"  {subject_dir.name}: running ({gemini.PROVIDER})...")
        r = run_subject(subject_dir.name, subject_dir, args.grade)
        results[subject_dir.name] = r
        if "error" in r:
            print(f"    failed: {r['error']}")
        else:
            print(f"    {r['questions']['extracted']} questions, "
                  f"{r['mapping']['answered']} answered, "
                  f"{r['mapping']['unmatched']} unmatched, "
                  f"{r['elapsed_s']}s")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": gemini.PROVIDER,
        "model": gemini.MODEL if gemini.PROVIDER == "gemini" else gemini.OLLAMA_MODEL,
        "subjects": results,
    }
    out_path = OUT / "dataset_sweep.json"
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\nwritten to {out_path}")
    print("Next: python eval/dashboard.py   to build the HTML report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
