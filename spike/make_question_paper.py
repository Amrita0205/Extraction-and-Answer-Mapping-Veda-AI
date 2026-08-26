"""Generate a question paper PDF for end-to-end testing.

Real CBSE papers are the better accuracy test, but they answer everything in
order, so they exercise none of the awkward cases the brief lists. This paper
is built so that one handwritten answer sheet can cover all of them:

  - 11 (a) and 11 (b) are labelled sub-parts, and must come out as two entries
  - 12 (i) / 12 (ii) use roman numerals, a different sub-part style
  - the paper stops at 13, so writing an answer labelled "Q15" on the sheet
    produces an answer that matches nothing
  - marks are printed in brackets, so mark extraction has something to find
  - question 7's stem runs long enough to wrap, which is where naive
    extraction tends to truncate

Output has a real text layer, so it also exercises the text-layer path in
questions.py rather than the vision fallback.

    python spike/make_question_paper.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUT = Path(__file__).resolve().parent / "out" / "question_paper.pdf"

# (number, part, text, marks)
QUESTIONS: list[tuple[str, str | None, str, int]] = [
    ("1", None, "Which blood vessel carries blood away from the heart?", 2),
    ("2", None, "Which organelle is primarily involved in photosynthesis?", 2),
    ("3", None,
     "Explain the role of chloroplasts in photosynthesis, naming the main "
     "pigments involved and briefly outlining the two major stages of the "
     "process.", 3),
    ("4", None,
     "Describe the flow of blood through the human heart, starting from the "
     "right atrium and ending at the aorta. Include the names of the valves "
     "crossed.", 3),
    ("5", None,
     "Draw a labelled diagram of an alveolus showing the capillary network "
     "and the air space. Label the alveolar sac, the capillary, and the "
     "direction of gas exchange.", 3),
    ("6", None,
     "State two structural features of the small intestine that increase the "
     "rate of absorption.", 2),
    ("7", None,
     "Draw and label a nephron, marking Bowman's capsule, the glomerulus, the "
     "proximal convoluted tubule, the loop of Henle, the distal convoluted "
     "tubule and the collecting duct. Indicate on your diagram the region "
     "where most reabsorption of water takes place.", 5),
    ("8", None,
     "Explain the structural differences between palisade mesophyll and "
     "spongy mesophyll, and state how each structure aids its function in "
     "the leaf.", 5),
    ("9", None,
     "Describe the process of transpiration in two to three sentences, and "
     "name two environmental factors that increase its rate.", 4),
    ("10", None,
     "Explain how the structure of xylem vessels facilitates water transport "
     "in plants. Mention one structural feature and its role.", 4),
    ("11", "a",
     "Two potted plants are kept side by side. Plant A stands in bright light "
     "and has broad green leaves. Plant B is kept in dim light and has pale, "
     "elongated leaves. Explain the difference in appearance.", 3),
    ("11", "b", "Suggest one practical measure to help Plant B recover.", 2),
    ("12", "i",
     "A resting person has a tidal volume of 0.5 L and breathes 12 times per "
     "minute. Calculate the pulmonary ventilation rate. Show your working.", 3),
    ("12", "ii",
     "If the dead space is 0.15 L per breath, calculate the alveolar "
     "ventilation rate per minute.", 3),
    ("13", None,
     "Define osmosis, and give one example of osmosis in a plant cell.", 3),
]


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "title", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=15, leading=19, alignment=TA_CENTER,
    )
    subtitle = ParagraphStyle(
        "subtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, leading=14, alignment=TA_CENTER, textColor="#444444",
    )
    rubric = ParagraphStyle(
        "rubric", parent=styles["Normal"], fontName="Helvetica-Oblique",
        fontSize=9.5, leading=13, textColor="#444444",
    )
    question = ParagraphStyle(
        "question", parent=styles["Normal"], fontName="Helvetica",
        fontSize=11, leading=15.5, spaceAfter=9,
        leftIndent=13 * mm, firstLineIndent=-13 * mm,
    )

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Class 10 Biology — Unit Test",
        author="VedaAI assignment test fixture",
    )

    story: list = [
        Paragraph("DELHI PUBLIC SCHOOL, BOKARO STEEL CITY", subtitle),
        Spacer(1, 4),
        Paragraph("Class 10 Biology — Unit Test", title),
        Spacer(1, 3),
        Paragraph("Time: 1 hour 30 minutes&nbsp;&nbsp;|&nbsp;&nbsp;"
                  f"Maximum Marks: {sum(q[3] for q in QUESTIONS)}", subtitle),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.7, color="#999999"),
        Spacer(1, 9),
        Paragraph(
            "General instructions: All questions are compulsory. Marks for "
            "each question are shown in brackets. Write the question number "
            "clearly before each answer. Draw diagrams neatly in pencil.",
            rubric,
        ),
        Spacer(1, 12),
    ]

    for i, (number, part, text, marks) in enumerate(QUESTIONS):
        label = f"{number} ({part})" if part else f"{number}."
        story.append(
            Paragraph(f"<b>{label}</b>&nbsp;&nbsp;{text} <b>[{marks}]</b>",
                      question)
        )
        # Break so the sub-part questions land on page two, which gives the
        # answer sheet a natural reason to run across pages too.
        if i == 8:
            story.append(PageBreak())

    doc.build(story)
    return OUT


if __name__ == "__main__":
    path = build()
    total = sum(q[3] for q in QUESTIONS)
    print(f"wrote {path}")
    print(f"{len(QUESTIONS)} questions, {total} marks")
