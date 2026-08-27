"""Tests for the parts of the pipeline that don't call the model.

Everything here is deterministic: label parsing, box tightening, and the
mapping ladder. Those are where the brief's edge cases actually get decided,
so they are worth pinning down without spending API quota.

    python api/tests/test_pipeline.py        # or: pytest api/tests
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from pipeline import gemini, grading, labels, mapping  # noqa: E402
from pipeline.questions import _normalise  # noqa: E402
from pipeline.schemas import AnswerBlock, Grade, Region  # noqa: E402
from pipeline.tighten import tighten  # noqa: E402


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

def test_label_forms():
    cases = {
        "Q2.": ("2", None),
        "2)": ("2", None),
        "Question 7:": ("7", None),
        "11 (b)": ("11", "b"),
        "11(B)": ("11", "b"),
        "Q11 b)": ("11", "b"),
        "Ques 5 (iii)": ("5", "iii"),
        "  q12  ": ("12", None),
        "Ans": (None, None),
        "": (None, None),
        "Roll No 42314": (None, None),
    }
    for raw, expected in cases.items():
        assert labels.parse(raw) == expected, f"{raw!r} -> {labels.parse(raw)}"


def test_label_embedded_in_text():
    number, part = labels.parse_leading(
        "Q3. The process mainly occurs in the chloroplast of the plant cell."
    )
    assert (number, part) == ("3", None)


def test_sort_order_puts_subparts_after_stem():
    order = sorted(
        [("11", "b"), ("2", None), ("11", "a"), ("11", None)],
        key=lambda t: labels.sort_key(*t),
    )
    assert order == [("2", None), ("11", None), ("11", "a"), ("11", "b")]


# --------------------------------------------------------------------------
# Question normalisation
# --------------------------------------------------------------------------

def test_subpart_packed_into_number_is_split():
    questions = _normalise(
        [
            {"number": "11(a)", "text": "First half of the question.", "marks": 2},
            {"number": "11", "part": "b", "text": "Second half.", "marks": 3},
        ],
        [],
    )
    assert [(q.number, q.part) for q in questions] == [("11", "a"), ("11", "b")]
    assert questions[0].marks == 2 and questions[1].marks == 3


def test_duplicate_label_keeps_the_fuller_text():
    questions = _normalise(
        [
            {"number": "4", "text": "Describe the flow of blood"},
            {"number": "4", "text": "Describe the flow of blood through the heart"},
        ],
        [],
    )
    assert len(questions) == 1
    assert questions[0].text.endswith("through the heart")


def test_near_duplicate_ocr_reread_still_merges():
    """Two reads of the same question at a page boundary, worded slightly
    differently by OCR/vision noise, must still collapse to one — the
    internal-choice fix below must not turn ordinary re-reads into phantom
    extra questions."""
    questions = _normalise(
        [
            {"number": "6", "text": "Explain the process of photosynthesis in plants."},
            {"number": "6", "text": "Explain the process of photosynthesis in green plants."},
        ],
        [],
    )
    assert len(questions) == 1


def test_internal_choice_questions_are_not_merged_into_one():
    """Papers often print an internal choice as two questions sharing one
    number: "13 — Explain the OSI model" / "13 — OR — Explain the TCP/IP
    model". Neither has a lettered sub-part, so they collide on the same key
    as a plain duplicate — the dedup used to keep only the longer text and
    silently drop the other branch entirely, which meant whichever branch a
    student actually attempted could vanish before mapping ever saw it."""
    questions = _normalise(
        [
            {"number": "12", "text": "Explain any two features of a computer network.", "marks": 3},
            {"number": "13", "text": "Explain the seven layers of the OSI model with a diagram.", "marks": 5},
            {"number": "13", "text": "OR: Explain the TCP/IP model and compare it with OSI.", "marks": 5},
            {"number": "14", "text": "What is an IP address? Give one example.", "marks": 2},
        ],
        [],
    )
    assert len(questions) == 4, "both branches of the internal choice must survive"
    thirteens = [q for q in questions if q.number == "13"]
    assert len(thirteens) == 2
    assert thirteens[0].id != thirteens[1].id, "branches need distinct ids to both be mappable"
    assert {q.marks for q in thirteens} == {5}

    # Distinguished by identity, never by inventing a sub-part. The brief
    # requires the printed numbering to be preserved, and a paper that prints
    # "13" twice does not print a "13(alt2)" — a synthetic part would reach
    # the teacher as a sub-part pill the paper never had.
    assert [q.part for q in thirteens] == [None, None], "no invented sub-parts"
    assert {q.choice_group for q in thirteens} == {"13|"}
    assert sorted(q.choice_branch for q in thirteens) == [0, 1]


# --------------------------------------------------------------------------
# Box tightening
# --------------------------------------------------------------------------

def _page_with_ink(tmp: Path) -> Path:
    """Ruled page with writing in the top third and blank paper below."""
    img = Image.new("RGB", (800, 1000), (253, 252, 249))
    draw = ImageDraw.Draw(img)
    for y in range(0, 1000, 30):
        draw.line([(40, y), (760, y)], fill=(206, 219, 236), width=1)  # ruling
    draw.line([(70, 0), (70, 1000)], fill=(233, 173, 178), width=2)  # margin
    for y in range(220, 340, 30):
        x = 120
        while x < 600:
            draw.line([(x, y), (x + 40, y)], fill=(30, 50, 130), width=3)
            x += 55
    path = tmp / "page.png"
    img.save(path)
    return path


def test_tightening_drops_blank_paper(tmp_path_factory=None):
    tmp = Path("/tmp/veda-test")
    tmp.mkdir(exist_ok=True)
    path = _page_with_ink(tmp)

    # A generous proposal: correct-ish at the top, running far past the writing.
    loose = (0.05, 0.15, 0.95, 0.85)
    fitted = tighten(path, loose)

    assert fitted[3] < 0.45, f"bottom edge should snap up to the ink, got {fitted}"
    assert fitted[1] > 0.18, f"top edge should snap down to the ink, got {fitted}"
    assert fitted[0] > 0.10, "left edge should clear the margin rule"
    # The ink really is inside the result.
    assert fitted[1] < 0.22 < fitted[3] and fitted[0] < 0.2 < fitted[2]


def test_tightening_leaves_a_blank_region_alone():
    tmp = Path("/tmp/veda-test")
    tmp.mkdir(exist_ok=True)
    path = _page_with_ink(tmp)
    blank = (0.1, 0.6, 0.9, 0.8)  # only ruling down there, no writing
    assert tighten(path, blank) == blank


# --------------------------------------------------------------------------
# Mapping — the brief's edge cases
# --------------------------------------------------------------------------

def _question(number, part, text, marks=2):
    from pipeline.schemas import Question

    return Question(
        id=f"q_{number}_{part or ''}".rstrip("_"),
        number=number,
        part=part,
        text=text,
        marks=marks,
        order=0,
    )


def _block(bid, label, text, page=0, y0=0.1, y1=0.3):
    return AnswerBlock(
        id=bid,
        label=label,
        text=text,
        regions=[Region(page=page, x0=0.05, y0=y0, x1=0.9, y1=y1)],
    )


def test_out_of_order_answers_still_land_correctly():
    questions = [
        _question("1", None, "Which blood vessel carries blood away from the heart?"),
        _question("2", None, "Which organelle is involved in photosynthesis?"),
        _question("3", None, "Explain the role of chloroplasts."),
    ]
    # Written on the page as 1, then 3, then 2.
    blocks = [
        _block("a1", "Q1.", "The artery, and the aorta is the largest."),
        _block("a3", "Q3.", "It happens in the chloroplast, two stages."),
        _block("a2", "Q2.", "The chloroplast."),
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    assert [q.answer.id for q in questions] == ["a1", "a2", "a3"]
    assert all(q.answer.match_method == "label" for q in questions)
    assert unmatched == []


def test_unanswered_and_unmatched_are_reported_separately():
    questions = [
        _question("1", None, "Name the largest artery."),
        _question("2", None, "Define osmosis."),
    ]
    blocks = [
        _block("a1", "Q1.", "The aorta."),
        _block("a9", "Q14.", "Something about a topic not on this paper at all."),
    ]
    questions, unmatched, warnings = mapping.map_answers(questions, blocks)

    assert questions[0].status == "answered"
    assert questions[1].status == "unanswered" and questions[1].answer is None
    assert [b.id for b in unmatched] == ["a9"]
    assert any("did not correspond" in w for w in warnings)


def test_subparts_are_matched_independently():
    questions = [
        _question("11", "a", "Explain why Plant B is pale."),
        _question("11", "b", "Suggest one practical measure."),
    ]
    blocks = [
        _block("a11a", "11 (a)", "Less light means less chlorophyll."),
        _block("a11b", "Q11 b)", "Move it to a sunny window."),
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    assert questions[0].answer.id == "a11a"
    assert questions[1].answer.id == "a11b"
    assert unmatched == []


def test_same_label_across_pages_becomes_one_multi_page_answer():
    questions = [_question("11", "b", "Suggest one practical measure.", marks=3)]
    blocks = [
        _block("a1", "Q11 (b)", "Move the plant to a brighter spot", page=0, y0=0.7, y1=0.95),
        _block("a2", "Q11 (b)", "so it can make chlorophyll again.", page=1, y0=0.05, y1=0.2),
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    answer = questions[0].answer
    assert answer is not None
    assert answer.spans_pages is True
    assert [r.page for r in answer.regions] == [0, 1]
    assert unmatched == []


def test_unlabelled_answer_matches_on_content():
    questions = [
        _question("1", None, "Name the pigment that absorbs light in a leaf."),
        _question("2", None, "State two factors that increase transpiration rate."),
    ]
    blocks = [
        _block("a1", None, "Transpiration increases with higher temperature and wind."),
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    assert questions[1].answer is not None, "should have matched question 2 on content"
    assert questions[1].answer.match_method in ("semantic", "sequential")
    assert questions[0].status == "unanswered"



def test_box_with_trailing_flags_is_still_a_box():
    """The model sometimes flattens the continuation booleans into box_2d.

    It returns `[ymin, xmin, ymax, xmax, false, false]`. Rejecting that for
    being six long threw away a correct box, and the caller fell back to a
    whole-page rectangle — so the highlight silently became the entire sheet.
    """
    four = gemini.box_to_fractions([132, 118, 217, 858])
    six = gemini.box_to_fractions([132, 118, 217, 858, False, False])
    assert six is not None, "a six-element box should still parse"
    assert six == four, "the trailing flags must not change the box"

    assert gemini.box_to_fractions([132, 118]) is None, "too short is still bad"


def test_label_naming_a_question_not_on_the_paper_stays_unmatched():
    """"Q14" on a paper that stops at 13 answers nothing here.

    Content overlap used to reassign it — an answer about osmosis written for
    Q14 landed on Q13, "Define osmosis", which reads as a confident correct
    match and quietly loses the brief's "answers that match no question" case.
    """
    questions = [
        _question("12", None, "Calculate the pulmonary ventilation rate."),
        _question("13", None, "Define osmosis, and give one example in a plant cell."),
    ]
    blocks = [
        _block("a1", "Q14.",
               "Osmosis makes an animal cell swell and burst in pure water."),
    ]
    questions, unmatched, warnings = mapping.map_answers(questions, blocks)

    assert [b.id for b in unmatched] == ["a1"], "Q14 should be left unmatched"
    assert questions[1].status == "unanswered", "Q13 must not absorb it"
    assert any("does not contain" in w for w in warnings), "should say why"



def test_internal_choice_picks_the_branch_the_student_answered():
    """A student writing "13." cannot say *which* 13 they meant, so the branch
    has to come from what they wrote. Defaulting to the first printed one marks
    a correct TCP/IP answer against the OSI question, and reports the branch
    they did answer as blank."""
    questions = _normalise(
        [
            {"number": "12", "text": "Explain virtual memory using paging.", "marks": 5},
            {"number": "13", "text": "What is the OSI reference model? List its seven layers.", "marks": 5},
            {"number": "13", "text": "What is the TCP/IP model? Compare it with the OSI model.", "marks": 5},
        ],
        [],
    )
    blocks = [
        _block("a1", "13.",
               "The TCP/IP model has four layers: link, internet, transport and "
               "application. Compared with OSI it merges session and presentation."),
    ]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)
    thirteens = [q for q in questions if q.number == "13"]

    answered = [q for q in thirteens if q.status == "answered"]
    assert len(answered) == 1
    assert "TCP/IP" in answered[0].text, "must match the branch actually written"

    skipped = [q for q in thirteens if q.status == "not_chosen"]
    assert len(skipped) == 1, "the other branch is not_chosen, never unanswered"


def test_unchosen_branch_is_excluded_from_the_marks_total():
    """A paper out of 40 must not be reported out of 45. Only one branch of an
    internal choice counts, so the branch the student was never meant to answer
    contributes nothing to the denominator."""
    questions = _normalise(
        [
            {"number": "12", "text": "Explain virtual memory using paging.", "marks": 5},
            {"number": "13", "text": "What is the OSI reference model? List its seven layers.", "marks": 5},
            {"number": "13", "text": "What is the TCP/IP model? Compare it with the OSI model.", "marks": 5},
        ],
        [],
    )
    blocks = [_block("a1", "13.", "The TCP/IP model has four layers, unlike OSI which has seven.")]
    questions, unmatched, _ = mapping.map_answers(questions, blocks)

    # Grade offline: only the not_chosen branch needs its marks zeroed, and
    # that happens without an API call.
    for q in questions:
        if q.status == "not_chosen":
            q.grade = Grade(awarded=0.0, max=0.0, verdict="ungraded")
        else:
            q.grade = Grade(awarded=0.0, max=q.marks or 2.0, verdict="ungraded")

    summary = grading.summarise(questions, unmatched, True, "")
    assert summary.marks_total == 10, f"expected 10, got {summary.marks_total}"
    assert summary.unanswered == 1, "the unchosen branch is not an omission"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
