"""Whole sentences and whole headings for customer copy.

Fitting copy into a card must never cut mid-phrase ("…and secure or.",
"with calm.", "INSTALL THE."). Shortening stops only at a real sentence
boundary (.!?), never at a comma, semicolon, colon, or dash inside a phrase,
and never ends on an article, conjunction, or preposition. A sentence that
does not fit is kept whole so the caller can wrap it or shrink the type.
Headings never take a period.
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


def _sentence_prefixes(text: str) -> List[str]:
    """Text through each sentence end, in order. Commas and dashes are not ends."""
    prefixes: List[str] = []
    for match in _SENTENCE_END.finditer(text):
        prefix = text[: match.end()].strip()
        if prefix and prefix not in prefixes and not ends_dangling(prefix):
            prefixes.append(prefix)
    return prefixes


def shorten_whole(text: str, fits) -> str:
    """The longest leading run of whole sentences that ``fits``.

    A comma, semicolon, colon, or dash inside a sentence is never a cut, so
    "with calm, cohesive art" is never shortened to "with calm.". When the
    first sentence itself does not fit, that sentence (or the full text) is
    returned so the caller can wrap it or shrink the type.
    """
    text = _clean(text)
    if not text or fits(text):
        return text
    options = _sentence_prefixes(text)
    for option in reversed(options):
        if fits(option):
            return option
    if options:
        return options[0]
    return text


def complete_clip(text: str, max_words: int) -> str:
    """At most ``max_words`` words when whole leading sentences fit there.

    Otherwise the first whole sentence is kept, even if it is longer. A cut
    never lands on a comma inside a phrase, and never leaves a dangling modifier.
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
