"""Scoring for the evaluation harness.

Deliberately forgiving where handwriting is involved and strict where it is
not. Question labels either match or they don't, so extraction is scored on
exact set membership. Answer content is a transcription of someone's
handwriting, so mapping is scored on whether a distinctive phrase survived
rather than on string equality, which would punish the model for a comma.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


@dataclass
class Score:
    """One number plus the evidence behind it."""

    name: str
    hits: int = 0
    total: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def value(self) -> float:
        return self.hits / self.total if self.total else 0.0

    def line(self) -> str:
        pct = f"{100 * self.value:5.1f}%" if self.total else "    --"
        return f"{self.name:<28} {pct}  ({self.hits}/{self.total})"


def prf(predicted: set[str], expected: set[str]) -> tuple[float, float, float]:
    """Precision, recall, F1 over a set of labels."""
    if not predicted and not expected:
        return 1.0, 1.0, 1.0
    tp = len(predicted & expected)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def order_errors(predicted: list[str], expected: list[str]) -> int:
    """How many adjacent pairs come out in the wrong relative order.

    Counted over the labels present in both lists, so a missed question is
    charged to extraction rather than being double-counted here.
    """
    rank = {label: i for i, label in enumerate(expected)}
    seq = [rank[label] for label in predicted if label in rank]
    return sum(1 for a, b in zip(seq, seq[1:]) if a > b)


def band_iou(pred: tuple[float, float], true: tuple[float, float]) -> float:
    """Overlap of two vertical bands on a page, as intersection over union.

    Vertical only. Answers run the width of the page, so the y-extent is what
    a teacher actually judges, and a y-band is something a human can label in
    seconds by eye - which matters when the labelling budget is one evening.
    """
    lo = max(pred[0], true[0])
    hi = min(pred[1], true[1])
    inter = max(0.0, hi - lo)
    union = max(pred[1], pred[0]) - min(pred[0], pred[1])
    union += max(true[1], true[0]) - min(true[0], true[1])
    union -= inter
    return inter / union if union > 0 else 0.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2
