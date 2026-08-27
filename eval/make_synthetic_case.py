"""Generate a synthetic answer sheet whose ground truth is known exactly.

    python eval/make_synthetic_case.py

Writes:
    eval/cases/fixtures/synthetic.pdf   three pages of "handwriting"
    eval/cases/synthetic.json           the case file run_eval.py scores against

Why generate one rather than label a real sheet. Hand-labelling is the better
evidence and this does not replace it, but it costs about fifteen minutes a
sheet and it is itself error-prone at the edges — a human eyeballing a y range
is doing the same job the metric is meant to check. Here the sheet is *drawn*
at coordinates we choose, so the ink bounds are recorded as they are written
rather than estimated afterwards. That makes this a calibration case: a run
that does not score close to perfect on it points at the pipeline, not at the
labelling.

It answers the paper in `spike/out/question_paper.pdf`, and is arranged to put
every awkward case in the brief on one sheet:

    out of order          Q3 is answered above Q2
    labelled sub-parts    11(a) and 11(b) are separate answers
    spanning pages        11(b) runs off page 2 and finishes on page 3
    unanswered            4, 6, 7, 8, 9, 10, 12(i), 12(ii), 13 are absent
    matching nothing      Q14 is answered; the paper stops at 13

The text is real prose rather than the scribble in `spike/make_mock_pages.py`,
because the mapper has to be scored on reaching the *right* answer, and a
scribble gives it nothing to be right about.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "cases" / "fixtures"

W, H = 1000, 1400
PAPER = (253, 252, 249)
RULE = (206, 219, 236)
MARGIN = (233, 173, 178)
INK = (32, 52, 120)
LEFT, RIGHT = 120, W - 70
LINE_H = 44

# A real handwriting face keeps this honest: the point is to measure a vision
# model reading handwriting, and rendered Helvetica would be a much easier task
# than the one the product actually faces.
FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\Inkfree.ttf",
    r"C:\Windows\Fonts\segoesc.ttf",
    r"C:\Windows\Fonts\comic.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "/Library/Fonts/Comic Sans MS.ttf",
    # Linux
    "/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# (page, label, [paragraph lines]) — drawn in this order, top to bottom.
SHEET: list[tuple[int, str, list[str]]] = [
    (0, "Q1.", [
        "Blood is carried away from the heart by the arteries.",
        "The largest artery is the aorta, which leaves the",
        "left ventricle of the heart.",
    ]),
    # Out of order on purpose: 3 is answered before 2.
    (0, "Q3.", [
        "Chloroplasts contain the pigment chlorophyll, which",
        "absorbs light energy. Photosynthesis happens in two",
        "stages, the light dependent reactions and the Calvin",
        "cycle, which fixes carbon dioxide into sugars.",
    ]),
    (0, "Q2.", [
        "The chloroplast is the organelle mainly involved",
        "in photosynthesis.",
    ]),
    (1, "Q11 (a)", [
        "Plant A has broad green leaves because it gets",
        "bright light. Plant B is etiolated, with pale",
        "elongated leaves, because it grew in dim light.",
    ]),
    # Starts low on page 2 and finishes at the top of page 3.
    (1, "Q11 (b)", [
        "Move Plant B into bright sunlight for a few hours",
        "each day, and water it regularly so that",
    ]),
    (2, "", [
        "new leaves can grow broader and greener over",
        "the next two weeks.",
    ]),
    # The paper stops at 13, so this one matches nothing.
    (2, "Q14.", [
        "Osmosis makes an animal cell swell and burst when",
        "it is placed into pure water.",
    ]),
    (2, "Q5.", [
        "Diagram of an alveolus. The alveolar sac is wrapped",
        "in a capillary network. Oxygen diffuses into the",
        "blood and carbon dioxide diffuses out.",
    ]),
]

# label -> the word that proves the mapper reached the right answer.
NEEDLES = {
    "Q1.": "aorta",
    "Q3.": "chlorophyll",
    "Q2.": "chloroplast",
    "Q11 (a)": "etiolated",
    "Q11 (b)": "sunlight",
    "Q5.": "alveolar",
}

# Questions the paper prints, in printed order.
PAPER_QUESTIONS = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11(a)", "11(b)", "12(i)", "12(ii)", "13",
]

# How SHEET labels map onto the paper's numbering.
AS_QUESTION = {"Q1.": "1", "Q2.": "2", "Q3.": "3", "Q5.": "5",
               "Q11 (a)": "11(a)", "Q11 (b)": "11(b)"}


def font(size: int) -> ImageFont.FreeTypeFont:
    """The first available face from `FONT_CANDIDATES`.

    Regenerating the sheet on a machine with a different font set produces a
    *different* sheet, and therefore different numbers — which is the reason
    `synthetic.pdf` is committed rather than left to be rebuilt. Rebuild it
    only when you mean to, and re-run the eval when you do.
    """
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(
        "No usable font found. Add a path to FONT_CANDIDATES — a handwriting "
        "face is preferred, since the point is to make the model read "
        "handwriting rather than clean type.\n"
        "You do not need this to run the eval: eval/cases/fixtures/"
        "synthetic.pdf is committed, so `python eval/run_eval.py --case "
        "synthetic` works without regenerating anything."
    )


def blank_page(index: int, f_small: ImageFont.FreeTypeFont) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    for y in range(150, H - 60, LINE_H):
        draw.line([(70, y), (RIGHT + 20, y)], fill=RULE, width=1)
    draw.line([(104, 50), (104, H - 50)], fill=MARGIN, width=2)
    draw.text((W - 150, 34), f"Page {index + 1}", fill=(150, 150, 150), font=f_small)
    return img


def build() -> dict:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    f_hand = font(30)
    f_label = font(32)
    f_small = font(18)

    pages = [blank_page(i, f_small) for i in range(3)]
    draws = [ImageDraw.Draw(p) for p in pages]
    cursor = {0: 190, 1: 190, 2: 190}
    truth: dict[str, dict] = {}

    for page, label, lines in SHEET:
        draw = draws[page]
        y = cursor[page]
        top = y

        x = LEFT
        if label:
            draw.text((x, y), label, fill=INK, font=f_label)
            x = LEFT + int(draw.textlength(label, font=f_label)) + 18

        for i, line in enumerate(lines):
            draw.text((x if i == 0 else LEFT, y), line, fill=INK, font=f_hand)
            y += LINE_H

        bottom = y - LINE_H + 34
        # Record the ink bounds as drawn — no eyeballing after the fact.
        if label in AS_QUESTION:
            truth[AS_QUESTION[label]] = {
                "page": page,
                "y": [round(top / H, 4), round(bottom / H, 4)],
                "contains": NEEDLES[label],
            }
        cursor[page] = y + int(LINE_H * 1.6)

    pages[0].save(
        FIXTURES / "synthetic.pdf", save_all=True,
        append_images=pages[1:], resolution=150.0,
    )

    # Everything on the paper that this sheet does not answer.
    for q in PAPER_QUESTIONS:
        truth.setdefault(q, None)

    case = {
        "name": "synthetic",
        "_comment": (
            "Generated by eval/make_synthetic_case.py — do not hand-edit. "
            "Coordinates are the ink bounds as drawn, so this is a "
            "zero-error calibration case."
        ),
        "question_paper": "../../spike/out/question_paper.pdf",
        "answer_sheet": "fixtures/synthetic.pdf",
        "questions": PAPER_QUESTIONS,
        "expected": truth,
        "unmatched": ["Q14"],
    }
    (HERE / "cases" / "synthetic.json").write_text(
        json.dumps(case, indent=2), encoding="utf-8"
    )
    return case


def main() -> None:
    case = build()
    answered = sum(1 for v in case["expected"].values() if v)
    blank = sum(1 for v in case["expected"].values() if v is None)
    print(f"wrote {FIXTURES / 'synthetic.pdf'} (3 pages)")
    print(f"wrote {HERE / 'cases' / 'synthetic.json'}")
    print(f"  {len(case['questions'])} questions on the paper")
    print(f"  {answered} answered, {blank} left blank, "
          f"{len(case['unmatched'])} answer matching nothing")


if __name__ == "__main__":
    main()
