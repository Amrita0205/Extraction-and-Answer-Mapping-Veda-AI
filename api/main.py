"""FastAPI entrypoint.

    uvicorn main:app --reload --port 8000

Endpoints:
    POST /api/jobs                              start a run
    GET  /api/jobs/{id}                         poll status, then result
    GET  /api/jobs/{id}/pages/{kind}/{i}.png    a rendered page
    GET  /api/health                            liveness, and a warm-up target
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline import gemini, jobs
from pipeline.schemas import JobStatus

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

MAX_UPLOAD = 10 * 1024 * 1024  # the design says "Max 10MB" on the dropzone

app = FastAPI(title="VedaAI — Extraction & Answer Mapping", version="1.0.0")

origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == "*" else [o.strip() for o in origins.split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "provider": gemini.PROVIDER,
        "model": os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        "ollama_model": gemini.OLLAMA_MODEL,
        "key_configured": gemini.PROVIDER == "ollama"
        or bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
    }


async def _read(upload: UploadFile, field: str) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(400, f"{field} was empty.")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(
            413, f"{field} is larger than the 10MB limit."
        )
    return data


@app.post("/api/jobs", response_model=JobStatus)
async def create_job(
    question_paper: UploadFile = File(...),
    answer_sheet: UploadFile = File(...),
) -> JobStatus:
    q = await _read(question_paper, "The question paper")
    a = await _read(answer_sheet, "The answer sheet")
    job = jobs.create(
        q, question_paper.filename or "question-paper.pdf",
        a, answer_sheet.filename or "answer-sheet.pdf",
    )
    return job.to_status()


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "That job has expired or never existed.")
    return job.to_status()


@app.get("/api/jobs/{job_id}/pages/{kind}/{index}.png")
def get_page(job_id: str, kind: str, index: int) -> FileResponse:
    path = jobs.page_path(job_id, kind, index)
    if path is None:
        raise HTTPException(404, "No such page.")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
