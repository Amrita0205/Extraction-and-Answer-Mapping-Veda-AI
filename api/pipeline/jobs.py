"""In-memory job store and the background runner that drives the pipeline.

The brief says no database is required and in-memory storage is sufficient, so
this is a dict plus a thread pool. Two concessions to running on a free tier:
jobs are evicted once there are more than `MAX_JOBS`, and each job's rendered
pages live in a temp directory that is removed with it.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import answers as answers_mod
from . import grading, mapping
from . import questions as questions_mod
from . import render
from .schemas import JobStatus, PageInfo, Result

log = logging.getLogger(__name__)

MAX_JOBS = 12
_executor = ThreadPoolExecutor(max_workers=2)
_lock = threading.Lock()


@dataclass
class Job:
    id: str
    dir: Path
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
        _jobs[job_id] = job
        _evict()
    _executor.submit(_run, job, q_path, a_path)
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
    try:
        pages_dir = job.dir / "pages"

        _set(job, "rendering", 0.06, "Reading your files")
        q_pages = render.render(q_path, pages_dir, "question")
        a_pages = render.render(a_path, pages_dir, "answer")
        if not q_pages or not a_pages:
            raise ValueError(
                "One of the uploads had no readable pages. Please upload a PDF "
                "or an image."
            )

        _set(job, "extracting_questions", 0.22, "Extracting questions")
        questions, w1 = questions_mod.extract(q_pages)

        _set(job, "extracting_answers", 0.48, "Reading the answer sheet")
        blocks, w2 = answers_mod.extract(a_pages)

        _set(job, "mapping", 0.72, "Matching answers to questions")
        questions, unmatched, w3 = mapping.map_answers(questions, blocks)

        _set(job, "grading", 0.86, "Marking and writing feedback")
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
