"""Extract every question from the question paper, in printed order.

Papers usually arrive as a PDF with a real text layer, and that layer is the
best available source for the *wording* of a question — it carries no OCR
error. It is a poor source for the paper's *structure*: PDF text extraction
routinely drops inter-word spaces and renders sub-part markers like "(i)" as
replacement glyphs, which is near-certain for Indic scripts. Losing those
markers is expensive, because they are what the answer sheet is matched on.

So each page goes to the model as an image *and* as its text layer, with the
model told to read structure off the image and wording off the text. Papers run
to a page or three, so the extra vision calls are cheap.
"""

from __future__ import annotations

import logging

from . import gemini, labels
from .render import RenderedPage
from .schemas import Question

log = logging.getLogger(__name__)

_RULES = """
Rules that matter:
- Extract EVERY question, including ones that continue across a page break.
- Preserve the printed numbering exactly as it appears. Do not renumber.
- A labelled sub-part is its own entry: "11 (a)" and "11 (b)" are TWO entries,
  each with number "11" and part "a" / "b". Put the shared stem, if any, on the
  first sub-part only; never duplicate it across sub-parts.
- Roman-numeral sub-parts ("(i)", "(ii)") keep their roman form in `part`.
- `marks` is the mark allocation printed for that question (often "[3]" or
  "(3 marks)"). Use null when the paper does not print one.
- Ignore headers, footers, page numbers, instructions ("Answer all questions"),
  section titles, and the rubric. Those are not questions.
- `text` is the question as printed, whitespace tidied, without its number.
- Return entries in printed order, first question first.
"""

_SCHEMA = """
Return JSON: {"questions": [{"number": string, "part": string|null,
"text": string, "marks": number|null, "page": integer}]}
"""


def extract(pages: list[RenderedPage]) -> tuple[list[Question], list[str]]:
    warnings: list[str] = []

    raw = _from_pages(pages)
    log.info("extracted %s question candidates", len(raw))

    questions = _normalise(raw, warnings)
    if not questions:
        warnings.append(
            "No questions were extracted from the question paper. "
            "Check that the upload is the paper and not a blank scan."
        )
    return questions, warnings


_TEXT_LAYER_NOTE = """
The PDF's own text layer for this page is quoted below. It is usually faithful
for wording, but it is not trustworthy for structure: extractors routinely drop
the spaces between words and replace sub-part markers such as "(i)" with a
replacement glyph, and this is close to guaranteed for Indic scripts. So read
the NUMBERING, SUB-PART LABELS and MARKS off the image, and use the text layer
only to confirm the wording of a question you can already see.
"""


def _from_pages(pages: list[RenderedPage]) -> list[dict]:
    """Read each page as an image, with its text layer alongside when it has one.

    Question papers run to a page or three, so paying for vision on all of them
    is cheap, and it is the only way to recover sub-part labels that the text
    layer has mangled. One page per call: page indices drift when several pages
    share a request.
    """
    out: list[dict] = []
    for page in pages:
        text = (page.text_layer or "").strip()
        prompt = (
            "This image is page "
            f"{page.index} of an exam question paper. Identify every question "
            "printed on THIS page.\n"
        )
        if text:
            prompt += f"{_TEXT_LAYER_NOTE}--- TEXT LAYER ---\n{text}\n--- END ---\n"
        prompt += (
            f"{_RULES}\n{_SCHEMA}\n"
            f"Set `page` to {page.index} on every entry."
        )
        try:
            data = gemini.generate_json(prompt, images=[page.path])
        except Exception as exc:  # noqa: BLE001
            log.error("question extraction failed on page %s: %s", page.index, exc)
            continue
        for item in _unwrap(data):
            item.setdefault("page", page.index)
            out.append(item)
    return out


def _unwrap(data) -> list[dict]:
    if isinstance(data, dict):
        for k in ("questions", "items", "result", "data"):
            if isinstance(data.get(k), list):
                return [d for d in data[k] if isinstance(d, dict)]
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def _normalise(raw: list[dict], warnings: list[str]) -> list[Question]:
    seen: dict[str, Question] = {}
    order: list[str] = []

    for item in raw:
        number = str(item.get("number") or "").strip()
        part = item.get("part")
        # Models hand back the sub-part as the paper prints it — "(i)", "i.",
        # "[b]". Strip it to bare "i" / "b" so it compares equal to a part
        # parsed off a student's answer, and so `display` can re-add brackets.
        part = labels.clean_part(str(part)) or None if part else None

        # The model sometimes packs the sub-part into `number` ("11(b)").
        if not part or not number.isdigit():
            parsed_number, parsed_part = labels.parse(number)
            if parsed_number:
                number, part = parsed_number, parsed_part or part
        if not number:
            continue

        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue

        marks = item.get("marks")
        try:
            marks = float(marks) if marks is not None else None
        except (TypeError, ValueError):
            marks = None

        k = labels.key(number, part)
        if k in seen:
            # Duplicate label — usually the same question caught twice at a
            # page boundary. Keep the longer text, it is the more complete read.
            if len(text) > len(seen[k].text):
                seen[k].text = text
            continue

        seen[k] = Question(
            id=f"q_{k.replace('|', '_').rstrip('_')}",
            number=number,
            part=part,
            text=text,
            marks=marks,
            order=len(order),
        )
        order.append(k)

    questions = [seen[k] for k in order]

    # The model returns printed order; sorting by parsed number is a safety net
    # for papers whose text layer streams out of visual order (two-column
    # layouts do this). We only re-sort when it disagrees badly, so a paper
    # that deliberately prints 5 before 4 is left alone.
    by_number = sorted(questions, key=lambda q: labels.sort_key(q.number, q.part))
    if _inversions(questions) > len(questions) * 0.25:
        warnings.append(
            "Question order from the paper looked scrambled, so it was sorted "
            "by printed number."
        )
        questions = by_number

    for i, q in enumerate(questions):
        q.order = i
    return questions


def _inversions(questions: list[Question]) -> int:
    keys = [labels.sort_key(q.number, q.part) for q in questions]
    return sum(
        1
        for i in range(len(keys) - 1)
        if keys[i] > keys[i + 1]
    )
