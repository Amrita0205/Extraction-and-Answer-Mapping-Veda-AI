"""Parsing and comparing question labels.

The brief is explicit that `11 (a)` and `11 (b)` are two separate questions and
that the printed numbering must be preserved. That makes label handling the
single highest-leverage piece of string code in the project: it is what lets a
student's handwritten "Q11(b)" find its way to the right row even when the
answers are written out of order.
"""

from __future__ import annotations

import re
import unicodedata

ROMAN = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12,
}

# "Q11 (b)", "11.b)", "Question 11 - part b", "11 b.", "5(iii)"
_LABEL = re.compile(
    r"""
    ^\s*
    (?:q(?:u(?:es(?:tion)?)?)?\s*[\.\)\-:]?\s*)?   # optional Q / Ques / Question
    (?P<number>\d{1,3})                            # the printed number
    \s*[\.\)\-:]?\s*
    (?:                                            # optional sub-part
        \(\s*(?P<p1>[a-zA-Z]{1,4})\s*\)
      | \[\s*(?P<p2>[a-zA-Z]{1,4})\s*\]
      | (?:part\s+)?(?P<p3>[a-z])\s*[\.\)]         # bare "b)" / "b."
    )?
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_LEADING = re.compile(
    r"""^\s*
    (?:q(?:u(?:es(?:tion)?)?)?\s*[\.\)\-:]?\s*)?
    (?P<number>\d{1,3})
    \s*[\.\)\-:]?\s*
    (?:\(\s*(?P<p1>[a-zA-Z]{1,4})\s*\)|(?P<p3>[a-z])\s*[\.\)])?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return text.replace("–", "-").replace("—", "-").strip()


def parse(label: str | None) -> tuple[str | None, str | None]:
    """`"Q11 (b)"` -> `("11", "b")`. Returns `(None, None)` if it isn't a label."""
    if not label:
        return None, None
    match = _LABEL.match(_clean(label))
    if not match:
        return None, None
    return _normalise(match)


def parse_leading(text: str | None) -> tuple[str | None, str | None]:
    """Like `parse`, but tolerates the answer text following the label."""
    if not text:
        return None, None
    match = _LEADING.match(_clean(text))
    if not match:
        return None, None
    return _normalise(match)


# A sub-part written on its own: "(ii)", "ii)", "(b)". Students stop repeating
# the question number after the first sub-part, so most of an answer booklet is
# labelled this way.
_BARE_PART = re.compile(
    r"^\(?\s*(?P<part>[ivx]{1,4}|[a-z])\s*[\)\.\]]",
    re.IGNORECASE,
)
_HAS_NUMBER = re.compile(r"^\s*(?:q\w*\s*[\.\)\-:]?\s*)?\d", re.IGNORECASE)


def bare_part(label: str | None) -> str | None:
    """`"(ii)"` -> `"ii"`, but `"4. (i)"` -> `None` (it has its own number)."""
    if not label:
        return None
    text = _clean(label)
    if _HAS_NUMBER.match(text):
        return None
    match = _BARE_PART.match(text)
    return match.group("part").lower() if match else None


def _normalise(match: re.Match[str]) -> tuple[str | None, str | None]:
    number = match.group("number")
    part = (
        match.groupdict().get("p1")
        or match.groupdict().get("p2")
        or match.groupdict().get("p3")
    )
    if part:
        part = part.lower()
        # Keep roman numerals as written — "iii" is how the paper prints it.
        if part not in ROMAN and len(part) > 1:
            part = part[0]
    return number, part


_PART_TRIM = re.compile(r"[^a-z0-9]", re.IGNORECASE)


def clean_part(part: str | None) -> str:
    """`"(i)"`, `"i."`, `"[I]"` -> `"i"`.

    The two sides of a match arrive punctuated differently: the paper prints
    "(i)" and a model reading it keeps the brackets, while a label parsed off a
    student's answer comes back bare. Comparing those two strings directly is
    the difference between a question being matched and being reported as
    unanswered, so every comparison goes through here.
    """
    return _PART_TRIM.sub("", (part or "")).lower()


def key(number: str | None, part: str | None) -> str:
    """A stable identity for a question, used to join answers to questions."""
    n = (number or "").lstrip("0") or (number or "")
    return f"{n}|{clean_part(part)}"


def sort_key(number: str | None, part: str | None) -> tuple:
    """Sort by printed number, then sub-part, so the list reads like the paper."""
    try:
        n = int(number or 0)
    except ValueError:
        n = 0
    p = clean_part(part)
    if not p:
        rank = -1
    elif p in ROMAN:
        rank = ROMAN[p]
    elif len(p) == 1 and p.isalpha():
        rank = ord(p) - ord("a")
    else:
        rank = 99
    return (n, rank)


def display(number: str | None, part: str | None) -> str:
    return f"{number}({part})" if part else (number or "?")
