"""Decide which answer belongs to which question.

The brief asks for three awkward cases to work: answers written out of order,
questions left unanswered, and answers that match nothing. A single semantic
similarity pass handles none of them well. What does work is a ladder, in
descending order of how much the evidence is worth:

1.  The student wrote a label. "Q11(b)" is not a hint, it is an instruction,
    and it is order-independent by construction — which is most of what
    "handle questions answered out of order" actually needs.
2.  The label is embedded in the first words of the transcription.
3.  Nothing labelled it, so fall back to content: IDF-weighted overlap between
    the answer text and each remaining question, greedily assigned.
4.  Still ambiguous, and few enough to be worth a request: ask the model to
    adjudicate the shortlist.
5.  Nothing anywhere: leave it unmatched and say so, rather than forcing it
    onto the nearest free question.

Anything still unassigned at the end is reported as an unmatched answer, and
any question with nothing assigned is reported as unanswered. Neither is an
error — both are outcomes the teacher needs to see.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import defaultdict

from . import gemini, labels
from .schemas import Answer, AnswerBlock, Question

log = logging.getLogger(__name__)

SEMANTIC_FLOOR = 0.13  # below this, "matched" is indistinguishable from noise
ADJUDICATE_LIMIT = 12  # cap the extra request so a messy sheet stays cheap

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was",
    "what", "which", "with", "you", "your", "state", "give", "write", "name",
    "explain", "describe", "define", "draw", "list", "mention", "briefly",
    "following", "question", "answer", "marks", "mark", "using", "show",
}
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {
        w for w in _WORD.findall((text or "").lower())
        if len(w) > 2 and w not in _STOP
    }


def map_answers(
    questions: list[Question], blocks: list[AnswerBlock]
) -> tuple[list[Question], list[AnswerBlock], list[str]]:
    warnings: list[str] = []
    by_key = {labels.key(q.number, q.part): q for q in questions}
    taken: dict[str, AnswerBlock] = {}

    blocks = _merge_same_label(blocks)

    # --- 1 & 2: the student told us. -------------------------------------
    for block in blocks:
        number, part = labels.parse(block.label)
        method = "label"
        if number is None:
            number, part = labels.parse_leading(block.text)
            method = "label"
        if number is None:
            continue

        question = _resolve(by_key, questions, number, part, taken)
        if question is None:
            continue
        _assign(block, question, taken, method, 0.97)

    # --- 3: content similarity for whatever is left. ----------------------
    free_blocks = [b for b in blocks if b.matched_question_id is None]
    free_questions = [q for q in questions if q.id not in taken]

    if free_blocks and free_questions:
        idf = _idf([q.text for q in free_questions] + [b.text for b in free_blocks])
        scored: list[tuple[float, AnswerBlock, Question]] = []
        for block in free_blocks:
            bt = _tokens(block.text)
            for question in free_questions:
                score = _similarity(bt, _tokens(question.text), idf)
                if score >= SEMANTIC_FLOOR:
                    scored.append((score, block, question))

        scored.sort(key=lambda t: -t[0])
        for score, block, question in scored:
            if block.matched_question_id or question.id in taken:
                continue
            _assign(block, question, taken, "semantic", round(min(0.92, score), 3))

    # --- 4: ask the model about what is still floating. -------------------
    free_blocks = [b for b in blocks if b.matched_question_id is None]
    free_questions = [q for q in questions if q.id not in taken]
    if free_blocks and free_questions and len(free_blocks) <= ADJUDICATE_LIMIT:
        try:
            _adjudicate(free_blocks, free_questions, taken)
        except Exception as exc:  # noqa: BLE001 - never fatal
            log.warning("adjudication pass failed: %s", exc)

    # --- 5: an entirely unlabelled sheet answered in order. ---------------
    free_blocks = [b for b in blocks if b.matched_question_id is None]
    if free_blocks and not any(b.match_method == "label" for b in blocks):
        free_questions = [q for q in questions if q.id not in taken]
        if len(free_blocks) == len(free_questions) and free_questions:
            warnings.append(
                "No answer on the sheet carried a question number, so answers "
                "were matched to questions in the order they were written."
            )
            for block, question in zip(free_blocks, free_questions):
                _assign(block, question, taken, "sequential", 0.4)

    _attach(questions, taken)
    unmatched = [b for b in blocks if b.matched_question_id is None]

    if unmatched:
        shown = ", ".join(b.label for b in unmatched if b.label) or "unlabelled"
        warnings.append(
            f"{len(unmatched)} answer(s) did not correspond to any question on "
            f"the paper ({shown})."
        )
    return questions, unmatched, warnings


def _resolve(
    by_key: dict[str, Question],
    questions: list[Question],
    number: str,
    part: str | None,
    taken: dict[str, AnswerBlock],
) -> Question | None:
    """Find the question a parsed label refers to, tolerating a missing part."""
    exact = by_key.get(labels.key(number, part))
    if exact is not None and exact.id not in taken:
        return exact
    if exact is not None:
        return None  # already answered; caller leaves the block unmatched

    if part is None:
        # Student wrote "11" on a paper that prints 11(a) and 11(b): give it to
        # the first sub-part still free, which is what writing order implies.
        siblings = [
            q for q in questions
            if q.number == number and q.id not in taken
        ]
        if siblings:
            return sorted(siblings, key=lambda q: labels.sort_key(q.number, q.part))[0]
    return None


def _assign(
    block: AnswerBlock,
    question: Question,
    taken: dict[str, AnswerBlock],
    method: str,
    confidence: float,
) -> None:
    block.matched_question_id = question.id
    block.match_method = method  # type: ignore[assignment]
    block.confidence = confidence
    taken[question.id] = block


def _merge_same_label(blocks: list[AnswerBlock]) -> list[AnswerBlock]:
    """Fold blocks carrying the same label into one multi-region answer.

    Covers the student who answers Q3, moves on, then comes back three pages
    later to add to it — which the brief's "answers may span multiple pages"
    requirement includes and page-adjacency merging alone would miss.
    """
    first: dict[str, AnswerBlock] = {}
    out: list[AnswerBlock] = []
    for block in blocks:
        number, part = labels.parse(block.label)
        if number is None:
            out.append(block)
            continue
        k = labels.key(number, part)
        if k in first:
            head = first[k]
            head.text = f"{head.text} {block.text}".strip()
            head.regions.extend(block.regions)
            continue
        first[k] = block
        out.append(block)
    return out


def _idf(corpus: list[str]) -> dict[str, float]:
    docs = [_tokens(t) for t in corpus if t]
    n = max(1, len(docs))
    freq: dict[str, int] = defaultdict(int)
    for doc in docs:
        for token in doc:
            freq[token] += 1
    return {t: math.log(1 + n / (1 + c)) for t, c in freq.items()}


def _similarity(a: set[str], b: set[str], idf: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = a & b
    if not shared:
        return 0.0
    num = sum(idf.get(t, 1.0) for t in shared)
    den = math.sqrt(sum(idf.get(t, 1.0) for t in a)) * math.sqrt(
        sum(idf.get(t, 1.0) for t in b)
    )
    return num / den if den else 0.0


def _adjudicate(
    blocks: list[AnswerBlock],
    questions: list[Question],
    taken: dict[str, AnswerBlock],
) -> None:
    payload = {
        "questions": [
            {
                "id": q.id,
                "label": labels.display(q.number, q.part),
                "text": q.text[:400],
            }
            for q in questions
        ],
        "answers": [
            {"id": b.id, "label": b.label, "text": b.text[:600]} for b in blocks
        ],
    }
    prompt = (
        "Each answer below was written by a student but carries no usable "
        "question number. Decide which question, if any, each one answers.\n"
        "Only match when the content genuinely addresses the question. It is "
        "correct and expected to return null for an answer that matches "
        "nothing — do not force a match to use up the list.\n"
        "Each question may be used at most once.\n"
        'Return JSON: {"matches": [{"answer_id": string, '
        '"question_id": string|null, "confidence": number}]}\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )
    data = gemini.generate_json(prompt, thinking_budget=None)
    matches = data.get("matches", []) if isinstance(data, dict) else []

    by_block = {b.id: b for b in blocks}
    by_question = {q.id: q for q in questions}
    for match in matches:
        if not isinstance(match, dict):
            continue
        block = by_block.get(match.get("answer_id"))
        question = by_question.get(match.get("question_id"))
        if block is None or question is None:
            continue
        if block.matched_question_id or question.id in taken:
            continue
        try:
            confidence = float(match.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        if confidence < 0.35:
            continue
        _assign(block, question, taken, "semantic", round(min(0.9, confidence), 3))


def _attach(questions: list[Question], taken: dict[str, AnswerBlock]) -> None:
    for question in questions:
        block = taken.get(question.id)
        if block is None:
            question.status = "unanswered"
            question.answer = None
            continue
        regions = sorted(block.regions, key=lambda r: (r.page, r.y0))
        question.status = "answered"
        question.answer = Answer(
            id=block.id,
            text=block.text,
            regions=regions,
            confidence=block.confidence,
            match_method=block.match_method,
            spans_pages=len({r.page for r in regions}) > 1,
        )
