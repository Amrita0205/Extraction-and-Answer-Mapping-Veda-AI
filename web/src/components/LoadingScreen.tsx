"use client";

import { useEffect, useState } from "react";
import type { Stage } from "@/lib/types";
import { Sparkle } from "./icons";

const LABEL: Record<Stage, string> = {
  queued: "Getting ready",
  rendering: "Reading your files",
  extracting_questions: "Extracting questions",
  extracting_answers: "Reading the answer sheet",
  mapping: "Matching answers to questions",
  grading: "Marking and writing feedback",
  done: "Ready",
  failed: "Something went wrong",
};

/**
 * The design's loading screen, plus one state it does not cover: a free-tier
 * API instance that has gone to sleep takes 30-60s to answer the first
 * request. Without this the screen looks broken for a minute; with it, the
 * wait reads as designed.
 */
export function LoadingScreen({
  stage,
  progress,
  waking,
}: {
  stage: Stage;
  progress: number;
  waking?: boolean;
}) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 25_000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <section className="flex min-h-0 flex-1 px-0 pb-3 sm:px-3">
      <div className="flex flex-1 flex-col items-center justify-center rounded-panel bg-white/80 backdrop-blur-xl">
        <Sparkle
          width={84}
          height={84}
          className="animate-sparkle text-brand"
        />
        <h2 className="mt-5 text-[26px] font-bold tracking-[-0.01em]">
          {waking ? "Waking the server…" : "Extracting…"}
        </h2>
        <p className="mt-1.5 text-[14px] text-ink-soft">
          {waking
            ? "The API sleeps on the free tier. This first request takes about a minute."
            : "This may take a while"}
        </p>

        {/* Not in the design, but the brief asks for processing progress and a
            six-page sheet is a long wait without it. Kept deliberately quiet
            so the composition above it reads as designed. */}
        <div className="mt-7 h-0.75 w-48 overflow-hidden rounded-full bg-black/8">
          <div
            className="h-full rounded-full bg-brand transition-[width] duration-500 ease-out"
            style={{ width: `${Math.max(4, Math.round(progress * 100))}%` }}
          />
        </div>
        {!waking && (
          <p className="mt-2 text-[11px] text-ink-faint">{LABEL[stage]}</p>
        )}

        {slow && !waking && (
          <p className="mt-4 max-w-xs text-center text-[11.5px] text-ink-faint">
            Still working. Long answer sheets are read a page at a time, so a
            six-page scan takes a couple of minutes.
          </p>
        )}
      </div>
    </section>
  );
}
