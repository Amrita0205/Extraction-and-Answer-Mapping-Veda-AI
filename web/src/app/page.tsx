"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createJob, pollJob, USING_MOCK } from "@/lib/api";
import type { JobStatus, Result, Stage } from "@/lib/types";
import { AppShell } from "@/components/AppShell";
import { LoadingScreen } from "@/components/LoadingScreen";
import { MappingScreen } from "@/components/MappingScreen";
import { UploadScreen } from "@/components/UploadScreen";

type View = "upload" | "processing" | "result";

export default function Page() {
  const [view, setView] = useState<View>("upload");
  const [stage, setStage] = useState<Stage>("queued");
  const [progress, setProgress] = useState(0);
  const [waking, setWaking] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stop = useRef<(() => void) | null>(null);
  useEffect(() => () => stop.current?.(), []);

  const start = useCallback(async (paper: File, sheet: File) => {
    setError(null);
    setStage("queued");
    setProgress(0.02);
    setView("processing");

    // A free-tier instance that has slept needs ~30-60s before it answers at
    // all. Say so rather than showing a spinner that looks stuck.
    const wakeTimer = setTimeout(() => setWaking(true), 6000);

    try {
      const job: JobStatus = await createJob(paper, sheet);
      clearTimeout(wakeTimer);
      setWaking(false);

      if (USING_MOCK) {
        // Walk the mock through the real stages so the loading screen can be
        // reviewed without a backend.
        const stages: Stage[] = [
          "rendering",
          "extracting_questions",
          "extracting_answers",
          "mapping",
          "grading",
        ];
        for (const [index, next] of stages.entries()) {
          setStage(next);
          setProgress((index + 1) / (stages.length + 1));
          await new Promise((resolve) => setTimeout(resolve, 700));
        }
        const { mockJob } = await import("@/lib/mock");
        setResult(mockJob.result);
        setView("result");
        return;
      }

      stop.current = pollJob(
        job.job_id,
        (status) => {
          setStage(status.stage);
          setProgress(status.progress);
        },
        (status) => {
          setResult(status.result);
          setView("result");
        },
        (message) => {
          setError(message);
          setView("upload");
        },
      );
    } catch (caught) {
      clearTimeout(wakeTimer);
      setWaking(false);
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not reach the server. Please try again.",
      );
      setView("upload");
    }
  }, []);

  const reset = () => {
    stop.current?.();
    setResult(null);
    setError(null);
    setProgress(0);
    setView("upload");
  };

  return (
    <AppShell collapsed={view !== "upload"} onBack={view === "result" ? reset : undefined}>
      {view === "upload" && <UploadScreen onStart={start} error={error} />}
      {view === "processing" && (
        <LoadingScreen stage={stage} progress={progress} waking={waking} />
      )}
      {view === "result" && result && (
        <MappingScreen result={result} onReset={reset} />
      )}
    </AppShell>
  );
}
