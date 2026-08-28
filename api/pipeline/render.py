"""Turn whatever the teacher uploaded into a list of page PNGs.

Both inputs can be a PDF or a stack of images. Everything downstream works on
rendered raster pages, so this is the only place that cares about the
difference.

Rendering DPI is a real accuracy lever: too low and the vision model misreads
handwriting, too high and we blow the free-tier request size. 150 DPI on A4
gives ~1240x1754, which is comfortably inside Gemini's image budget and legible
for handwriting. Raising it to 200 was tried and scored no better on the
hand-marked sheet, so it stays where the committed numbers were measured;
`VEDA_RENDER_DPI` moves it without an edit for anyone who wants to retest.

Every page then goes through `preprocess`, which deskews and evens out the
lighting when it measures that the page needs it. That happens here, and not
just before the upload, so that the cleaned page is the one everything shares:
the model reads it, `tighten.py` looks for ink in it, and the browser displays
it. Cleaning a copy for the model alone would put every returned box in a
coordinate frame no other component agrees with.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from . import preprocess as prep

log = logging.getLogger(__name__)

# Overridable so the accuracy harness can A/B a resolution change without an
# edit to source. 150 was the previous value and is what the committed numbers
# before this were measured at.
RENDER_DPI = int(os.environ.get("VEDA_RENDER_DPI", "150"))
MAX_EDGE = int(os.environ.get("VEDA_MAX_EDGE", "2200"))
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class RenderedPage:
    index: int
    path: Path
    width: int
    height: int
    # Text extracted from the PDF's own text layer, when it has one.
    # Printed question papers usually do; scanned answer sheets never do.
    text_layer: str = ""


def _finish(img: Image.Image, path: Path, page: int, src: Path) -> Image.Image:
    """Downscale, clean, and write the page image everything downstream uses."""
    img = _downscale(img)
    img, steps = prep.preprocess(img)
    if steps:
        log.info("cleaned page %s of %s: %s", page, src.name, steps)
    img.save(path, "PNG", optimize=True)
    return img


def _downscale(img: Image.Image) -> Image.Image:
    longest = max(img.width, img.height)
    if longest <= MAX_EDGE:
        return img
    scale = MAX_EDGE / longest
    return img.resize(
        (int(img.width * scale), int(img.height * scale)), Image.LANCZOS
    )


def render(src: Path, out_dir: Path, prefix: str) -> list[RenderedPage]:
    """Render `src` into `out_dir` as `{prefix}-{i}.png`, one file per page."""
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    if suffix in IMAGE_SUFFIXES:
        return _render_image(src, out_dir, prefix)
    if suffix == ".pdf":
        return _render_pdf(src, out_dir, prefix)

    # No usable extension (some browsers upload without one). Sniff it.
    head = src.open("rb").read(5)
    if head.startswith(b"%PDF"):
        return _render_pdf(src, out_dir, prefix)
    return _render_image(src, out_dir, prefix)


def _render_image(src: Path, out_dir: Path, prefix: str) -> list[RenderedPage]:
    img = Image.open(src)
    frames: list[Image.Image] = []

    # Multi-page TIFFs are a real thing in scanning workflows.
    try:
        while True:
            frames.append(img.convert("RGB").copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    if not frames:
        frames = [Image.open(src).convert("RGB")]

    pages: list[RenderedPage] = []
    for i, frame in enumerate(frames):
        path = out_dir / f"{prefix}-{i}.png"
        frame = _finish(frame, path, i, src)
        pages.append(RenderedPage(i, path, frame.width, frame.height))
    return pages


def _render_pdf(src: Path, out_dir: Path, prefix: str) -> list[RenderedPage]:
    doc = fitz.open(src)
    zoom = RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    pages: list[RenderedPage] = []
    for i, page in enumerate(doc):
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pixmap.tobytes("png")))
        path = out_dir / f"{prefix}-{i}.png"
        img = _finish(img, path, i, src)

        try:
            text = page.get_text("text") or ""
        except Exception:  # a malformed text layer shouldn't kill the render
            log.warning("text layer extraction failed on page %s of %s", i, src)
            text = ""

        pages.append(RenderedPage(i, path, img.width, img.height, text.strip()))
    doc.close()
    return pages


def has_text_layer(pages: list[RenderedPage]) -> bool:
    """True when the PDF carries enough real text to be worth trusting.

    A scanned page often carries a few stray characters from OCR artefacts, so
    we need a threshold rather than a simple non-empty check.
    """
    chars = sum(len(p.text_layer) for p in pages)
    return chars >= 200 * max(1, len(pages) // 2)
