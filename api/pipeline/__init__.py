"""AI assessment extraction and answer mapping pipeline.

Environment variables are loaded here, once, before any module reads them —
`GEMINI_API_KEY` is needed by `gemini.py` and `ALLOWED_ORIGINS` by the app
itself, and both should work whether uvicorn is started from the repo root or
from `api/`. Real environment variables always win over the file, so a
deployed instance with the key set in Render's dashboard is unaffected.
"""

from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv

    _API = Path(__file__).resolve().parent.parent
    for _candidate in (_API.parent / ".env", _API / ".env"):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
except ImportError:  # python-dotenv is optional; real env vars still work
    pass
