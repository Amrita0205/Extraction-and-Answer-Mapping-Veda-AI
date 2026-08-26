"""Grade the answers that were matched, and write the summary.

Grading runs last and fails soft on purpose. It is the one stage the brief
lists as optional ("This can include grading"), and it is the stage most likely
to hit a free-tier rate limit, so a failure here downgrades every question to
`ungraded` and leaves extraction, mapping and highlighting untouched.

Unanswered questions are scored zero without a request — there is nothing to
send — but they are marked `ungraded` rather than `incorrect`, because a blank
page and a wrong answer are different things and a teacher reading the summary
needs to see which is which.
"""

from __future__ import annotations

import json
import logging

from . import gemini, labels
from .schemas import AnswerBlock, Grade, Question, Summary

log = logging.getLogger(__name__)

BATCH = 8  # questions per request — small enough to stay well inside limits
DEFAULT_MARKS = 2.0


def grade(questions: list[Question]) -> tuple[bool, str, list[str]]:
    """Attach a `Grade` to every question. Returns (graded, overall, warnings)."""
    warnings: list[str] = []
    answered = [q for q in questions if q.status == "answered" and q.answer]

    for question in questions:
        if question.status != "answered":
            question.grade = Grade(
                awarded=0.0,
                max=question.marks or DEFAULT_MARKS,
                verdict="ungraded",
                feedback="This question was left unanswered.",
            )

    if not answered:
        return False, "", warnings

    graded_any = False
    for start in range(0, len(answered), BATCH):
        batch = answered[start : start + BATCH]
        try:
            _grade_batch(batch)
            graded_any = True
        except Exception as exc:  # noqa: BLE001
            log.error("grading batch %s failed: %s", start // BATCH, exc)
            for question in batch:
                question.grade = Grade(
                    awarded=0.0,
                    max=question.marks or DEFAULT_MARKS,
                    verdict="ungraded",
                    feedback="Grading was unavailable for this question.",
                )

    if not graded_any:
        warnings.append(
            "Answers were extracted and mapped, but grading was unavailable. "
            "Scores are shown as ungraded."
        )
        return False, "", warnings

    # An answer that does not address its question is usually a mapping
    # failure wearing a mark of zero. Surfacing it separately tells the teacher
    # to re-check the pairing rather than the pupil — and on a paper whose
    # numbering does not line up with the booklet, this is most of the story.
    mismatched = [
        labels.display(q.number, q.part)
        for q in answered
        if q.grade is not None and not q.grade.addresses_question
    ]
    if mismatched:
        warnings.append(
            f"{len(mismatched)} answer(s) were matched to a question they do "
            f"not appear to address ({', '.join(mismatched)}). The pairing is "
            "worth checking before the mark is."
        )

    overall = ""
    try:
        overall = _overall(answered)
    except Exception as exc:  # noqa: BLE001
        log.warning("overall feedback failed: %s", exc)

    return True, overall, warnings


def _grade_batch(batch: list[Question]) -> None:
    payload = [
        {
            "id": q.id,
            "label": labels.display(q.number, q.part),
            "question": q.text,
            "max_marks": q.marks or DEFAULT_MARKS,
            "student_answer": (q.answer.text if q.answer else ""),
        }
        for q in batch
    ]
    prompt = (
        "You are marking a school exam. For each item, award marks out of "
        "`max_marks` and write one or two sentences of feedback addressed to "
        "the student.\n"
        "Guidance:\n"
        "- These pairings were made automatically, usually from the number the "
        "  student wrote beside their answer, so a pairing CAN be wrong. Judge "
        "  the answer against the question as printed. If the answer plainly "
        "  does not address that question — it answers something else, or it "
        "  is a multiple-choice option for a question that asks for an "
        "  explanation — award 0, set `addresses_question` false, and say so "
        "  plainly. Do NOT reinterpret the question to fit the answer, and do "
        "  not praise an answer for something the question did not ask.\n"
        "- The answer is a transcription of handwriting, so ignore spelling "
        "  and transcription noise. Mark the understanding, not the neatness.\n"
        "- Award partial marks where part of the answer is right.\n"
        "- `verdict` is 'correct' at full marks, 'incorrect' at zero, and "
        "  'partial' in between.\n"
        "- Feedback should say what earned the marks and what was missing. Be "
        "  specific and kind; never sarcastic.\n"
        'Return JSON: {"grades": [{"id": string, "awarded": number, '
        '"verdict": "correct"|"partial"|"incorrect", '
        '"addresses_question": boolean, "feedback": string}]}\n\n'
        + json.dumps(payload, ensure_ascii=False)
    )
    # Marking benefits from a little deliberation, unlike extraction.
    data = gemini.generate_json(prompt, temperature=0.1, thinking_budget=None)
    grades = data.get("grades", []) if isinstance(data, dict) else data or []

    by_id = {q.id: q for q in batch}
    for item in grades:
        if not isinstance(item, dict):
            continue
        question = by_id.get(item.get("id"))
        if question is None:
            continue
        maximum = question.marks or DEFAULT_MARKS
        try:
            awarded = float(item.get("awarded", 0))
        except (TypeError, ValueError):
            awarded = 0.0
        awarded = max(0.0, min(maximum, awarded))

        verdict = item.get("verdict")
        if verdict not in ("correct", "partial", "incorrect"):
            verdict = (
                "correct" if awarded >= maximum
                else "incorrect" if awarded <= 0
                else "partial"
            )
        question.grade = Grade(
            awarded=round(awarded, 2),
            max=maximum,
            verdict=verdict,
            feedback=str(item.get("feedback") or "").strip(),
            addresses_question=bool(item.get("addresses_question", True)),
        )

    for question in batch:
        if question.grade is None:
            question.grade = Grade(
                awarded=0.0,
                max=question.marks or DEFAULT_MARKS,
                verdict="ungraded",
                feedback="Grading did not return a result for this question.",
            )


def _overall(answered: list[Question]) -> str:
    lines = [
        f"{labels.display(q.number, q.part)}: "
        f"{q.grade.awarded}/{q.grade.max} — {q.grade.feedback}"
        for q in answered
        if q.grade
    ]
    prompt = (
        "Here is a marked exam, question by question. Write two or three "
        "sentences of overall feedback for the student: what they did well, "
        "and the single most useful thing to work on next. Address the "
        "student directly.\n"
        'Return JSON: {"feedback": string}\n\n' + "\n".join(lines)
    )
    data = gemini.generate_json(prompt, temperature=0.3, thinking_budget=None)
    if isinstance(data, dict):
        return str(data.get("feedback") or "").strip()
    return ""


def summarise(
    questions: list[Question],
    unmatched: list[AnswerBlock],
    graded: bool,
    overall: str,
) -> Summary:
    answered = [q for q in questions if q.status == "answered"]
    return Summary(
        total_questions=len(questions),
        answered=len(answered),
        unanswered=len(questions) - len(answered),
        unmatched_answers=len(unmatched),
        marks_awarded=round(
            sum(q.grade.awarded for q in questions if q.grade), 2
        ),
        marks_total=round(
            sum(
                (q.grade.max if q.grade else (q.marks or DEFAULT_MARKS))
                for q in questions
            ),
            2,
        ),
        graded=graded,
        overall_feedback=overall,
    )
