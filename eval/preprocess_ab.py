"""Measure what page cleaning does to an image, without calling the API.

    python eval/preprocess_ab.py                       # the hand-marked sheet
    python eval/preprocess_ab.py --src path/to/file.pdf
    python eval/preprocess_ab.py --save eval/out/ab    # write before/after PNGs

`run_eval.py` is the one that answers "did accuracy improve", and it costs
quota every time it runs. This answers the cheaper question that has to come
first: is the cleaning doing the thing it claims, on these pages, at all. If
the residual skew does not fall and the background does not flatten, there is
nothing for an accuracy run to detect and no reason to spend requests on it.

Three numbers per page, all measured on the pixels and none of them on the
model:

    residual skew   degrees of tilt still detectable after cleaning. The
                    honest test of a deskew: run the estimator again and it
                    should now find nothing worth correcting.
    background      how far the estimated paper level varies across the page,
                    in grey levels. A shadowed photo starts high; even
                    lighting is a small number.
    separation      paper level minus ink level. Higher is a crisper page.
                    This one is stretched on purpose, so a rise is the
                    operation working rather than independent evidence that
                    it helped - the skew and background columns are the
                    interesting ones.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from pipeline import preprocess as prep  # noqa: E402
from pipeline import render  # noqa: E402

DEFAULT_SRC = ROOT / "dataset" / "test_answer_sheet.pdf"


def pages_of(src: Path) -> list[Image.Image]:
    """The raw render, before any cleaning - the "before" arm."""
    import fitz

    if src.suffix.lower() != ".pdf":
        return [Image.open(src).convert("RGB")]

    doc = fitz.open(src)
    zoom = render.RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    out = []
    for page in doc:
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
        out.append(render._downscale(img))
    doc.close()
    return out


def measure(img: Image.Image) -> dict:
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    background = prep._background(gray)
    return {
        "skew": abs(prep._skew_angle(gray)),
        "background": float(background.max() - background.min()),
        "separation": float(
            np.percentile(gray, prep.PAPER_ANCHOR)
            - np.percentile(gray, prep.INK_PERCENTILE)
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--save", type=Path, help="write before/after PNGs here")
    args = ap.parse_args()

    if not args.src.exists():
        print(f"no such file: {args.src}")
        return 2

    print(f"{args.src.name} at {render.RENDER_DPI} DPI\n")
    header = f"{'page':>5}  {'residual skew':>26}  {'background':>22}  {'separation':>22}"
    print(header)
    print("-" * len(header))

    deltas: dict[str, list[float]] = {"skew": [], "background": [], "separation": []}
    applied: list[dict] = []

    for i, raw in enumerate(pages_of(args.src)):
        before = measure(raw)
        clean, steps = prep.preprocess(raw)
        after = measure(clean)
        applied.append(steps)

        for key in deltas:
            deltas[key].append(after[key] - before[key])

        print(
            f"{i:>5}  "
            f"{before['skew']:>10.2f} -> {after['skew']:<10.2f}    "
            f"{before['background']:>8.1f} -> {after['background']:<8.1f}  "
            f"{before['separation']:>8.1f} -> {after['separation']:<8.1f}"
        )

        if args.save:
            args.save.mkdir(parents=True, exist_ok=True)
            raw.save(args.save / f"page-{i}-before.png")
            clean.save(args.save / f"page-{i}-after.png")

    print()
    for key, label in (
        ("skew", "residual skew"),
        ("background", "background range"),
        ("separation", "ink/paper separation"),
    ):
        mean = sum(deltas[key]) / max(1, len(deltas[key]))
        print(f"  mean change in {label:<22} {mean:+.2f}")

    print("\nwhat was applied, per page:")
    for i, steps in enumerate(applied):
        print(f"  page {i}: {steps or 'nothing - page was already clean'}")

    if args.save:
        print(f"\nimages written to {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
