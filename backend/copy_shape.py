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


_TITLE_BREAK = frozenset(
    """
    by at in on near beside between for with without from into onto under over along across
    so to that which where when while because using
    """.split()
)


def whole_title(text: str, max_words: int = 5) -> str:
    """A complete title: the whole phrase when short, else the phrase up to its first natural break.

    "Create a drop zone by the entry for keys" becomes "Create a drop zone", never
    "Create a drop" or "Create a drop zone by the.". No trailing period.
    """
    cleaned = _clean(re.sub(r"\s*\([^)]*\)", "", _clean(text)))
    cleaned = re.split(r"[.!?;:]\s|\s[—–]\s|,\s", cleaned + " ", maxsplit=1)[0].strip().rstrip(".!?;:,")
    words = cleaned.split()
    if not words:
        return ""
    if len(words) <= max_words and not ends_dangling(cleaned):
        return cleaned
    for index, word in enumerate(words):
        if index >= 2 and word.lower().strip(".,") in _TITLE_BREAK:
            picked = _strip_dangling(words[:index])
            if 2 <= len(picked) <= max_words:
                return " ".join(picked)
            break
    picked = _strip_dangling(words[:max_words])
    return " ".join(picked or words[:max_words]).rstrip(".,;:—– ")


def _outside_parens(text: str, index: int) -> bool:
    return text[:index].count("(") <= text[:index].count(")")


def _clause_options(text: str) -> List[str]:
    """Whole sentences, then whole clauses. Nothing here ends mid-sentence."""
    options: List[str] = []
    for match in _SENTENCE_END.finditer(text):
        options.append(text[: match.end()])
    for match in _CLAUSE.finditer(text):
        if not _outside_parens(text, match.start()):
            continue
        kept = _strip_dangling(text[: match.start()].split())
        if len(kept) >= 3:
            options.append(" ".join(kept).rstrip(".,;:—– ") + ".")
    unique: List[str] = []
    for option in options:
        if option and option not in unique and not ends_dangling(option):
            unique.append(option)
    return unique


def shorten_whole(text: str, fits) -> str:
    """The longest whole sentence or clause that ``fits``.

    A fragment such as "warmth and tie." is never returned. When no shorter
    unit fits, the first whole sentence (or the full text) is returned so the
    caller can wrap it or set the type size before drawing.
    """
    text = _clean(text)
    if not text or fits(text):
        return text
    options = sorted(_clause_options(text), key=len, reverse=True)
    for option in options:
        if fits(option):
            return option
    if options:
        return options[-1]
    return text


def complete_clip(text: str, max_words: int) -> str:
    """At most ``max_words`` words when a whole sentence or clause fits there.

    Otherwise the first whole sentence is kept, even if it is longer, instead of
    a mid-sentence fragment with a period glued on.
    """
    text = _clean(text)
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text

    def fits(value: str) -> bool:
        return len(value.split()) <= max_words

    shortened = shorten_whole(text, fits)
    if shortened != text and fits(shortened):
        return shortened
    first = _SENTENCE_END.search(text)
    if first:
        return text[: first.end()]
    return text
