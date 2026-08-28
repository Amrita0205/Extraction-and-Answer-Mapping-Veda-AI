"use client";

import { useMemo, useState } from "react";
import type { Result, Row } from "@/lib/types";
import { Chevron } from "./icons";
import { AnswerSheet } from "./AnswerSheet";
import { OrphanCard, QuestionCard } from "./QuestionCard";
import { Underlined } from "./Underlined";

export function MappingScreen({
  result,
  onReset,
}: {
  result: Result;
  onReset: () => void;
}) {
  const rows = useMemo<Row[]>(
    () => [
      ...result.questions.map((question) => ({
        kind: "question" as const,
        question,
      })),
      ...result.unmatched_answers.map((answer) => ({
        kind: "orphan" as const,
        answer,
      })),
    ],
    [result],
  );

  const firstRowId = rows.length
    ? rows[0].kind === "question"
      ? rows[0].question.id
      : rows[0].answer.id
    : null;
  const firstAnswered =
    result.questions.find((question) => question.status === "answered")?.id ??
    firstRowId;

  const [selected, setSelected] = useState<string | null>(firstAnswered ?? null);
  // Below lg the two panels don't fit side by side, so the design puts them
  // behind a segmented control.
  const [tab, setTab] = useState<"questions" | "sheet">("questions");
  const [open, setOpen] = useState<Set<string>>(
    () => new Set(firstAnswered ? [firstAnswered] : []),
  );

  const allOpen = open.size >= rows.length;
  const toggleAll = () =>
    setOpen(
      allOpen
        ? new Set()
        : new Set(
            rows.map((row) =>
              row.kind === "question" ? row.question.id : row.answer.id,
            ),
          ),
    );

  // On a phone, picking a question moves to the sheet — seeing the highlight
  // is the reason for the tap. The tabs get you back.
  const select = (id: string) => {
    setSelected(id);
    if (window.matchMedia("(max-width: 1023px)").matches) setTab("sheet");
  };

  const toggle = (id: string) =>
    setOpen((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const active = rows.find(
    (row) => (row.kind === "question" ? row.question.id : row.answer.id) === selected,
  );

  const regions =
    active?.kind === "question"
      ? (active.question.answer?.regions ?? [])
      : (active?.answer.regions ?? []);

  const tag =
    active?.kind === "question"
      ? `Q${active.question.number}${active.question.part ? active.question.part : ""}`
      : (active?.answer.label?.replace(/[.:]$/, "") ?? null);

  const { summary } = result;

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-2.5 px-0 pb-3 sm:px-3">
      <SummaryStrip
        summary={summary}
        warnings={result.warnings}
        onReset={onReset}
      />

      <SegmentedTabs tab={tab} onChange={setTab} />

      {/* Below lg one panel shows at a time behind the tabs; from lg they sit
          side by side at full height and scroll independently. */}
      {/*
        The floor matters on a short laptop. Without it these two panes just
        take whatever height is left, so at 900px tall — minus browser chrome,
        the top bar, the summary strip and the tabs — each pane is a couple of
        question cards deep and the screen reads as broken. Below the floor the
        page scrolls instead of the panes shrinking further.
      */}
      <div className="grid min-h-120 flex-1 gap-3 lg:grid-cols-2">
        {/* Left — the extracted questions, in printed order. */}
        <div
          className={[
            "min-h-0 flex-col rounded-panel bg-white/50 p-3 backdrop-blur-xl lg:flex",
            tab === "questions" ? "flex" : "hidden",
          ].join(" ")}
        >
          <div className="mb-2 flex shrink-0 items-center justify-between px-1">
            <h2 className="min-w-0 text-[12px] font-bold sm:text-[13px]">
              Extracted <Underlined>Questions</Underlined>{" "}
              <span className="font-normal text-ink-faint">
                (from question paper)
              </span>
            </h2>
            <button
              type="button"
              onClick={toggleAll}
              className="shrink-0 whitespace-nowrap rounded-full px-2 py-1 text-[11.5px] font-medium text-ink-soft transition hover:bg-white/70 hover:text-ink"
            >
              {allOpen ? "Collapse All" : "Expand All"}
            </button>
          </div>

          <div className="no-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {rows.map((row) =>
              row.kind === "question" ? (
                <QuestionCard
                  key={row.question.id}
                  question={row.question}
                  selected={selected === row.question.id}
                  expanded={open.has(row.question.id)}
                  onSelect={() => select(row.question.id)}
                  onToggle={() => toggle(row.question.id)}
                />
              ) : (
                <OrphanCard
                  key={row.answer.id}
                  answer={row.answer}
                  selected={selected === row.answer.id}
                  expanded={open.has(row.answer.id)}
                  onSelect={() => select(row.answer.id)}
                  onToggle={() => toggle(row.answer.id)}
                />
              ),
            )}
          </div>
        </div>

        {/* Right — the answer sheet with the selected region lit up. */}
        <div
          className={[
            "min-h-0 lg:flex",
            tab === "sheet" ? "flex" : "hidden",
          ].join(" ")}
        >
          <AnswerSheet
            pages={result.answer_pages}
            regions={regions}
            label={tag}
          />
        </div>
      </div>
    </section>
  );
}

function SegmentedTabs({
  tab,
  onChange,
}: {
  tab: "questions" | "sheet";
  onChange: (tab: "questions" | "sheet") => void;
}) {
  const item = (active: boolean) =>
    [
      "flex-1 rounded-full py-2.5 text-[14px] font-semibold transition",
      active ? "bg-ink text-white" : "text-ink-soft",
    ].join(" ");

  return (
    <div className="flex shrink-0 gap-1 rounded-full bg-white/70 p-1 backdrop-blur-xl lg:hidden">
      <button
        type="button"
        onClick={() => onChange("questions")}
        className={item(tab === "questions")}
      >
        <Underlined>Questions</Underlined>
      </button>
      <button
        type="button"
        onClick={() => onChange("sheet")}
        className={item(tab === "sheet")}
      >
        Answer Sheet
      </button>
    </div>
  );
}

function SummaryStrip({
  summary,
  warnings,
  onReset,
}: {
  summary: Result["summary"];
  warnings: string[];
  onReset: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="shrink-0 rounded-2xl bg-white/55 px-3.5 py-2.5 backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <Stat label="Questions" value={summary.total_questions} />
        <Stat label="Answered" value={summary.answered} tone="good" />
        <Stat label="Unanswered" value={summary.unanswered} tone="bad" />
        <Stat label="Unmatched" value={summary.unmatched_answers} tone="warn" />
        {summary.graded && (
          <Stat
            label="Score"
            value={`${trim(summary.marks_awarded)} / ${trim(summary.marks_total)}`}
          />
        )}
        <button
          type="button"
          onClick={onReset}
          className="ml-auto rounded-full border border-black/10 px-3 py-1.5 text-[11.5px] font-medium text-ink-soft transition hover:bg-white hover:text-ink"
        >
          New upload
        </button>
      </div>

      {/*
        The counts stay; the prose folds away. The brief asks for a clear
        grading summary, so the numbers are always on screen — but the overall
        feedback plus a few warnings ran to nine or ten lines on a real sheet,
        which pushed the questions and the answer sheet below the fold. The
        design puts those two panels directly under the top bar, and they are
        what the teacher came to look at.
      */}
      {(summary.overall_feedback || warnings.length > 0) && (
        <div className="mt-1.5 border-t border-black/5 pt-1.5">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="flex items-center gap-1.5 rounded-full py-0.5 text-[11.5px] font-medium text-ink-soft transition hover:text-ink"
          >
            <Chevron
              dir={open ? "up" : "down"}
              width={13}
              height={13}
              className="text-ink-faint"
            />
            {open ? "Hide" : "Show"} feedback
            {warnings.length > 0 && (
              <span className="rounded-full bg-warn-bg px-1.5 py-0.5 text-[10.5px] font-semibold text-warn">
                {warnings.length}
              </span>
            )}
          </button>

          {open && (
            <div className="animate-rise pt-1.5">
              {summary.overall_feedback && (
                <p className="text-[11.5px] leading-normal text-ink-soft">
                  <span className="font-semibold text-ink">Overall — </span>
                  {summary.overall_feedback}
                </p>
              )}
              {warnings.length > 0 && (
                <ul className="mt-1.5 space-y-0.5">
                  {warnings.map((warning) => (
                    <li key={warning} className="text-[11px] text-warn">
                      {warning}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "good" | "bad" | "warn";
}) {
  const color =
    tone === "good"
      ? "text-good"
      : tone === "bad"
        ? "text-bad"
        : tone === "warn"
          ? "text-warn"
          : "text-ink";
  return (
    <span className="flex items-baseline gap-1.5">
      <span className={`text-[15px] font-bold tabular-nums ${color}`}>{value}</span>
      <span className="text-[11px] text-ink-faint">{label}</span>
    </span>
  );
}

const trim = (n: number) => (Number.isInteger(n) ? n : Number(n.toFixed(1)));
