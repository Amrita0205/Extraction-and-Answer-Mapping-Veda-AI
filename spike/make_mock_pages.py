"""Generate the mock answer-sheet pages the frontend uses without a backend.

The blocks are drawn at exactly the fractional coordinates in
`web/src/lib/mock.ts`, so clicking a question in mock mode proves the overlay
maths lands on the right patch of paper before any AI is involved.

    python spike/make_mock_pages.py
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "mock"
W, H = 900, 1200
PAPER = (253, 252, 249)
RULE = (206, 219, 236)
MARGIN = (233, 173, 178)
INK = (36, 58, 132)

# (page, label, y0, y1) — must match mock.ts
BLOCKS = [
    (0, "Q1.", 0.100, 0.275),
    (0, "Q3.", 0.330, 0.515),
    (0, "Q2.", 0.570, 0.780),
    (1, "Q11 (a)", 0.080, 0.220),
    (1, "Q11 (b)", 0.270, 0.915),
    (2, "", 0.060, 0.300),
    (2, "Q14.", 0.360, 0.550),
    (2, "Q5.", 0.600, 0.850),
]
LINE_H = 34


def page_image(index: int) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    for y in range(120, H - 40, LINE_H):
        draw.line([(60, y), (W - 40, y)], fill=RULE, width=1)
    draw.line([(96, 40), (96, H - 40)], fill=MARGIN, width=2)
    draw.text((W - 120, 24), f"Page {index + 1}", fill=(150, 150, 150))
    return img


def scribble(draw: ImageDraw.ImageDraw, rng: random.Random, y0: int, y1: int) -> None:
    """Rows of short ink strokes — reads as handwriting at a glance and, more
    usefully, gives the ink-tightening pass something real to find."""
    y = y0
    while y < y1 - 8:
        x = 118
        right = W - 70 - rng.randint(0, 160)
        while x < right:
            word = rng.randint(26, 78)
            top = y + rng.randint(-2, 2)
            draw.line([(x, top + 12), (x + word, top + 12)], fill=INK, width=3)
            for _ in range(rng.randint(1, 3)):
                cx = x + rng.randint(0, max(1, word - 6))
                draw.line([(cx, top + 2), (cx + 4, top + 12)], fill=INK, width=2)
            x += word + rng.randint(10, 20)
        y += LINE_H


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)

    for index in range(3):
        img = page_image(index)
        draw = ImageDraw.Draw(img)
        for page, label, f0, f1 in BLOCKS:
            if page != index:
                continue
            y0, y1 = int(f0 * H), int(f1 * H)
            if label:
                draw.text((62, y0 + 6), label, fill=INK)
            scribble(draw, rng, y0 + 4, y1)
        path = OUT / f"answer-{index}.png"
        img.save(path, "PNG", optimize=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
