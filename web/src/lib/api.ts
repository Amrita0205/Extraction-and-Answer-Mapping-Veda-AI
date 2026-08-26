import type { JobStatus } from "./types";
import { mockJob } from "./mock";

/**
 * With NEXT_PUBLIC_API_BASE unset the app serves the mock fixture, so the UI
 * can be developed and reviewed without a backend or an API key. Set it to the
 * deployed FastAPI origin to use the real pipeline.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "";
export const USING_MOCK = API_BASE === "";

/** Page URLs come back as API-relative paths; make them absolute. */
export function pageUrl(url: string): string {
  if (!url || url.startsWith("http") || url.startsWith("data:")) return url;
  return `${API_BASE}${url}`;
}

export async function createJob(
  questionPaper: File,
  answerSheet: File,
): Promise<JobStatus> {
  if (USING_MOCK) {
    await sleep(600);
    return { ...mockJob, status: "running", stage: "rendering", progress: 0.05 };
  }

  const body = new FormData();
  body.append("question_paper", questionPaper);
  body.append("answer_sheet", answerSheet);

  const response = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  if (USING_MOCK) {
    await sleep(400);
    return mockJob;
  }
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

/**
 * Poll until the job finishes.
 *
 * Polling rather than SSE: free-tier proxies buffer event streams
 * unpredictably, and a stream that dies mid-run is painful to diagnose from a
 * deployed URL. A 1.5s poll is boring and survives a cold start.
 */
export function pollJob(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  onDone: (status: JobStatus) => void,
  onError: (message: string) => void,
): () => void {
  let stopped = false;
  let failures = 0;

  const tick = async () => {
    if (stopped) return;
    try {
      const status = await getJob(jobId);
      failures = 0;
      if (stopped) return;
      onUpdate(status);
      if (status.status === "done") return onDone(status);
      if (status.status === "failed") {
        return onError(status.error ?? "The run failed.");
      }
    } catch (error) {
      failures += 1;
      // A sleeping free-tier instance refuses a few requests before it wakes.
      // Only give up once it has failed repeatedly.
      if (failures >= 8) {
        return onError(
          error instanceof Error ? error.message : "Lost contact with the server.",
        );
      }
    }
    setTimeout(tick, 1500);
  };

  void tick();
  return () => {
    stopped = true;
  };
}

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return data?.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
