"""Thin wrapper over Gemini with the bits that matter for accuracy.

Two things in here are deliberate and easy to get wrong:

1.  **Box convention.** Gemini is trained to emit `box_2d` as
    `[ymin, xmin, ymax, xmax]` normalised to 0-1000. Asking for any other
    ordering or range measurably degrades localisation, so we ask for exactly
    that and convert on our side.

2.  **One page per request.** Batching several pages into a single call makes
    the model conflate page indices and drift on coordinates. Pages are cheap;
    correctness is not.
"""

from __future__ import annotations

import json
import logging
import os
import base64
import random
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

log = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

# The free tier grants 20 requests per day *per model*, so a single answer
# sheet (one call per page) can exhaust one model's daily allowance. Each name
# below has its own quota bucket, so we walk down the list when one runs dry.
#
# Order is by measured latency on a rendered A4 page, and the spread is not
# small: the two leaders answer in ~2.5s, while `gemini-flash-lite-latest`
# takes ~170s on the same page. That alias resolves to a thinking model *and*
# rejects `thinking_budget`, so its thinking cannot be turned off — which is
# why it is not in this list despite the promising name.
MODEL_FALLBACKS = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        "gemini-3.1-flash-lite,gemini-3.5-flash-lite,"
        "gemini-3.5-flash,gemini-3-flash-preview",
    ).split(",")
    if m.strip()
]

# Some models reject `thinking_budget` outright (400 INVALID_ARGUMENT). We only
# find out by asking, so remember which ones refused and stop sending it.
_no_thinking: set[str] = set()
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_client = None


class GeminiUnavailable(RuntimeError):
    pass


def client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "GOOGLE_API_KEY"
        )
        if not api_key:
            raise GeminiUnavailable(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey"
            )
        from google import genai

        _client = genai.Client(api_key=api_key)
    return _client


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json(text: str) -> Any:
    text = _strip_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Models occasionally trail a stray token after the closing brace.
        for opener, closer in (("[", "]"), ("{", "}")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise


def generate_json(
    prompt: str,
    images: list[Path] | None = None,
    *,
    temperature: float = 0.0,
    attempts: int = 4,
    thinking_budget: int | None = 0,
) -> Any:
    """Run a prompt (optionally with page images) and parse the JSON reply.

    Retries on transient errors and on unparseable JSON. Free-tier rate limits
    show up as 429s often enough that the backoff is not optional.
    """
    if PROVIDER == "ollama":
        return _generate_ollama(prompt, images, temperature=temperature)

    from google.genai import types as gt

    parts: list[Any] = []
    for image in images or []:
        parts.append(
            gt.Part.from_bytes(
                data=image.read_bytes(), mime_type="image/png"
            )
        )
    parts.append(gt.Part.from_text(text=prompt))

    def build_config(model: str) -> dict[str, Any]:
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "temperature": temperature,
        }
        # Extraction is a perception task, not a reasoning one. Thinking is not
        # a mild cost here: the same page takes 3s with the budget at zero and
        # 176s with it left at the default. Grading turns it back on.
        if thinking_budget is not None and model not in _no_thinking:
            config["thinking_config"] = gt.ThinkingConfig(
                thinking_budget=thinking_budget
            )
        return config

    # Try the configured model first, then the rest of the rotation.
    rotation = [MODEL] + [m for m in MODEL_FALLBACKS if m != MODEL]

    last: Exception | None = None
    for model in rotation:
        for attempt in range(attempts):
            try:
                response = client().models.generate_content(
                    model=model,
                    contents=[gt.Content(role="user", parts=parts)],
                    config=build_config(model),
                )
                return _parse_json(response.text or "")
            except GeminiUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - retry on anything transient
                last = exc
                text = str(exc)

                # The model refuses a thinking budget: drop it and re-ask once.
                if "INVALID_ARGUMENT" in text and model not in _no_thinking:
                    _no_thinking.add(model)
                    log.info("%s rejects thinking_budget — retrying without it", model)
                    continue

                # Daily quota gone, or the model is unavailable. Waiting will
                # not help; the next model has its own bucket.
                if "RESOURCE_EXHAUSTED" in text or "UNAVAILABLE" in text:
                    log.warning("%s is exhausted or unavailable — trying the next model", model)
                    break

                wait = min(2**attempt + random.random(), 20)
                log.warning(
                    "%s failed (attempt %s/%s): %s — retrying in %.1fs",
                    model,
                    attempt + 1,
                    attempts,
                    exc,
                    wait,
                )
                time.sleep(wait)

    raise RuntimeError(
        f"Every model in the rotation failed ({', '.join(rotation)}). Last error: {last}"
    )


def _generate_ollama(
    prompt: str,
    images: list[Path] | None,
    *,
    temperature: float,
) -> Any:
    """Call a local Ollama vision model using its OpenAI-like chat payload."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    encoded_images = [
        base64.b64encode(image.read_bytes()).decode("ascii")
        for image in images or []
    ]

    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "user", "content": prompt, "images": encoded_images}
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        }
    ).encode("utf-8")
    request = Request(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"Ollama is unavailable at {OLLAMA_BASE_URL}. "
            f"Start Ollama and pull {OLLAMA_MODEL}."
        ) from exc

    text = data.get("message", {}).get("content", "")
    if not text:
        raise RuntimeError("Ollama returned an empty response.")
    return _parse_json(text)


def box_to_fractions(box: Any) -> tuple[float, float, float, float] | None:
    """Convert Gemini's `[ymin, xmin, ymax, xmax]` 0-1000 box to (x0,y0,x1,y1).

    Returns None for anything malformed rather than raising — one bad box on
    one page should not sink the whole run.

    Length is checked as "at least four", not "exactly four", because the model
    sometimes flattens the neighbouring fields into the array and returns
    `[132, 118, 217, 858, false, false]` — the box, then the two continuation
    booleans. Insisting on exactly four threw away a *correct* box: those
    coordinates are within a percent of the true ink bounds. The caller then
    fell back to a whole-page rectangle, so the highlight silently became the
    entire sheet, which is the one failure mode a teacher notices immediately.
    """
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        return None
    try:
        ymin, xmin, ymax, xmax = (float(v) for v in box[:4])
    except (TypeError, ValueError):
        return None

    # Some responses come back already normalised to 0-1.
    scale = 1000.0 if max(ymin, xmin, ymax, xmax) > 1.5 else 1.0
    x0, y0 = xmin / scale, ymin / scale
    x1, y1 = xmax / scale, ymax / scale

    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0

    clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731
    x0, y0, x1, y1 = clamp(x0), clamp(y0), clamp(x1), clamp(y1)
    if x1 - x0 < 0.005 or y1 - y0 < 0.004:
        return None
    return x0, y0, x1, y1
