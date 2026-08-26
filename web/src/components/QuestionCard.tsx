"use client";

import type { Question, UnmatchedAnswer } from "@/lib/types";
import { Chevron, Sparkle } from "./icons";

export function ScorePill({
  awarded,
  max,
  muted,
  className = "",
}: {
  awarded: number;
  max: number;
  muted?: boolean;
  className?: string;
}) {
  const full = max > 0 && awarded >= max;
  const zero = awarded <= 0;
  const tone = muted || zero
    ? "bg-bad-bg text-bad"
    : full
      ? "bg-good-bg text-good"
      : "bg-warn-bg text-warn";

  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-[3px] text-[11.5px] font-semibold tabular-nums ${tone} ${className}`}
    >
      {trim(awarded)} / {trim(max)}
    </span>
  );
}

const trim = (n: number) => (Number.isInteger(n) ? n : Number(n.toFixed(1)));

export function QuestionCard({
  question,
  selected,
  expanded,
  onSelect,
  onToggle,
}: {
  question: Question;
  selected: boolean;
  expanded: boolean;
  onSelect: () => void;
  onToggle: () => void;
}) {
  const unanswered = question.status === "unanswered";
  const grade = question.grade;

  return (
    <article
      onClick={onSelect}
      className={[
        "cursor-pointer rounded-card bg-white transition",
        selected
          ? "border-2 border-brand-soft shadow-[0_2px_10px_rgba(255,86,35,0.08)]"
          : "border border-transparent hover:border-hairline",
      ].join(" ")}
    >
      {/* Below lg the design puts the badge, score and chevron on one row and
          drops the question text underneath; from lg they sit inline. */}
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2 px-3.5 py-3">
        <span className="order-1 flex shrink-0 items-center gap-1.5 pt-0.5">
          <span
            className={[
              "grid h-7 w-7 place-items-center rounded-full text-[12px] font-bold text-white",
              selected ? "bg-brand" : unanswered ? "bg-ink/45" : "bg-ink",
            ].join(" ")}
          >
            {question.number}
          </span>
          {question.part && (
            <span className="rounded-md bg-chip px-1.5 py-[3px] text-[11px] font-semibold text-ink-soft">
              {question.part}.
            </span>
          )}
        </span>

        <p
          className={[
            "order-4 w-full min-w-0 text-[12.5px] leading-[1.45] lg:order-2 lg:w-auto lg:flex-1",
            unanswered ? "text-ink-faint" : "text-ink",
          ].join(" ")}
        >
          {question.text}
        </p>

        {grade && (
          <ScorePill
            awarded={grade.awarded}
            max={grade.max}
            muted={unanswered}
            className="order-2 ml-auto lg:order-3 lg:ml-0"
          />
        )}

        <button
          type="button"
          aria-label={expanded ? "Collapse" : "Expand"}
          aria-expanded={expanded}
          onClick={(event) => {
            event.stopPropagation();
            onToggle();
          }}
          className="order-3 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-chip text-ink-soft transition hover:bg-black/10 hover:text-ink lg:order-4 lg:h-6 lg:w-6 lg:bg-transparent lg:text-ink-faint lg:hover:bg-chip"
        >
          <Chevron dir={expanded ? "up" : "down"} width={15} height={15} />
        </button>
      </div>

      {expanded && (
        <div className="animate-rise px-3.5 pb-3.5">
          {unanswered ? (
            <div className="rounded-[10px] bg-bad-bg/60 px-3 py-2.5 text-[12px] text-bad">
              No answer for this question was found anywhere on the answer sheet.
            </div>
          ) : (
            <div className="space-y-2.5">
              <div className="rounded-[10px] bg-chip px-3 py-2.5">
                <p className="mb-1 text-[11px] font-bold">
                  Student&apos;s answer
                </p>
                <p className="text-[12px] leading-normal text-ink-soft">
                  {question.answer?.text || "—"}
                </p>
              </div>

              {grade?.feedback && (
                <div className="rounded-[10px] bg-chip px-3 py-2.5">
                  <p className="mb-1 flex items-center gap-1.5 text-[11px] font-bold">
                    <Sparkle width={12} height={12} className="text-brand" />
                    AI Feedback
                  </p>
                  <p className="text-[12px] leading-normal text-ink-soft">
                    {grade.feedback}
                  </p>
                </div>
              )}

              <MatchNote question={question} />
            </div>
          )}
        </div>
      )}
    </article>
  );
}

/** Why this answer was attached to this question — the teacher's audit trail. */
function MatchNote({ question }: { question: Question }) {
  const answer = question.answer;
  if (!answer) return null;

  const how =
    answer.match_method === "label"
      ? "matched by the number the student wrote"
      : answer.match_method === "inherited"
        ? "matched by the sub-part, numbered from the answer above"
        : answer.match_method === "semantic"
        ? "matched by content — the student did not label it"
        : answer.match_method === "sequential"
          ? "matched by position on the page"
          : "unmatched";

  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-ink-faint">
      <span>{how}</span>
      <span aria-hidden>·</span>
      <span>{Math.round(answer.confidence * 100)}% confidence</span>
      {answer.spans_pages && (
        <>
          <span aria-hidden>·</span>
          <span className="font-medium text-brand">
            spans {new Set(answer.regions.map((r) => r.page)).size} pages
          </span>
        </>
      )}
    </p>
  );
}

/**
 * An answer that matched no question. The Figma has no state for this, but the
 * brief requires handling it, so it gets one built from the same vocabulary:
 * the badge shape of a question row, in the zero-marks red, with a "?" where
 * the number would be.
 */
export function OrphanCard({
  answer,
  selected,
  expanded,
  onSelect,
  onToggle,
}: {
  answer: UnmatchedAnswer;
  selected: boolean;
  expanded: boolean;
  onSelect: () => void;
  onToggle: () => void;
}) {
  return (
    <article
      onClick={onSelect}
      className={[
        "cursor-pointer rounded-card bg-white transition",
        selected
          ? "border-2 border-brand-soft shadow-[0_2px_10px_rgba(255,86,35,0.08)]"
          : "border border-transparent hover:border-hairline",
      ].join(" ")}
    >
      <div className="flex items-start gap-3 px-3.5 py-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-bad-bg text-[12px] font-bold text-bad">
          ?
        </span>
        <p className="min-w-0 flex-1 text-[12.5px] leading-[1.45]">
          <span className="font-semibold">
            {answer.label?.replace(/[.:]$/, "") ?? "Unlabelled answer"}
          </span>
          <span className="text-ink-faint">
            {" "}
            — no question on the paper matches this answer.
          </span>
        </p>
        <button
          type="button"
          aria-label={expanded ? "Collapse" : "Expand"}
          aria-expanded={expanded}
          onClick={(event) => {
            event.stopPropagation();
            onToggle();
          }}
          className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-ink-faint transition hover:bg-chip hover:text-ink"
        >
          <Chevron dir={expanded ? "up" : "down"} width={15} height={15} />
        </button>
      </div>

      {expanded && (
        <div className="animate-rise px-3.5 pb-3.5">
          <div className="rounded-[10px] bg-chip px-3 py-2.5">
            <p className="mb-1 text-[11px] font-bold">What the student wrote</p>
            <p className="text-[12px] leading-normal text-ink-soft">
              {answer.text || "—"}
            </p>
          </div>
        </div>
      )}
    </article>
  );
}
