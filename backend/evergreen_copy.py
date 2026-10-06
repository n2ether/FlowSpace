"""Customer copy stays evergreen.

A Blueprint is read again months later. Copy that names an age ("just turned
one"), a date, a week label ("Week 1", "this week"), or a countdown
("60 seconds", "one-minute") goes stale, so customer surfaces do not print it
unless it is essential. Safety temperatures (68–72°F), sizes, and prices are
not time-sensitive and stay.

``find_time_sensitive`` is the lint used by tests. ``evergreen_text`` rewrites
known phrases and drops a sentence that still names an age or a date.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_NUM = (
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"fifteen|twenty|thirty|forty[- ]?five|sixty|ninety)"
)
_MONTHS = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
)

AGE_PATTERNS = (
    re.compile(rf"\b(?:just\s+)?turn(?:ed|ing|s)?\s+{_NUM}\b", re.I),
    re.compile(rf"\bages?\s+{_NUM}\b", re.I),
    re.compile(rf"\b{_NUM}[-\s](?:years?|months?|weeks?)[-\s]old\b", re.I),
    re.compile(rf"\b{_NUM}\s+(?:years?|months?)\s+(?:old|of age)\b", re.I),
    re.compile(r"\b(?:first|1st|second|2nd|third|3rd)\s+birthday\b", re.I),
    re.compile(r"\bbirthday\b", re.I),
    re.compile(r"\bnewly\s+(?:mobile|walking|crawling)\b", re.I),
    re.compile(r"\b(?:toddler|newborn|infant|preschooler)s?\b", re.I),
)
DATE_PATTERNS = (
    # "May" alone is a modal verb; month names need a day, a year, or a season word.
    re.compile(rf"\b{_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b"),
    re.compile(rf"\b{_MONTHS}\s+(?:19|20)\d{{2}}\b"),
    re.compile(r"\b(?:January|February|March|April|June|July|August|September|October|November|December)\b"),
    re.compile(r"(?<![\d$.,])\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    re.compile(r"(?<![\d$.,×x])\b(?:19|20)\d{2}\b(?![\d×x])"),
    re.compile(r"\b(?:today|tonight|tomorrow|yesterday)\b", re.I),
)
WEEK_PATTERNS = (
    re.compile(rf"\b(?:week|day|month)\s+{_NUM}\b", re.I),
    re.compile(r"\b(?:this|next|last)\s+(?:week|month|weekend|year)\b", re.I),
)
DURATION_PATTERNS = (
    re.compile(rf"\b{_NUM}[-\s](?:seconds?|minutes?|mins?|hours?|hrs?)\b", re.I),
    re.compile(r"\b(?:a|one)\s+minute\b", re.I),
)

TIME_SENSITIVE_PATTERNS = AGE_PATTERNS + DATE_PATTERNS + WEEK_PATTERNS + DURATION_PATTERNS

# Phrase rewrites run before the sentence check, so a useful line survives.
_REWRITES = (
    (re.compile(r"\bone[-\s]minute\s+bedtime\s+ritual\b", re.I), "Bedtime ritual"),
    (re.compile(rf"\b{_NUM}[-\s]minute\s+(?:weekly\s+)?reset\b", re.I), "Quick reset"),
    (re.compile(r"\b(first\s+move)\s+(?:this|next)\s+week\b", re.I), r"\1"),
    (re.compile(r"\bmoves?\s+from\s+(?:toddler|baby|infant|newborn|child)\s+to\s+(?:preschooler|big[-\s]kid|toddler|school\s+age)\b", re.I), "grows"),
    (re.compile(r"\bthis\s+week\s*[—–-]\s*", re.I), ""),
    (re.compile(rf"\bweek\s+{_NUM}\s*[:—–-]\s*", re.I), ""),
    (re.compile(r"\b(?:this|next)\s+week\b", re.I), "first"),
    (re.compile(r"\bonce\s+a\s+week,?\s+take\s+" + _NUM + r"\s+minutes?\s+to\b", re.I), "Now and then,"),
    (re.compile(rf"\s*\b(?:in|within|under|about|for|takes?|of)\s+(?:about\s+|under\s+)?{_NUM}\s+(?:seconds?|minutes?|mins?|hours?)\b", re.I), ""),
    (re.compile(rf"\b{_NUM}[-\s](?:second|minute|hour)\s+", re.I), "quick "),
    (re.compile(r"\bnewly\s+(?:mobile|walking|crawling)\s+", re.I), ""),
    (re.compile(r"\ban\s+infant\b", re.I), "a child"),
    (re.compile(r"\b(?:toddler|newborn|infant)s\b", re.I), "children"),
    (re.compile(r"\b(?:toddler|newborn|infant)\b", re.I), "child"),
    (re.compile(r"\bJanuary\s+window\b", re.I), "window"),
    (re.compile(r"\b(?:the\s+)?(?:winter|january|february|december)\s+(?:cold|chill)\b", re.I), "the cold"),
    (re.compile(r"\b(?:December|January|February)\b(?!\s+\d)"), "winter"),
    (re.compile(r"\b(?:June|July|August)\b(?!\s+\d)"), "summer"),
    (re.compile(r"\b(?:September|October|November)\b(?!\s+\d)"), "fall"),
    (re.compile(r"\b(?:March|April)\b(?!\s+\d)"), "spring"),
)

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")

STORY_TEMPLATE = "As {child} grows, we kept the space familiar and gave every part a clear job."

# Customer-approved copy that keeps a duration on purpose. Printed exactly; the lint skips it.
BEDTIME_RITUAL_TITLE = "ONE-MINUTE BEDTIME RITUAL"
BEDTIME_RITUAL_BODY = (
    "Bring your baby into the ritual from the beginning. Calmly narrate the same sequence you move "
    "through together: resetting the rocker, keeping the crib clear, closing the curtains, and dimming "
    "the lights. Repeat the same goodnight phrase. Then turn on the sound machine at a gentle volume—or "
    "sing a familiar song—as you settle your baby.\n\n"
    "These cues help make bedtime easier to read, even when your baby resists sleep. By the time you sit "
    "in the rocker, the room is ready for feeding, connection, and rest."
)
EVERGREEN_EXCEPTIONS = (BEDTIME_RITUAL_TITLE, *BEDTIME_RITUAL_BODY.split("\n\n"))


def _without_exceptions(text: str) -> str:
    """Drop approved blocks, matching across any line wrapping a renderer added."""
    flat = " ".join(text.split())
    for block in EVERGREEN_EXCEPTIONS:
        flat = flat.replace(" ".join(block.split()), " ")
    return flat


def find_time_sensitive(text: Any) -> List[str]:
    """Every age, date, week label, or countdown phrase in ``text``."""
    blob = _without_exceptions(str(text or ""))
    hits: List[str] = []
    for pattern in TIME_SENSITIVE_PATTERNS:
        for match in pattern.finditer(blob):
            hits.append(match.group(0))
    return hits


def _tidy(text: str) -> str:
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])(?=[.!?])", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = " ".join(text.split()).strip()
    return text[:1].upper() + text[1:] if text else text


def evergreen_text(text: Any) -> str:
    """Rewrite known time phrases, then drop a sentence that still names an age or a date."""
    raw = str(text or "")
    if not raw.strip():
        return ""
    if not find_time_sensitive(raw):
        return raw
    out = raw
    for pattern, replacement in _REWRITES:
        out = pattern.sub(replacement, out)
    if not find_time_sensitive(out):
        return _tidy(out)
    kept: List[str] = []
    for match in _SENTENCE.findall(out):
        sentence = " ".join(match.split()).strip()
        if sentence and not find_time_sensitive(sentence):
            kept.append(sentence)
    return _tidy(" ".join(kept))


def project_story(child: str) -> str:
    child = " ".join(str(child or "").split())
    return STORY_TEMPLATE.format(child=child) if child else ""


_DOC_TEXT_KEYS = ("intro", "summary", "notes", "budget_note", "attachment_note", "project_story")
_DOC_LIST_KEYS = ("needs", "strategy", "action_plan", "benefits", "safety_lines")
_INSTRUCTION_TEXT_KEYS = ("start_here", "weekly_reset")
_INSTRUCTION_LIST_KEYS = ("do_this_week", "do_not")


def _clean_list(items: Any) -> List[str]:
    out: List[str] = []
    for item in items or []:
        text = evergreen_text(item)
        if text:
            out.append(text)
    return out


def apply_evergreen(deliverable: Dict[str, Any], *, child: Optional[str] = None) -> List[str]:
    """Mutate the customer copy of a deliverable in place. Returns issue strings.

    Shopping-list names are retailer product names and are left alone.
    When the plan names a child, the opening story is the evergreen template.
    """
    changed = False
    for key in _DOC_TEXT_KEYS:
        raw = deliverable.get(key)
        if isinstance(raw, str) and raw:
            updated = evergreen_text(raw)
            if updated != raw:
                deliverable[key] = updated
                changed = True
    for key in _DOC_LIST_KEYS:
        raw = deliverable.get(key)
        if isinstance(raw, list) and raw:
            updated = _clean_list(raw)
            if updated != [str(x) for x in raw]:
                deliverable[key] = updated
                changed = True
    for zone in deliverable.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        for key in ("title", "desc"):
            raw = str(zone.get(key) or "")
            updated = evergreen_text(raw)
            if updated != raw:
                zone[key] = updated
                changed = True
    layers = deliverable.get("blueprint_layers")
    if isinstance(layers, dict) and isinstance(layers.get("customer_instruction"), dict):
        inst = layers["customer_instruction"]
        for key in _INSTRUCTION_TEXT_KEYS:
            raw = inst.get(key)
            if isinstance(raw, str) and raw:
                updated = evergreen_text(raw)
                if updated != raw:
                    inst[key] = updated
                    changed = True
        for key in _INSTRUCTION_LIST_KEYS:
            raw = inst.get(key)
            if isinstance(raw, list) and raw:
                updated = _clean_list(raw)
                if updated != [str(x) for x in raw]:
                    inst[key] = updated
                    changed = True
    if child:
        story = project_story(child)
        if deliverable.get("project_story") != story:
            deliverable["project_story"] = story
        if deliverable.get("intro") != story:
            deliverable["intro"] = story
    return ["removed ages, dates, week labels, or countdowns from customer copy"] if changed else []


def evergreen_flow(flow: Dict[str, Any]) -> Dict[str, Any]:
    """Room-flow record copy (subtitle, zone jobs, flow note) without time-sensitive phrases."""
    for key in ("subtitle", "flow_note"):
        if isinstance(flow.get(key), str):
            flow[key] = evergreen_text(flow[key])
    if isinstance(flow.get("flow_principle"), list):
        flow["flow_principle"] = _clean_list(flow["flow_principle"])
    for zone in flow.get("zones") or []:
        if isinstance(zone, dict):
            for key in ("title", "job", "map_label"):
                if isinstance(zone.get(key), str):
                    zone[key] = evergreen_text(zone[key])
    return flow


DRAFTER_EVERGREEN_RULE = (
    "- Evergreen copy: customer-facing text must not include ages, birthdays, dates, month names, "
    "week labels (\"Week 1\", \"this week\"), or countdowns (\"60 seconds\", \"one-minute\", \"10-minute\") "
    "unless essential. Do not write \"just turned one\", \"age 1\", or \"newly mobile toddler\". "
    "Describe routines and steps without durations or calendar words.\n"
)
