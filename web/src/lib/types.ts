/**
 * Mirrors `api/pipeline/schemas.py`. Change one, change the other.
 */

export type Stage =
  | "queued"
  | "rendering"
  | "extracting_questions"
  | "extracting_answers"
  | "mapping"
  | "grading"
  | "done"
  | "failed";

export type MatchMethod = "label" | "semantic" | "sequential" | "none";
export type Verdict = "correct" | "partial" | "incorrect" | "ungraded";

/** A rectangle on one page, in page fractions (0..1) rather than pixels, so
 *  the overlay stays correct at any rendered width. */
export interface Region {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface PageInfo {
  index: number;
  width: number;
  height: number;
  url: string;
}

export interface Grade {
  awarded: number;
  max: number;
  verdict: Verdict;
  feedback: string;
}

export interface Answer {
  id: string;
  text: string;
  regions: Region[];
  confidence: number;
  match_method: MatchMethod;
  spans_pages: boolean;
}

export interface Question {
  id: string;
  /** Printed number, preserved verbatim — "11". */
  number: string;
  /** Sub-part, rendered as its own pill — "b". Null when there isn't one. */
  part: string | null;
  text: string;
  marks: number | null;
  order: number;
  status: "answered" | "unanswered";
  answer: Answer | null;
  grade: Grade | null;
}

export interface UnmatchedAnswer {
  id: string;
  label: string | null;
  text: string;
  regions: Region[];
  matched_question_id: string | null;
  match_method: MatchMethod;
  confidence: number;
}

export interface Summary {
  total_questions: number;
  answered: number;
  unanswered: number;
  unmatched_answers: number;
  marks_awarded: number;
  marks_total: number;
  graded: boolean;
  overall_feedback: string;
}

export interface Result {
  questions: Question[];
  unmatched_answers: UnmatchedAnswer[];
  question_pages: PageInfo[];
  answer_pages: PageInfo[];
  summary: Summary;
  warnings: string[];
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "failed";
  stage: Stage;
  progress: number;
  message: string;
  error: string | null;
  result: Result | null;
}

/** What the left-hand list renders — a question row, or an answer that
 *  belongs to no question. The design has no state for the second kind, so
 *  it gets one built from the same vocabulary. */
export type Row =
  | { kind: "question"; question: Question }
  | { kind: "orphan"; answer: UnmatchedAnswer };
