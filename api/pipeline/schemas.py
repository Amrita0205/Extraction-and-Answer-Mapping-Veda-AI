"""Wire types shared by the pipeline and the API layer.

These mirror `web/src/lib/types.ts` exactly. If you change a field here,
change it there too.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Stage = Literal[
    "queued",
    "rendering",
    "extracting_questions",
    "extracting_answers",
    "mapping",
    "grading",
    "done",
    "failed",
    "cancelled",
]

MatchMethod = Literal["label", "semantic", "sequential", "none"]
Verdict = Literal["correct", "partial", "incorrect", "ungraded"]


class Region(BaseModel):
    """A rectangle on one rendered page, in page fractions (0..1).

    Fractions rather than pixels so the frontend can overlay the highlight at
    whatever width it renders the page at, without knowing the render DPI.
    """

    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


class PageInfo(BaseModel):
    index: int
    width: int
    height: int
    url: str


class AnswerBlock(BaseModel):
    """One contiguous run of student writing that looks like a single answer."""

    id: str
    label: Optional[str] = None  # what the student wrote, e.g. "Q2.", "11 b)"
    text: str = ""
    regions: list[Region] = Field(default_factory=list)
    # Populated during mapping.
    matched_question_id: Optional[str] = None
    match_method: MatchMethod = "none"
    confidence: float = 0.0


class Grade(BaseModel):
    awarded: float = 0.0
    max: float = 0.0
    verdict: Verdict = "ungraded"
    feedback: str = ""
    # False when the marker judged that this answer does not address this
    # question at all — which usually means the mapping is wrong rather than
    # the student being wrong. Worth separating: a teacher should re-check the
    # pairing, not the pupil.
    addresses_question: bool = True


class Answer(BaseModel):
    id: str
    text: str
    regions: list[Region]
    confidence: float
    match_method: MatchMethod
    spans_pages: bool = False


class Question(BaseModel):
    id: str
    number: str  # "11"  — printed numbering, preserved verbatim
    part: Optional[str] = None  # "a" / "b" — rendered as its own pill
    text: str
    marks: Optional[float] = None
    order: int  # printed order, 0-based
    status: Literal["answered", "unanswered"] = "unanswered"
    answer: Optional[Answer] = None
    grade: Optional[Grade] = None

    @property
    def display_number(self) -> str:
        return f"{self.number}({self.part})" if self.part else self.number


class Summary(BaseModel):
    total_questions: int = 0
    answered: int = 0
    unanswered: int = 0
    unmatched_answers: int = 0
    marks_awarded: float = 0.0
    marks_total: float = 0.0
    graded: bool = False
    overall_feedback: str = ""


class Result(BaseModel):
    questions: list[Question] = Field(default_factory=list)
    unmatched_answers: list[AnswerBlock] = Field(default_factory=list)
    question_pages: list[PageInfo] = Field(default_factory=list)
    answer_pages: list[PageInfo] = Field(default_factory=list)
    summary: Summary = Field(default_factory=Summary)
    warnings: list[str] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    stage: Stage
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    result: Optional[Result] = None
