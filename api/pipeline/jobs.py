"""In-memory job store and the background runner that drives the pipeline.

The brief says no database is required and in-memory storage is sufficient, so
this is a dict plus a few daemon threads. Three concessions to running on a
free tier: jobs are evicted once there are more than `MAX_JOBS`, each job's
rendered pages live in a temp directory that is removed with it, and a new
upload cancels whatever was already running.

That last one is not tidiness. Extraction costs one request per page against a
quota of 20 per day per model, so a run the teacher walked away from — they
refreshed, or changed their mind about the subject — would quietly spend most
of a day's allowance producing a result nobody asked for any more.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
import uuid

from dataclasses import dataclass, field
from pathlib import Path

from . import answers as answers_mod
from . import grading, mapping
from . import questions as questions_mod
from . import render
from .schemas import JobStatus, PageInfo, Result

log = logging.getLogger(__name__)

MAX_JOBS = 12
MAX_CONCURRENT = 2
_lock = threading.Lock()

# Deliberately daemon threads rather than a ThreadPoolExecutor. The executor's
# workers are non-daemon and joined at interpreter exit, so a run in progress
# blocks shutdown — which means `uvicorn --reload` detects an edit, says
# "Reloading...", and then hangs until the sheet finishes, and Ctrl-C does the
# same. A run is disposable (nothing is persisted, and the client is told to
# start again), so it should never hold the process open.
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)


class Cancelled(Exception):
    """Raised inside a worker when its job has been superseded or cancelled."""


@dataclass
class Job:
    id: str
    dir: Path
    cancelled: bool = False
    status: str = "queued"
    stage: str = "queued"
    progress: float = 0.0
    message: str = "Waiting to start"
    error: str | None = None
    result: Result | None = None
    created: float = field(default_factory=time.time)

    def to_status(self) -> JobStatus:
        return JobStatus(
            job_id=self.id,
            status=self.status,  # type: ignore[arg-type]
            stage=self.stage,  # type: ignore[arg-type]
            progress=self.progress,
            message=self.message,
            error=self.error,
            result=self.result,
        )


_jobs: dict[str, Job] = {}


def create(question_bytes: bytes, question_name: str,
           answer_bytes: bytes, answer_name: str) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job_dir = Path(tempfile.mkdtemp(prefix=f"veda-{job_id}-"))

    (job_dir / "question").mkdir()
    (job_dir / "answer").mkdir()
    q_path = job_dir / "question" / _safe(question_name, "question-paper.pdf")
    a_path = job_dir / "answer" / _safe(answer_name, "answer-sheet.pdf")
    q_path.write_bytes(question_bytes)
    a_path.write_bytes(answer_bytes)

    job = Job(id=job_id, dir=job_dir)
    with _lock:
        # A new upload supersedes whatever was already running. The brief
        # describes one teacher marking one sheet, so there is no case where
        # two runs are both wanted — and a run the user has walked away from
        # (they refreshed, or uploaded a different subject) is not free: it
        # keeps issuing one request per page against a quota of 20 per day per
        # model. Left alone, an abandoned 18-page sheet burns most of a day's
        # allowance to produce a result nobody will look at.
        superseded = [j for j in _jobs.values() if j.status in ("queued", "running")]
        for old in superseded:
            old.cancelled = True
            log.info("[%s] superseded by %s — cancelling", old.id, job_id)
        _jobs[job_id] = job
        _evict()
    threading.Thread(
        target=_queued_run,
        args=(job, q_path, a_path),
        name=f"veda-job-{job_id}",
        daemon=True,
    ).start()
    return job


def _queued_run(job: Job, q_path: Path, a_path: Path) -> None:
    """Wait for a free slot, then run — unless the job was cancelled while waiting."""
    with _slots:
        if job.cancelled:
            job.status, job.stage = "cancelled", "cancelled"
            job.message = "Stopped — a newer upload replaced this one"
            shutil.rmtree(job.dir, ignore_errors=True)
            return
        _run(job, q_path, a_path)


def cancel(job_id: str) -> Job | None:
    """Stop a run that is still in flight. Finished jobs are left alone."""
    job = _jobs.get(job_id)
    if job is None:
        return None
    if job.status in ("queued", "running"):
        job.cancelled = True
        log.info("[%s] cancelled by request", job_id)
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def page_path(job_id: str, kind: str, index: int) -> Path | None:
    job = _jobs.get(job_id)
    if job is None or kind not in ("question", "answer"):
        return None
    path = job.dir / "pages" / f"{kind}-{index}.png"
    return path if path.exists() else None


def _safe(name: str, fallback: str) -> str:
    name = (name or "").strip().replace("/", "_").replace("\\", "_")
    return name[-80:] or fallback


def _evict() -> None:
    if len(_jobs) <= MAX_JOBS:
        return
    for job in sorted(_jobs.values(), key=lambda j: j.created)[: len(_jobs) - MAX_JOBS]:
        _jobs.pop(job.id, None)
        shutil.rmtree(job.dir, ignore_errors=True)


def _set(job: Job, stage: str, progress: float, message: str) -> None:
    job.stage, job.progress, job.message = stage, progress, message
    job.status = "running"
    log.info("[%s] %s — %s", job.id, stage, message)


def _run(job: Job, q_path: Path, a_path: Path) -> None:
    def check() -> None:
        """Abort at the next safe point if this job has been superseded.

        Called between stages and, more importantly, between pages: answer
        extraction is one request per page, so a check that only ran between
        stages would still let a cancelled 18-page sheet spend its whole
        quota before noticing.
        """
        if job.cancelled:
            raise Cancelled

    try:
        pages_dir = job.dir / "pages"

        _set(job, "rendering", 0.06, "Reading your files")
        check()
        q_pages = render.render(q_path, pages_dir, "question")
        a_pages = render.render(a_path, pages_dir, "answer")
        if not q_pages or not a_pages:
            raise ValueError(
                "One of the uploads had no readable pages. Please upload a PDF "
                "or an image."
            )

        _set(job, "extracting_questions", 0.22, "Extracting questions")
        questions, w1 = questions_mod.extract(q_pages, check)

        _set(job, "extracting_answers", 0.48, "Reading the answer sheet")
        blocks, w2 = answers_mod.extract(a_pages, check)

        _set(job, "mapping", 0.72, "Matching answers to questions")
        check()
        questions, unmatched, w3 = mapping.map_answers(questions, blocks)

        _set(job, "grading", 0.86, "Marking and writing feedback")
        check()
        graded, overall, w4 = grading.grade(questions)
        summary = grading.summarise(questions, unmatched, graded, overall)

        job.result = Result(
            questions=questions,
            unmatched_answers=unmatched,
            question_pages=_page_infos(job.id, "question", q_pages),
            answer_pages=_page_infos(job.id, "answer", a_pages),
            summary=summary,
            warnings=[*w1, *w2, *w3, *w4],
        )
        job.status, job.stage, job.progress = "done", "done", 1.0
        job.message = "Ready"
    except Cancelled:
        log.info("[%s] stopped early", job.id)
        job.status, job.stage = "cancelled", "cancelled"
        job.message = "Stopped — a newer upload replaced this one"
        # The pages are the bulk of a job's disk use and nothing will read
        # them again, so drop them now rather than waiting for eviction.
        shutil.rmtree(job.dir, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        log.exception("[%s] pipeline failed", job.id)
        job.status, job.stage = "failed", "failed"
        job.error = str(exc)
        job.message = "Something went wrong"


def _page_infos(job_id: str, kind: str, pages) -> list[PageInfo]:
    return [
        PageInfo(
            index=p.index,
            width=p.width,
            height=p.height,
            url=f"/api/jobs/{job_id}/pages/{kind}/{p.index}.png",
        )
        for p in pages
    ]
