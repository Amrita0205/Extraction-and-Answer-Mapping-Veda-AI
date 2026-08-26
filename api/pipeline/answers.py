"""Extract the student's answers, with the region each one occupies.

The region is the whole point: the teacher clicks a question and the exact
patch of the answer sheet lights up. Two things make that work.

First, we ask for one *block* per answer rather than per line — a block is the
run of writing that belongs to one question, including any diagram. Line-level
boxes would need reassembling and the seams show.

Second, the model's box is treated as a proposal, not an answer. `tighten.py`
snaps it to the actual ink. Vision models are reliably good at "the answer to
Q3 is roughly here" and unreliably good at the last few percent of an edge.
"""

from __future__ import annotations

import logging
from typing import Callable

from . import gemini, labels
from .render import RenderedPage
from .schemas import AnswerBlock, Region
from .tighten import tighten

log = logging.getLogger(__name__)

_PROMPT = """
This image is page {index} of a student's handwritten answer sheet.

Find every distinct answer the student has written on THIS page.

An "answer block" is one contiguous run of writing that answers a single
question — including any diagram, working, or equation that belongs to it.
Do not split an answer into separate lines. Do not merge two different answers
into one block.

For each block report:
- `label`: exactly what the student wrote to identify it, verbatim
  ("Q2.", "11 b)", "Ans 5"). Use null if the block carries no visible label.
- `text`: a faithful transcription of the handwriting. Transcribe what is
  actually written, including mistakes; do not correct or complete it. For a
  diagram, transcribe any labels and add a short bracketed note such as
  "[diagram of a nephron]".
- `box_2d`: the bounding box of the block as [ymin, xmin, ymax, xmax],
  normalised to 0-1000. Include the student's own label in the box. Do NOT
  include the printed ruling of the page, the margin line, or empty space
  below the last line of writing.
- `continues_from_previous_page`: true if this block is the tail of an answer
  that began on an earlier page (it starts mid-sentence, or has no label and
  sits at the very top of the page).
- `continues_on_next_page`: true if the writing runs to the bottom edge and is
  clearly unfinished.

Ignore anything that is not the student answering a question: their name, roll
number, date, page numbers, the school header, and the subject title or paper
code written at the top of the booklet ("Hindi Core (302)", "Physics 042").
A subject title is not an answer even though it is handwritten and sits where
an answer would.

Return JSON: {{"blocks": [{{"label": string|null, "text": string,
"box_2d": [number, number, number, number],
"continues_from_previous_page": boolean,
"continues_on_next_page": boolean}}]}}
"""


def extract(
    pages: list[RenderedPage],
    check: Callable[[], None] | None = None,
) -> tuple[list[AnswerBlock], list[str]]:
    warnings: list[str] = []
    per_page: list[list[dict]] = []

    for page in pages:
        if check is not None:
            check()
        try:
            data = gemini.generate_json(
                _PROMPT.format(index=page.index), images=[page.path]
            )
        except Exception as exc:  # noqa: BLE001
            log.error("answer extraction failed on page %s: %s", page.index, exc)
            warnings.append(
                f"Page {page.index + 1} of the answer sheet could not be read; "
                "answers on it were skipped."
            )
            per_page.append([])
            continue

        blocks = data.get("blocks") if isinstance(data, dict) else data
        per_page.append([b for b in (blocks or []) if isinstance(b, dict)])

    raw = _inherit_numbers(_to_blocks(per_page, pages))
    merged = _merge_continuations(raw)
    log.info("extracted %s answer blocks (%s before merge)", len(merged), len(raw))
    return merged, warnings


def _to_blocks(
    per_page: list[list[dict]], pages: list[RenderedPage]
) -> list[AnswerBlock]:
    out: list[AnswerBlock] = []
    for page, items in zip(pages, per_page):
        for item in items:
            box = gemini.box_to_fractions(item.get("box_2d"))
            if box is None:
                # A block we cannot place is still worth keeping for mapping —
                # it just cannot be highlighted. Give it the full page.
                box = (0.04, 0.04, 0.96, 0.96)

            x0, y0, x1, y1 = tighten(page.path, box)
            label = item.get("label")
            label = str(label).strip() if label else None

            out.append(
                AnswerBlock(
                    id=f"a_{page.index}_{len(out)}",
                    label=label,
                    text=" ".join(str(item.get("text") or "").split()),
                    regions=[Region(page=page.index, x0=x0, y0=y0, x1=x1, y1=y1)],
                )
            )
            out[-1].__dict__["_continues_from"] = bool(
                item.get("continues_from_previous_page")
            )
            out[-1].__dict__["_continues_on"] = bool(
                item.get("continues_on_next_page")
            )
    return out


def _inherit_numbers(blocks: list[AnswerBlock]) -> list[AnswerBlock]:
    """Give a bare sub-part the question number of the answer above it.

    A student writes "4. (i)" once and then just "(ii)", "(iii)" underneath. On
    its own, "(ii)" matches nothing — it has no number for the label rung of the
    ladder to compare. Carrying the last full number forward is what turns most
    of a booklet from unmatched into matched, so it is done before mapping and
    before continuation merging, while blocks are still in reading order.
    """
    last_number: str | None = None
    for block in blocks:
        number, _ = labels.parse_leading(block.label)
        if number:
            last_number = number
            continue

        part = labels.bare_part(block.label)
        if part and last_number:
            block.label = f"{last_number} ({part})"
            # Worth recording: an inherited label is a weaker signal than one
            # the student actually wrote, and the mapper may want to say so.
            block.__dict__["_inherited_number"] = True
    return blocks


def _merge_continuations(blocks: list[AnswerBlock]) -> list[AnswerBlock]:
    """Join an answer that runs off the bottom of one page onto the next.

    Two signals agree or we don't merge: the earlier block says it continues,
    or the later block says it is a continuation — and the later block either
    carries no label of its own or carries the same one.
    """
    merged: list[AnswerBlock] = []
    for block in blocks:
        prev = merged[-1] if merged else None
        if prev is not None and _should_merge(prev, block):
            prev.text = f"{prev.text} {block.text}".strip()
            prev.regions.extend(block.regions)
            prev.__dict__["_continues_on"] = block.__dict__.get(
                "_continues_on", False
            )
            continue
        merged.append(block)
    return merged


def _should_merge(prev: AnswerBlock, block: AnswerBlock) -> bool:
    prev_page = prev.regions[-1].page if prev.regions else -1
    this_page = block.regions[0].page if block.regions else -1
    if this_page != prev_page + 1:
        return False

    says_continues = prev.__dict__.get("_continues_on") or block.__dict__.get(
        "_continues_from"
    )
    if not says_continues:
        return False

    prev_number, prev_part = labels.parse(prev.label)
    this_number, this_part = labels.parse(block.label)
    if this_number is None:
        return True  # unlabelled tail — the common case
    return (this_number, this_part) == (prev_number, prev_part)
