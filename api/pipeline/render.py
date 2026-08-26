"""Turn whatever the teacher uploaded into a list of page PNGs.

Both inputs can be a PDF or a stack of images. Everything downstream works on
rendered raster pages, so this is the only place that cares about the
difference.

Rendering DPI is a real accuracy lever: too low and the vision model misreads
handwriting, too high and we blow the free-tier request size. 150 DPI on A4
gives ~1240x1754, which is comfortably inside Gemini's image budget and legible
for handwriting.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

log = logging.getLogger(__name__)

RENDER_DPI = 150
MAX_EDGE = 2200  # hard cap so a huge scan can't blow up memory or upload size
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
        frame = _downscale(frame)
        path = out_dir / f"{prefix}-{i}.png"
        frame.save(path, "PNG", optimize=True)
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
        img = _downscale(img)
        path = out_dir / f"{prefix}-{i}.png"
        img.save(path, "PNG", optimize=True)

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
