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

# A label-matched answer whose words have essentially nothing to do with the
# question it was filed under, when some *unanswered* question matches it
# strongly, is a misread digit rather than a student writing nonsense. The
# gap has to be stark before we overrule what the student appears to have
# written: a correct short answer can legitimately share no words with its
# question ("Expand RAM." / "Random Access Memory"), so a low score on its
# own proves nothing — only a low score *beside* a strong rival does.
REPAIR_HERE_MAX = 0.05
REPAIR_RIVAL_MIN = 0.25

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
    # A label can name more than one question: an internal choice prints
    # "13 ... OR 13 ...", so both branches live under the key "13|".
    by_key: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        by_key[labels.key(q.number, q.part)].append(q)
    taken: dict[str, AnswerBlock] = {}

    blocks = _merge_same_label(blocks)
    numbers_on_paper = {q.number for q in questions}

    # Blocks the student labelled with a question the paper does not contain.
    # These are held back from the content and adjudication rungs below: the
    # label is an instruction, and "Q14" on a paper that stops at 13 is the
    # student telling us this answers nothing here. Letting word overlap
    # reassign it is how an answer written for Q14 ends up marked as Q13 —
    # which is exactly the "answers that match no question" case, silently got
    # wrong. Only an explicit written label counts; a number parsed out of the
    # opening words of a sentence is too easy to get wrong to pin on.
    orphaned: set[str] = set()

    # --- 1 & 2: the student told us. -------------------------------------
    for block in blocks:
        number, part = labels.parse(block.label)
        method = "label"
        if number is not None and number not in numbers_on_paper:
            orphaned.add(block.id)
            continue
        if number is None:
            number, part = labels.parse_leading(block.text)
            method = "label"
        if number is None:
            continue

        question = _resolve(by_key, questions, number, part, taken, block.text)
        if question is None:
            continue

        # Not every "label" match is worth the same. A number the student
        # actually wrote beside the answer is near-certain. A number carried
        # down from an earlier answer — the student wrote "4. (i)" and then
        # just "(ii)" — is an inference from writing order, and it is wrong
        # wherever the run of sub-parts was misread. Showing both as 97% told
        # the teacher the system was certain in precisely the places it was
        # guessing.
        inherited = block.__dict__.get("_inherited_number")
        if inherited:
            _assign(block, question, taken, "inherited", 0.82)
        else:
            _assign(block, question, taken, method, 0.97)

    _repair_misread_labels(questions, taken, blocks)

    # --- 3: content similarity for whatever is left. ----------------------
    free_blocks = [
        b for b in blocks
        if b.matched_question_id is None and b.id not in orphaned
    ]
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
    free_blocks = [
        b for b in blocks
        if b.matched_question_id is None and b.id not in orphaned
    ]
    free_questions = [q for q in questions if q.id not in taken]
    if free_blocks and free_questions and len(free_blocks) <= ADJUDICATE_LIMIT:
        try:
            _adjudicate(free_blocks, free_questions, taken)
        except Exception as exc:  # noqa: BLE001 - never fatal
            log.warning("adjudication pass failed: %s", exc)

    # --- 5: an entirely unlabelled sheet answered in order. ---------------
    free_blocks = [
        b for b in blocks
        if b.matched_question_id is None and b.id not in orphaned
    ]
    # "inherited" counts as labelled here: the sheet did carry numbers, we just
    # had to carry them down onto the sub-parts. Reading position off a sheet
    # that is in fact numbered would be the wrong fallback entirely.
    labelled = {"label", "inherited"}
    if free_blocks and not any(b.match_method in labelled for b in blocks):
        free_questions = [q for q in questions if q.id not in taken]
        if len(free_blocks) == len(free_questions) and free_questions:
            warnings.append(
                "No answer on the sheet carried a question number, so answers "
                "were matched to questions in the order they were written."
            )
            for block, question in zip(free_blocks, free_questions):
                _assign(block, question, taken, "sequential", 0.4)

    _attach(questions, taken)
    _resolve_choices(questions, warnings)
    unmatched = [b for b in blocks if b.matched_question_id is None]

    if unmatched:
        shown = ", ".join(b.label for b in unmatched if b.label) or "unlabelled"
        warnings.append(
            f"{len(unmatched)} answer(s) did not correspond to any question on "
            f"the paper ({shown})."
        )

    named = [b.label for b in unmatched if b.id in orphaned and b.label]
    if named:
        warnings.append(
            f"{len(named)} answer(s) are labelled with a question number the "
            f"paper does not contain ({', '.join(named)}). They were left "
            "unmatched rather than reassigned, because the label is the "
            "student's own."
        )
    return questions, unmatched, warnings



def _repair_misread_labels(
    questions: list[Question],
    taken: dict[str, AnswerBlock],
    blocks: list[AnswerBlock],
) -> None:
    """Move an answer whose label points somewhere its words plainly do not.

    The label rung trusts the number the student wrote, which is right almost
    always — but the number is read off handwriting, and a misread digit files
    a correct answer under the wrong question *and* reports the right one as
    blank. On the sample sheet a "8" read as "7" put the normalization answer
    on "compiler vs interpreter" and left normalization looking unattempted:
    two questions wrong from one character.

    So a label match is overruled only when the evidence is one-sided: the
    answer shares essentially nothing with the question it landed on, and
    shares a lot with one that is still unanswered.
    """
    free = [q for q in questions if q.id not in taken]
    if not free:
        return

    corpus = [q.text for q in questions] + [b.text for b in blocks]
    idf = _idf(corpus)

    for question in list(questions):
        block = taken.get(question.id)
        if block is None or block.match_method not in ("label", "inherited"):
            continue

        tokens = _tokens(block.text)
        here = _similarity(tokens, _tokens(question.text), idf)
        if here > REPAIR_HERE_MAX:
            continue

        rival, best = None, 0.0
        for candidate in free:
            if candidate.id in taken:
                continue
            score = _similarity(tokens, _tokens(candidate.text), idf)
            if score > best:
                rival, best = candidate, score

        if rival is None or best < REPAIR_RIVAL_MIN:
            continue

        log.info(
            "repairing %s -> %s (label match scored %.3f, %s scores %.3f)",
            labels.display(question.number, question.part),
            labels.display(rival.number, rival.part),
            here,
            labels.display(rival.number, rival.part),
            best,
        )
        del taken[question.id]
        block.matched_question_id = None
        # Confidence drops: the number the student wrote said otherwise, and we
        # are trusting the words over their own label.
        _assign(block, rival, taken, "semantic", round(min(0.8, best), 3))
        free = [q for q in questions if q.id not in taken]


def _resolve(
    by_key: dict[str, list[Question]],
    questions: list[Question],
    number: str,
    part: str | None,
    taken: dict[str, AnswerBlock],
    text: str = "",
) -> Question | None:
    """Find the question a parsed label refers to, tolerating a missing part."""
    branches = [q for q in by_key.get(labels.key(number, part), [])]
    free = [q for q in branches if q.id not in taken]

    if len(free) == 1:
        return free[0]
    if len(free) > 1:
        # An internal choice: the label says "13" but the paper printed two.
        # Which one the student answered is only knowable from what they
        # wrote, and word overlap is the wrong instrument for it — an answer
        # that compares itself to the other branch borrows that branch's
        # vocabulary. On the sample paper the TCP/IP answer says "four layers
        # instead of seven", so "layers" and "seven" pushed it onto the OSI
        # question by 0.25 to 0.22. Which question an answer *answers* is a
        # judgement, so it is asked as one, with overlap kept as the fallback.
        return _pick_branch(text, free)
    if branches:
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



def _pick_branch(text: str, branches: list[Question]) -> Question | None:
    """Choose which alternative of an internal choice an answer addresses.

    One request, and only when a paper actually prints a choice and a student
    actually answers it — so on a paper with no "OR" this never runs.
    """
    payload = [
        {"index": i, "question": q.text}
        for i, q in enumerate(branches)
    ]
    prompt = (
        "An exam offered a choice: the questions below are alternatives "
        "printed under the same number, and the student answered exactly one "
        "of them.\n"
        "Decide which one this answer is an answer TO. Judge what the answer "
        "sets out to explain, not which words it happens to share — an answer "
        "may mention the other alternative in order to compare itself against "
        "it, and that is not the question it is answering.\n"
        'Return JSON: {"index": integer}\n\n'
        f"ANSWER:\n{text[:1500]}\n\nALTERNATIVES:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        data = gemini.generate_json(prompt, temperature=0.0)
        index = int(data.get("index")) if isinstance(data, dict) else -1
        if 0 <= index < len(branches):
            log.info("choice branch %s picked by adjudication", index)
            return branches[index]
    except Exception as exc:  # noqa: BLE001 - never fatal, fall back below
        log.warning("branch adjudication failed, falling back to overlap: %s", exc)

    tokens = _tokens(text)
    idf = _idf([q.text for q in branches] + [text])
    return max(branches, key=lambda q: _similarity(tokens, _tokens(q.text), idf))


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


def _resolve_choices(questions: list[Question], warnings: list[str]) -> None:
    """Mark the branches of an internal choice the student did not take.

    A paper printing "13 ... OR 13 ..." expects one answer, not two, so the
    branch left blank is not a question the student failed to attempt — it is
    one they were never meant to answer. Reporting it as `unanswered` would
    put it in the teacher's list of omissions and, worse, count its marks
    against the total: the sample paper is out of 40, and summing both
    branches of 13 reports 45.
    """
    groups: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        if q.choice_group:
            groups[q.choice_group].append(q)

    for group, branches in groups.items():
        if not any(q.status == "answered" for q in branches):
            continue  # neither attempted — both stay genuinely unanswered
        skipped = [q for q in branches if q.status != "answered"]
        for q in skipped:
            q.status = "not_chosen"
        if skipped:
            number = skipped[0].number
            warnings.append(
                f"Question {number} offered a choice; the student answered one "
                f"branch, so the other is not counted as unanswered and its "
                f"marks are excluded from the total."
            )


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
