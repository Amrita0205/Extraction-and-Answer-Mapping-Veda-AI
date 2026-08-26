"""Ten-minute check on the one assumption everything else rests on.

The highlight is only as good as the boxes coming back from the model. This
script runs the real extraction path over one answer sheet and writes out each
page with two overlays: the model's raw proposal in red, and the tightened box
in green. Open the PNGs and look.

    GEMINI_API_KEY=... python spike/box_accuracy_spike.py path/to/answer_sheet.pdf

Writes to spike/out/. If the green boxes hug the handwriting, the pipeline's
assumptions hold. If they don't, the numbers printed at the end say which knob
in tighten.py to reach for.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from PIL import Image, ImageDraw  # noqa: E402

from pipeline import gemini, render  # noqa: E402
from pipeline.answers import _PROMPT  # noqa: E402
from pipeline.tighten import tighten  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    src = Path(sys.argv[1]).expanduser()
    if not src.exists():
        print(f"No such file: {src}")
        return 2

    OUT.mkdir(exist_ok=True)
    pages = render.render(src, OUT / "pages", "answer")
    print(f"Rendered {len(pages)} page(s) at {render.RENDER_DPI} DPI\n")

    total, shrunk, missing = 0, 0, 0
    for page in pages:
        try:
            data = gemini.generate_json(
                _PROMPT.format(index=page.index), images=[page.path]
            )
        except Exception as exc:  # noqa: BLE001
            print(f"page {page.index}: extraction failed — {exc}")
            continue

        blocks = data.get("blocks", []) if isinstance(data, dict) else data or []
        image = Image.open(page.path).convert("RGB")
        draw = ImageDraw.Draw(image)

        for block in blocks:
            raw = gemini.box_to_fractions(block.get("box_2d"))
            if raw is None:
                missing += 1
                print(f"  page {page.index}: no usable box for {block.get('label')!r}")
                continue
            total += 1
            fitted = tighten(page.path, raw)

            draw.rectangle(_px(raw, image), outline=(220, 60, 40), width=3)
            draw.rectangle(_px(fitted, image), outline=(50, 200, 30), width=3)
            draw.text(
                (_px(fitted, image)[0] + 4, max(2, _px(fitted, image)[1] - 14)),
                str(block.get("label") or "?"),
                fill=(20, 120, 10),
            )

            before = (raw[2] - raw[0]) * (raw[3] - raw[1])
            after = (fitted[2] - fitted[0]) * (fitted[3] - fitted[1])
            change = 100 * (1 - after / before) if before else 0
            if change > 8:
                shrunk += 1
            print(
                f"  page {page.index}  {str(block.get('label') or '-'):>8}  "
                f"raw={_fmt(raw)}  fitted={_fmt(fitted)}  "
                f"tightened {change:5.1f}%"
            )

        out_path = OUT / f"overlay-{page.index}.png"
        image.save(out_path)
        print(f"page {page.index}: wrote {out_path}\n")

    print("-" * 60)
    print(f"blocks with a usable box : {total}")
    print(f"boxes tightened >8%      : {shrunk}")
    print(f"boxes the model missed   : {missing}")
    print(
        "\nOpen the overlay PNGs. Red is what the model proposed, green is what\n"
        "the pipeline will highlight. Green should hug the handwriting with a\n"
        "hairline of margin and no band of blank paper underneath."
    )
    return 0


def _px(box, image):
    x0, y0, x1, y1 = box
    return (
        int(x0 * image.width), int(y0 * image.height),
        int(x1 * image.width), int(y1 * image.height),
    )


def _fmt(box) -> str:
    return "(" + ", ".join(f"{v:.3f}" for v in box) + ")"


if __name__ == "__main__":
    raise SystemExit(main())
