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
import random
import re
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
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
    from google.genai import types as gt

    parts: list[Any] = []
    for image in images or []:
        parts.append(
            gt.Part.from_bytes(
                data=image.read_bytes(), mime_type="image/png"
            )
        )
    parts.append(gt.Part.from_text(text=prompt))

    config: dict[str, Any] = {
        "response_mime_type": "application/json",
        "temperature": temperature,
    }
    # Extraction is a perception task, not a reasoning one — thinking tokens
    # mostly cost latency here. Grading turns it back on.
    if thinking_budget is not None:
        try:
            config["thinking_config"] = gt.ThinkingConfig(
                thinking_budget=thinking_budget
            )
        except Exception:
            pass

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            response = client().models.generate_content(
                model=MODEL,
                contents=[gt.Content(role="user", parts=parts)],
                config=config,
            )
            return _parse_json(response.text or "")
        except GeminiUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - retry on anything transient
            last = exc
            wait = min(2**attempt + random.random(), 20)
            log.warning(
                "gemini call failed (attempt %s/%s): %s — retrying in %.1fs",
                attempt + 1,
                attempts,
                exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(f"Gemini call failed after {attempts} attempts: {last}")


def box_to_fractions(box: Any) -> tuple[float, float, float, float] | None:
    """Convert Gemini's `[ymin, xmin, ymax, xmax]` 0-1000 box to (x0,y0,x1,y1).

    Returns None for anything malformed rather than raising — one bad box on
    one page should not sink the whole run.
    """
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        ymin, xmin, ymax, xmax = (float(v) for v in box)
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
