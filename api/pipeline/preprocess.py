"""Clean a scanned page before anything reads it.

Every misread on this project so far has been a misread *label* — an `8`
transcribed as a `7`, a zero-padded `05.` — and a misread label does not cost
one field, it costs the whole mapping for that question. Nothing downstream
recovers from it. So the cheapest remaining accuracy lever is upstream of the
model: hand it a better page.

Three operations:

    flatten     a photo has a bright side and a shadowed side; the model reads
                "dark region" where a person reads "shadow", and `tighten.py`
                thresholds against paper colour so it makes the same mistake
    stretch     faint pencil sits close to the paper value; pushing ink down
                and paper up is the difference between a legible 8 and a 7
    deskew      a phone photo is never square to the page, and text running
                diagonally across the crop is harder to read and produces
                boxes that do not line up with the writing

Deskew runs last, and that ordering is measured rather than aesthetic. On the
scanned sheets in `dataset/` the paper level swings by around 100 grey levels
across a single page, so before flattening more than half the page falls below
any sensible ink threshold and the angle search is reading the shadow instead
of the handwriting. Running it first put page 2 of the test sheet *further* off
square than it started. Flatten, then the mask is actually ink, and the same
search lands on the text lines.

None of it calls an API. The free tier limits *requests per day*, not pixels,
so this costs local CPU and nothing else. NumPy and Pillow only, both already
dependencies — no OpenCV, which would not fit the free deploy image.

The important property is that **every step is gated on measuring that the
page actually needs it**. A digitally generated PDF already has a pure white,
perfectly flat, perfectly square background, and every gate here declines on
it, so clean input passes through untouched. Preprocessing that fires
unconditionally is a way to make good scans worse.
"""

from __future__ import annotations

import logging
import os

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

# --- deskew ---------------------------------------------------------------
# Past 5 degrees it is not skew, it is a page fed in sideways, and a search
# that wide starts locking onto the wrong feature.
SKEW_LIMIT = 5.0
# Rotation resamples every pixel. Under a third of a degree the blur it costs
# is worth more than the alignment it buys.
SKEW_MIN = 0.35
SKEW_WIDTH = 640          # the angle search runs on a thumbnail, not the page
SKEW_MARGIN = 0.06        # ignore the corners, which rotate in and out of frame
SKEW_GAIN = 1.02          # the winner must beat "no rotation" by this much

# --- illumination ---------------------------------------------------------
TILE_ROWS = 32
TILE_COLS = 24
# Within one tile this percentile is paper, not ink. Handwriting is nowhere
# near 20% coverage of a tile this size; a solid diagram might be, and the
# floor below catches that case.
PAPER_PERCENTILE = 80
TARGET_PAPER = 245.0
FLAT_ENOUGH = 10.0        # background range under this needs no correction
BRIGHT_ENOUGH = 236.0     # ...and neither does one already this bright

# --- contrast -------------------------------------------------------------
# A sparse page is mostly paper, so the ink anchor has to sit well inside the
# ink. Half a percent of a 1650x2340 page is still ~19k pixels.
INK_PERCENTILE = 0.5
PAPER_ANCHOR = 96.0
STRETCH_MIN_SPREAD = 50.0
INK_FLOOR = 8.0
PAPER_CEIL = 250.0
# A page already using this much of the available range is left alone.
#
# This bar started at 0.90 and that was wrong, measurably. Flattening already
# lifts a shadowed scan to roughly 200 levels of separation, which cleared 0.55
# but not 0.90, so the stretch fired on pages that did not need it - and the
# thing it amplified was the show-through from the reverse side of thin
# notebook paper, which sits between ink and paper and gets pulled toward ink
# along with everything else. On the hand-marked sheet that cost 3.5 marks and
# turned a "Q15" into a "Q5". The stretch is a rescue for genuinely faint
# writing, not a default finish, so the bar belongs where only faint pages
# fall under it.
STRETCH_ENOUGH = 0.55


def enabled() -> bool:
    """`VEDA_PREPROCESS=0` turns the whole module off.

    This exists so the accuracy harness can run both arms of an A/B without
    editing code, which is the only honest way to decide whether any of this
    earns its place.
    """
    return os.getenv("VEDA_PREPROCESS", "1").lower() not in {"0", "false", "no"}


def preprocess(img: Image.Image) -> tuple[Image.Image, dict]:
    """Return a cleaned copy of `img`, plus a note of what was actually done.

    The note is for logging and for the eval report: "deskewed 1.8 degrees" is
    a claim you can check against the page, where "preprocessed" is not.
    """
    if not enabled():
        return img, {}

    img = img.convert("RGB")
    steps: dict = {}

    try:
        arr = np.asarray(img, dtype=np.float32)

        arr, spread = _flatten(arr, _luma(img))
        if spread is not None:
            steps["flatten_range"] = round(spread, 1)

        arr, ink = _stretch(arr)
        if ink is not None:
            steps["stretch_from_ink"] = round(ink, 1)

        if steps:
            img = Image.fromarray(arr.astype(np.uint8), "RGB")

        gray = _luma(img)
        angle = _skew_angle(gray)
        if abs(angle) >= SKEW_MIN:
            img = _rotate(img, angle, gray)
            steps["deskew_deg"] = round(angle, 2)

        return img, steps
    except Exception as exc:  # noqa: BLE001
        # A page that cannot be cleaned is still a page the model can read.
        # Never let cosmetic preprocessing take down an extraction run.
        log.warning("preprocessing failed, using the raw page: %s", exc)
        return img, {}


def _luma(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.float32)


# --------------------------------------------------------------------------
# deskew


def _skew_angle(gray: np.ndarray) -> float:
    """The rotation, in degrees, that best lines the text up with the rows.

    Projection profile: sum the ink in each row, and ask how spiky the result
    is. When the page is straight, every line of writing piles into a few rows
    and the gaps between lines stay empty, so the profile swings hard. Tilt it
    and each line smears across many rows, flattening the profile. Maximising
    the squared row-to-row difference finds the angle that separates the lines
    most cleanly, and it never has to detect a line of text to do it.
    """
    height, width = gray.shape
    if width < 200 or height < 200:
        return 0.0

    scale = SKEW_WIDTH / width
    small = Image.fromarray(gray.astype(np.uint8)).resize(
        (SKEW_WIDTH, max(1, int(height * scale))), Image.BILINEAR
    )
    thumb = np.asarray(small, dtype=np.float32)

    paper = float(np.percentile(thumb, 92))
    ink = float(np.percentile(thumb, 3))
    if paper - ink < 25:
        return 0.0  # blank, or too washed out to align to

    mask = Image.fromarray(
        ((thumb < paper - 0.45 * (paper - ink)) * 255).astype(np.uint8)
    )

    def score(angle: float) -> float:
        rotated = mask.rotate(angle, resample=Image.NEAREST, fillcolor=0)
        arr = np.asarray(rotated, dtype=np.float32)
        # The corners swing in and out of frame as the angle changes, which
        # would otherwise reward whichever angle happens to keep the most ink.
        my = int(SKEW_MARGIN * arr.shape[0])
        mx = int(SKEW_MARGIN * arr.shape[1])
        rows = arr[my : arr.shape[0] - my, mx : arr.shape[1] - mx].sum(axis=1)
        return float(np.square(np.diff(rows)).sum())

    base = score(0.0)
    if base <= 0:
        return 0.0

    coarse, _ = _best(score, np.arange(-SKEW_LIMIT, SKEW_LIMIT + 0.01, 0.5))
    best, value = _best(score, np.arange(coarse - 0.5, coarse + 0.51, 0.1))

    # Handwriting drifts, paper curls, and a genuinely straight page will still
    # show some angle as marginally "best". Require a real margin over doing
    # nothing before touching the pixels.
    if value < base * SKEW_GAIN:
        return 0.0
    return float(best)


def _best(score, angles) -> tuple[float, float]:
    scored = [(float(a), score(float(a))) for a in angles]
    return max(scored, key=lambda pair: pair[1])


def _rotate(img: Image.Image, angle: float, gray: np.ndarray) -> Image.Image:
    """Rotate, expanding the canvas so nothing is cropped off a corner.

    The wedges this opens at the corners are filled with the page's own paper
    colour rather than black, so the ink detection in `tighten.py` and the
    flattening below both see a plausible page rather than four dark triangles.
    """
    paper = int(np.clip(np.percentile(gray, 92), 0, 255))
    return img.rotate(
        angle,
        resample=Image.BICUBIC,
        expand=True,
        fillcolor=(paper, paper, paper),
    )


# --------------------------------------------------------------------------
# illumination


def _flatten(arr: np.ndarray, gray: np.ndarray) -> tuple[np.ndarray, float | None]:
    """Divide out the lighting, so paper reads the same value everywhere.

    The background is estimated on a coarse grid rather than by blurring,
    because a blur is dragged down by the ink sitting on top of it — a densely
    written paragraph would be estimated as darker paper and then brightened
    back towards illegibility. A high percentile within each tile ignores the
    ink entirely.
    """
    background = _background(gray)
    spread = float(background.max() - background.min())
    if spread < FLAT_ENOUGH and float(background.mean()) >= BRIGHT_ENOUGH:
        return arr, None  # already evenly lit — a generated PDF lands here

    gain = TARGET_PAPER / np.clip(background, 40.0, None)
    return np.clip(arr * gain[:, :, None], 0.0, 255.0), spread


def _background(gray: np.ndarray) -> np.ndarray:
    height, width = gray.shape
    ys = np.linspace(0, height, TILE_ROWS + 1).astype(int)
    xs = np.linspace(0, width, TILE_COLS + 1).astype(int)

    grid = np.full((TILE_ROWS, TILE_COLS), 255.0, dtype=np.float32)
    for r in range(TILE_ROWS):
        for c in range(TILE_COLS):
            tile = gray[ys[r] : ys[r + 1], xs[c] : xs[c + 1]]
            if tile.size:
                grid[r, c] = np.percentile(tile, PAPER_PERCENTILE)

    # A tile that is nothing but a solid diagram or a photograph has no paper
    # in it at all, and would otherwise be brightened into a white hole. Floor
    # the outliers at what the rest of the page calls paper.
    grid = np.maximum(grid, float(np.percentile(grid, 20)))

    smooth = Image.fromarray(grid, mode="F").resize((width, height), Image.BICUBIC)
    return np.asarray(smooth, dtype=np.float32)


# --------------------------------------------------------------------------
# contrast


def _stretch(arr: np.ndarray) -> tuple[np.ndarray, float | None]:
    """Pull the ink down and the paper up, without clipping either flat.

    Deliberately a linear stretch and not a threshold. Binarising is what most
    scanner software does and it is the wrong choice here: it destroys faint
    pencil, thin diagram strokes and the grey of a half-erased answer, all of
    which the model can still read as greys.
    """
    gray = arr.mean(axis=2)
    lo = float(np.percentile(gray, INK_PERCENTILE))
    hi = float(np.percentile(gray, PAPER_ANCHOR))

    span = hi - lo
    if span < STRETCH_MIN_SPREAD:
        return arr, None  # near-blank page; there is no ink to anchor to
    if span >= STRETCH_ENOUGH * (PAPER_CEIL - INK_FLOOR):
        return arr, None  # already spans the range

    scale = (PAPER_CEIL - INK_FLOOR) / span
    return np.clip((arr - lo) * scale + INK_FLOOR, 0.0, 255.0), lo
