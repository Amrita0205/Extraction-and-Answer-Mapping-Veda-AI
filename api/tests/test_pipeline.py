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

# ADDED SO THAT THE MANY WAYS A STUDENT WRITES A QUESTION NUMBER ("Q11(b)", "11.b)", "Question 11 - part b") ALL PARSE TO THE SAME LABEL.
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


# ADDED SO THAT AN ANSWER WHOSE NUMBER IS BURIED IN ITS FIRST WORDS, RATHER THAN WRITTEN IN THE MARGIN, IS STILL MATCHED BY LABEL.
def test_label_embedded_in_text():
    number, part = labels.parse_leading(
        "Q3. The process mainly occurs in the chloroplast of the plant cell."
    )
    assert (number, part) == ("3", None)


# ADDED SO THAT THE LIST READS IN PRINTED ORDER - 11 BEFORE 11(a) BEFORE 11(b) - WHICH THE BRIEF REQUIRES AND PLAIN STRING SORTING GETS WRONG.
def test_sort_order_puts_subparts_after_stem():
    order = sorted(
        [("11", "b"), ("2", None), ("11", "a"), ("11", None)],
        key=lambda t: labels.sort_key(*t),
    )
    assert order == [("2", None), ("11", None), ("11", "a"), ("11", "b")]


# --------------------------------------------------------------------------
# Question normalisation
# --------------------------------------------------------------------------

# ADDED SO THAT A MODEL RETURNING "11(b)" AS ONE STRING STILL BECOMES number=11 AND part=b, INSTEAD OF A QUESTION NUMBERED "11(b)".
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


# ADDED SO THAT A QUESTION READ TWICE AT A PAGE BOUNDARY COLLAPSES TO ONE ENTRY, KEEPING THE MORE COMPLETE READING.
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


# ADDED SO THAT THE INTERNAL-CHOICE FIX BELOW CANNOT TURN ORDINARY OCR NOISE ON A RE-READ INTO A PHANTOM EXTRA QUESTION.
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


# ADDED SO THAT A PAPER PRINTING "13 ... OR 13 ..." KEEPS BOTH BRANCHES - MERGING THEM SILENTLY DROPPED WHICHEVER ONE THE STUDENT ANSWERED.
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


# ADDED SO THAT A HIGHLIGHT SNAPS ONTO THE INK AND NOT ONTO THE BAND OF EMPTY RULED PAPER THE MODEL INCLUDES BELOW THE LAST LINE.
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


# ADDED SO THAT TIGHTENING A REGION WITH NO INK IN IT RETURNS THE REGION UNCHANGED RATHER THAN COLLAPSING TO NOTHING.
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


# ADDED SO THAT "HANDLE QUESTIONS ANSWERED OUT OF ORDER" HOLDS - THE LABEL DECIDES, SO WRITING ORDER IS IRRELEVANT.
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


# ADDED SO THAT A BLANK QUESTION AND AN ANSWER MATCHING NOTHING STAY TWO DIFFERENT OUTCOMES, WHICH THE BRIEF ASKS FOR SEPARATELY.
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


# ADDED SO THAT 11(a) AND 11(b) CAN BE MATCHED, MISSED OR MARKED ON THEIR OWN, RATHER THAN MOVING TOGETHER AS ONE QUESTION.
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


# ADDED SO THAT AN ANSWER RUNNING OVER A PAGE BREAK IS ONE ANSWER WITH A HIGHLIGHT ON BOTH PAGES, NOT TWO HALVES.
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


# ADDED SO THAT AN ANSWER THE STUDENT NEVER NUMBERED IS STILL PLACED, BY CONTENT, INSTEAD OF BEING DROPPED.
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



# ADDED SO THAT A SIX-ELEMENT box_2d IS NOT THROWN AWAY - REJECTING IT SILENTLY MADE EVERY HIGHLIGHT THE WHOLE PAGE.
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


# ADDED SO THAT "Q14" ON A PAPER ENDING AT 13 IS REPORTED UNMATCHED, NOT REASSIGNED TO A REAL QUESTION BY WORD OVERLAP.
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



# ADDED SO THAT "13." RESOLVES TO THE BRANCH THE ANSWER ACTUALLY ADDRESSES - DEFAULTING TO THE FIRST PRINTED ONE MARKED A CORRECT ANSWER ZERO.
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
    # index 1 is the TCP/IP branch — the one this answer addresses.
    with _stub_model({"index": 1}) as model:
        questions, unmatched, _ = mapping.map_answers(questions, blocks)
    assert model.calls >= 1, "the branch should be decided by asking, not by overlap"
    thirteens = [q for q in questions if q.number == "13"]

    answered = [q for q in thirteens if q.status == "answered"]
    assert len(answered) == 1
    assert "TCP/IP" in answered[0].text, "must match the branch actually written"

    skipped = [q for q in thirteens if q.status == "not_chosen"]
    assert len(skipped) == 1, "the other branch is not_chosen, never unanswered"


# ADDED SO THAT A PAPER OUT OF 40 IS NOT REPORTED OUT OF 45 BY COUNTING BOTH BRANCHES OF A CHOICE.
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
    with _stub_model({"index": 1}):
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


# ADDED SO THAT ONE MISREAD DIGIT ("8" AS "7") DOES NOT COST TWO QUESTIONS - THE ANSWER MISFILED, AND THE RIGHT QUESTION REPORTED BLANK.
def test_a_misread_label_is_repaired_from_content():
    """A digit misread on the answer sheet costs two questions, not one.

    On the real sample an "8" was transcribed as "7": the normalization answer
    was filed under "compiler vs interpreter", and normalization itself was
    reported as never attempted. The answer shares no words at all with the
    question its label pointed at, and plenty with one sitting unanswered,
    which is one-sided enough to overrule the label.
    """
    questions = [
        _question("7", None, "Differentiate between a compiler and an interpreter.", 3),
        _question("8", None, "What is normalization in a database? Name any two normal forms.", 3),
    ]
    blocks = [
        _block("a1", "Q7.",
               "Normalization is the process of organising the data in a database so "
               "that redundancy is reduced and update anomalies are avoided. Two normal "
               "forms are First Normal Form and Second Normal Form."),
    ]
    questions, _unmatched, _w = mapping.map_answers(questions, blocks)
    by_number = {q.number: q for q in questions}

    assert by_number["8"].status == "answered", "the answer belongs to 8"
    assert by_number["7"].status == "unanswered", "and 7 was genuinely left blank"
    assert by_number["8"].answer.confidence < 0.97, (
        "overruling the student's own label is weaker evidence than following it"
    )


# ADDED SO THAT THE REPAIR ABOVE CANNOT MOVE A CORRECT ANSWER LIKE "RANDOM ACCESS MEMORY", WHICH SHARES NO WORDS WITH "EXPAND RAM." AND IS FINE.
def test_a_correct_short_answer_sharing_no_words_is_left_alone():
    """The repair must not fire on every low-scoring label match.

    "Expand the abbreviation RAM." and "Random Access Memory" have no token in
    common, and that answer is perfectly correct. A rule that moved answers on
    a low score alone would break it; only a low score *beside a strong rival*
    counts as evidence.
    """
    questions = [
        _question("2", None, "Expand the abbreviation RAM.", 1),
        _question("4", None, "Expand the abbreviation HTTP.", 1),
    ]
    blocks = [_block("a1", "Q2.", "Random Access Memory")]
    questions, _unmatched, _w = mapping.map_answers(questions, blocks)
    by_number = {q.number: q for q in questions}

    assert by_number["2"].status == "answered"
    assert by_number["2"].answer.match_method == "label", "the label must still win"
    assert by_number["4"].status == "unanswered"



class _stub_model:
    """Answer every model call in a test with a fixed payload.

    The mapping ladder asks the model two things - which branch of an internal
    choice an answer addresses, and who owns any block still floating at the
    end. Both are real code paths worth testing, but a test suite that reaches
    the network is neither deterministic nor free, and these run against a
    quota of 20 requests a day. So the request is made for real and the reply
    is stubbed.
    """

    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def __enter__(self):
        self._real = gemini.generate_json

        def fake(*_args, **_kwargs):
            self.calls += 1
            return self.reply

        gemini.generate_json = fake
        return self

    def __exit__(self, *_exc):
        gemini.generate_json = self._real
        return False



# ADDED SO THAT A ZERO-PADDED LABEL ("05.") STILL FINDS QUESTION 5 - THE ORPHAN
# CHECK COMPARED RAW NUMBERS AND THREW AWAY EVERY ANSWER ON A PADDED SHEET.
def test_zero_padded_labels_match_the_printed_number():
    """Students zero-pad. A sheet numbered "01." to "09." is ordinary.

    The safeguard that leaves "Q15" unmatched on a paper ending at 14 compared
    the number as written against the paper's numbers, so "05" was judged a
    question the paper does not contain and was held back from every remaining
    rung. On a padded sheet that silently discarded most of the answers.
    """
    questions = [
        _question("5", None, "Which sorting algorithm has O(n log n) worst case?", 1),
        _question("6", None, "Define time complexity.", 3),
        _question("7", None, "Differentiate between a compiler and an interpreter.", 3),
    ]
    blocks = [
        _block("a5", "05.", "(b) Quick Sort"),
        _block("a6", "06.", "Time complexity measures the running time of an algorithm."),
        _block("a7", "07.", "A compiler translates the whole program, an interpreter line by line."),
    ]
    questions, unmatched, _w = mapping.map_answers(questions, blocks)

    assert [q.status for q in questions] == ["answered"] * 3
    assert unmatched == [], "a padded label is the same question, not a stray answer"
    assert labels.norm_number("05") == labels.norm_number("5")


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
