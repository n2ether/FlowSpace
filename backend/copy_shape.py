"""Whole sentences and whole headings for customer copy.

Fitting copy into a card must never cut mid-phrase ("…and secure or.",
"INSTALL THE."). Clipping prefers a whole sentence, then a whole clause
outside parentheses, and never ends on an article, conjunction, or
preposition. Headings never take a period.
"""
from __future__ import annotations

import re
from typing import List

FUNCTION_WORDS = frozenset(
    """
    a an the and or but nor so yet of to for with without in on at by from into onto over under
    near beside between through toward towards about as than then if while when where which that
    this these those every each any all some no your our its his her their my is are was be been
    """.split()
)

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_CLAUSE = re.compile(r",\s|;\s|:\s|\s[—–]\s")


def _clean(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _last_word(text: str) -> str:
    words = re.findall(r"[A-Za-z']+", text)
    return words[-1].lower() if words else ""


def ends_dangling(text: str) -> bool:
    """True when copy ends on a function word ("secure or.", "Install the.")."""
    return _last_word(_clean(text).rstrip(".,;:!?—– ")) in FUNCTION_WORDS


def _strip_dangling(words: List[str]) -> List[str]:
    while words and re.sub(r"[^A-Za-z']", "", words[-1]).lower() in FUNCTION_WORDS:
        words = words[:-1]
    return words


def heading(text: str, max_words: int = 3) -> str:
    """A short heading from the first words of a line. No trailing function word, no period."""
    words = [w.strip(".,;:!?()") for w in _clean(text).split()]
    words = [w for w in words if w]
    picked = _strip_dangling(words[:max_words])
    if not picked:
        return ""
    size = max_words
    while len(picked) < 2 and size < min(len(words), max_words + 2):
        size += 1
        picked = _strip_dangling(words[:size]) or picked
    return " ".join(picked).rstrip(".,;:—– ")


def _outside_parens(text: str, index: int) -> bool:
    return text[:index].count("(") <= text[:index].count(")")


def complete_clip(text: str, max_words: int) -> str:
    """At most ``max_words`` words, ending on a whole sentence or clause. Always ends with a period."""
    text = _clean(text)
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    head = " ".join(words[:max_words])
    for match in reversed(list(_SENTENCE_END.finditer(head))):
        if match.start() >= len(head) * 0.3:
            return head[: match.end()]
    for match in reversed(list(_CLAUSE.finditer(head))):
        if match.start() >= len(head) * 0.4 and _outside_parens(head, match.start()):
            kept = _strip_dangling(head[: match.start()].split())
            if kept:
                return " ".join(kept).rstrip(".,;:—– ") + "."
    first = _SENTENCE_END.search(text)
    if first and len(text[: first.end()].split()) <= max_words + 4:
        return text[: first.end()]
    kept = _strip_dangling(head.split())
    joined = " ".join(kept).rstrip(".,;:—–( ")
    if joined.count("(") > joined.count(")"):
        joined = joined[: joined.rfind("(")].rstrip(" ,")
    return (joined or head).rstrip(".,;:—– ") + "."
