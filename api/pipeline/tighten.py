"""Snap a proposed answer box onto the actual ink.

Vision models place a box in roughly the right place and then miss the edges —
usually by including a band of blank ruled paper under the last line, sometimes
by clipping a descender or the first character of a label. Either way the
highlight looks wrong to a teacher, and "correct highlighting of answers" is
one of the things being marked.

The fix is cheap and does not involve the model at all. Take the proposal, grow
it slightly, find the pixels that are actually darker than the paper, discard
the printed ruling, and crop to what is left.

No OpenCV — Pillow plus NumPy keeps the deploy image small enough for a free
tier, and the operation is a couple of array reductions.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

# How far outside the proposal we look for ink the model may have clipped.
SEARCH_PAD = 0.02
# Breathing room left around the ink so the highlight doesn't graze the letters.
INK_PAD_X = 0.008
INK_PAD_Y = 0.006
# A legitimately loose proposal can shrink a long way — a box drawn round a
# whole page for two lines of writing is exactly the case this exists to fix —
# so the sanity check is on the absolute size of the result, not on how much it
# shrank. Anything smaller than a couple of words is treated as a detection
# failure and the proposal is kept instead.
MIN_WIDTH = 0.02
MIN_HEIGHT = 0.006
MIN_AREA_RATIO = 0.02


@lru_cache(maxsize=32)
def _load(path: str) -> np.ndarray:
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32)


def tighten(
    page_path: Path, box: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    """Return a box in page fractions cropped to the ink inside `box`."""
    x0, y0, x1, y1 = box
    try:
        gray = _load(str(page_path))
    except Exception as exc:  # noqa: BLE001
        log.warning("could not open %s for tightening: %s", page_path, exc)
        return box

    height, width = gray.shape
    sx0 = int(max(0.0, x0 - SEARCH_PAD) * width)
    sy0 = int(max(0.0, y0 - SEARCH_PAD) * height)
    sx1 = int(min(1.0, x1 + SEARCH_PAD) * width)
    sy1 = int(min(1.0, y1 + SEARCH_PAD) * height)
    if sx1 - sx0 < 8 or sy1 - sy0 < 8:
        return box

    crop = gray[sy0:sy1, sx0:sx1]
    mask = _ink_mask(crop)
    mask = _drop_rules(mask)

    rows = mask.sum(axis=1)
    cols = mask.sum(axis=0)
    if rows.max() < 2 or cols.max() < 2:
        return box  # nothing legible in there — leave the proposal alone

    r0, r1 = _extent(rows)
    c0, c1 = _extent(cols)
    if r1 <= r0 or c1 <= c0:
        return box

    nx0 = (sx0 + c0) / width - INK_PAD_X
    nx1 = (sx0 + c1) / width + INK_PAD_X
    ny0 = (sy0 + r0) / height - INK_PAD_Y
    ny1 = (sy0 + r1) / height + INK_PAD_Y

    clamp = lambda v: float(max(0.0, min(1.0, v)))  # noqa: E731
    tightened = (clamp(nx0), clamp(ny0), clamp(nx1), clamp(ny1))

    width_out = tightened[2] - tightened[0]
    height_out = tightened[3] - tightened[1]
    before = max(1e-6, (x1 - x0) * (y1 - y0))
    if (
        width_out < MIN_WIDTH
        or height_out < MIN_HEIGHT
        or (width_out * height_out) / before < MIN_AREA_RATIO
    ):
        log.debug("tightening rejected as implausible: %s -> %s", box, tightened)
        return box
    return tightened


def _ink_mask(crop: np.ndarray) -> np.ndarray:
    """Pixels meaningfully darker than the paper around them."""
    paper = float(np.percentile(crop, 92))
    darkest = float(np.percentile(crop, 3))
    # A blank crop has almost no spread; refuse to invent ink in it.
    if paper - darkest < 18:
        return np.zeros_like(crop, dtype=bool)
    threshold = paper - max(26.0, 0.42 * (paper - darkest))
    return crop < threshold


def _drop_rules(mask: np.ndarray) -> np.ndarray:
    """Remove the printed ruling and the margin line.

    A rule is a near-unbroken run across most of the crop. Handwriting, even a
    dense line of it, breaks up into words. Measuring the longest run rather
    than the total count is what separates the two.
    """
    height, width = mask.shape

    # Both passes measure the ORIGINAL mask. Clearing rows first would chop the
    # margin line into short segments — one per gap between ruled lines — and
    # the column pass would then never recognise it as a rule.
    rule_rows = [i for i in range(height) if _longest_run(mask[i]) > 0.62 * width]
    rule_cols = [
        j for j in range(width) if _longest_run(mask[:, j]) > 0.62 * height
    ]

    mask = mask.copy()
    for i in rule_rows:
        mask[i] = False
    for j in rule_cols:
        mask[:, j] = False
    return mask


def _longest_run(line: np.ndarray) -> int:
    if not line.any():
        return 0
    # Positions where the value changes, so runs can be measured in one pass.
    padded = np.concatenate(([False], line, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    if edges.size < 2:
        return 0
    runs = edges[1::2] - edges[::2]
    return int(runs.max()) if runs.size else 0


def _extent(profile: np.ndarray) -> tuple[int, int]:
    """First and last index carrying a non-trivial amount of ink."""
    peak = float(profile.max())
    floor = max(1.5, 0.035 * peak)
    hits = np.flatnonzero(profile >= floor)
    if hits.size == 0:
        return 0, 0
    return int(hits[0]), int(hits[-1] + 1)
