"""One shared item list per project: what stays fixed, what the brief asks for, what we add.

Every after image, the Design Plan, the Room Flow map, the Companion Guide, and
the shopping list read the same three lists from here, so a view cannot show a
rug the text never mentions, and the text cannot promise art no view shows:

- ``fixed_items``: furniture and built-ins that stay. Their structure (doors,
  drawers, shelves, finish) is written once and repeated in every view's
  prompt and QA check. Sources: the drafter's ``fixed_items`` (derived from all
  room photos), the customer's "keep" answers, and "keep existing X" in the brief.
- ``brief_requests``: what the customer or the admin brief explicitly asked for
  (open budget, larger art, a rug, cozy touches, a set table, …) and which
  existing pieces they want kept.
- ``planned_additions``: every new visible item. Brief requests first, then the
  shopping list. The image prompt allows these and nothing else beyond small
  accessories.

- ``avoid_rules``: what no view may show ("basket on Sam's bed").

``room_inventory`` bundles these with the wall rule and the one effective
budget, plus a hash of everything an after depends on. Each view's QA and the
cross-view comparison record the hash and the image they covered.

``consistency_report`` compares the plan text, the shopping rows, the per-view
and cross-view results, the budget, and the customer copy against the
inventory and returns issues. A ``block`` issue stops the customer final send
(``final_send_block_reason``); ``NON_OVERRIDABLE`` blocks cannot be overridden.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ──────────────────────────── Text sources ─────────────────────────────

_LEAD_TEXT_KEYS = (
    "biggest_challenge",
    "goals",
    "notes",
    "daily_improvement",
    "bothers_other",
    "feeling_other",
    "must_stay",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def brief_notes(lead: Optional[Dict[str, Any]]) -> str:
    """The admin brief notes for this project (``lead.brief.notes``). Empty when none."""
    brief = (lead or {}).get("brief")
    if isinstance(brief, dict):
        return _clean(brief.get("notes"))
    return _clean(brief) if isinstance(brief, str) else ""


def request_text(lead: Optional[Dict[str, Any]]) -> str:
    """Every sentence the customer or the brief wrote about this room."""
    lead = lead or {}
    parts = [_clean(lead.get(key)) for key in _LEAD_TEXT_KEYS]
    intake = lead.get("intake") if isinstance(lead.get("intake"), dict) else {}
    for key in ("specifics", "change_avoid", "keep_items", "limit_other"):
        parts.append(_clean(intake.get(key)))
    answers = intake.get("space_answers") if isinstance(intake.get("space_answers"), dict) else {}
    parts.append(_clean(answers.get("text")))
    parts.append(brief_notes(lead))
    seen: List[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return "\n".join(seen)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text or "") if s.strip()]


_NEGATION = re.compile(r"\b(?:no|not|don'?t|do not|without|never|avoid|skip|nothing)\b[^.!?;]{0,25}$", re.I)


def _negated(sentence: str, start: int) -> bool:
    return bool(_NEGATION.search(sentence[:start]))


# ──────────────────────────── Brief requests ─────────────────────────────

OPEN_BUDGET_RE = re.compile(
    r"\bopen\s+budget\b|\bno\s+(?:budget\s+)?(?:cap|limit|ceiling)\b|\bbudget\s+is\s+open\b|"
    r"\bunlimited\s+budget\b|\bbudget\s*:\s*open\b|\bno\s+spending\s+(?:cap|limit)\b",
    re.I,
)

# kind → (label for prompts and documents, request pattern, words that count as "planned")
DECOR_KINDS: Tuple[Tuple[str, str, re.Pattern, re.Pattern], ...] = (
    (
        "art",
        "Larger wall art",
        re.compile(
            r"\b(?:larger|bigger|large|big|statement|new|more|add(?:ing)?|hang(?:ing)?|want|need)\b[^.!?;]{0,30}"
            r"\b(?:art|artwork|art\s?piece|print|painting|canvas|gallery\s+wall|wall\s+(?:art|decor|décor))\b"
            r"|\b(?:art|artwork|painting|canvas|print)\b[^.!?;]{0,25}\b(?:larger|bigger|on the wall|linking|between|connecting)\b",
            re.I,
        ),
        re.compile(r"\b(?:art|artwork|print|painting|canvas|frame|poster|wall\s+(?:art|decor|décor))\b", re.I),
    ),
    (
        "rug",
        "Area rug",
        re.compile(
            r"\b(?:add(?:ing)?|new|want|need|larger|bigger|an?|area|cozy|soft)\s+(?:\w+\s+){0,2}rugs?\b|\brugs?\b[^.!?;]{0,20}\b(?:added|please)\b",
            re.I,
        ),
        re.compile(r"\brugs?\b", re.I),
    ),
    (
        "cozy",
        "Cozy textiles",
        re.compile(
            r"\bcoz(?:y|ier|iness)|\bcos(?:y|ier)\b|\bwarm(?:er)?\s+(?:touch|textile|feel)|\bthrow\s+(?:pillows?|blanket)|\bsoft\s+textiles\b"
            r"|\bwarmth\b|\b(?:add|adding|more|some|bring\s+in)\s+(?:\w+\s+)?textures?\b",
            re.I,
        ),
        re.compile(r"\b(?:throw|pillows?|cushions?|textiles?|blanket|coz(?:y|ier))\b", re.I),
    ),
    (
        "table_setting",
        "Set dining table",
        re.compile(
            r"\bset\s+(?:the\s+)?(?:dining\s+)?table\b|\btable\s+(?:set|setting|settings|styled|styling)\b|"
            r"\b(?:well[-\s])?styled\s+(?:dining\s+)?table\b|"
            r"\bplace\s?settings?\b|\btablescape\b|\bcenter\s?piece\b|\bcentre\s?piece\b|\bplacemats?\b",
            re.I,
        ),
        re.compile(r"\b(?:placemats?|place\s?settings?|table\s+(?:setting|runner)|centerpiece|centrepiece|dinnerware|napkins?)\b", re.I),
    ),
    (
        "plant",
        "Plants",
        re.compile(r"\b(?:add|want|some|more|a)\s+(?:\w+\s+)?(?:plants?|greenery)\b", re.I),
        re.compile(r"\b(?:plants?|greenery|planter)\b", re.I),
    ),
    (
        "lamp",
        "Lamp",
        re.compile(r"\b(?:add|want|need|a|new)\s+(?:\w+\s+)?(?:lamp|floor\s+lamp|table\s+lamp)\b", re.I),
        re.compile(r"\blamps?\b", re.I),
    ),
)

_KEEP_EXISTING = re.compile(
    r"\bkeep(?:ing)?\s+(?:the\s+|my\s+|our\s+|their\s+|her\s+|his\s+|all\s+)?(?:existing|current|original)\s+"
    r"(?P<item>[a-z][a-z \-+&/']{1,48}?)(?=\s*(?:[,.;!?)]|\band\b|\bbut\b|\bthat\b|\bwhich\b|\bon\b|\bin\b|\bwhere\b|$))",
    re.I,
)

_KIND_WORDS: Tuple[Tuple[str, re.Pattern], ...] = (
    ("art", re.compile(r"\b(?:art|artwork|print|painting|canvas|frames?|poster|gallery)\b", re.I)),
    ("rug", re.compile(r"\brugs?\b", re.I)),
    ("cozy", re.compile(r"\b(?:throw|pillows?|cushions?|blanket|textiles?)\b", re.I)),
    ("table_setting", re.compile(r"\b(?:placemats?|place\s?settings?|table\s+(?:setting|runner)|centerpiece|centrepiece|napkins?)\b", re.I)),
    ("plant", re.compile(r"\b(?:plants?|greenery|planter)\b", re.I)),
    ("lamp", re.compile(r"\blamps?\b", re.I)),
    ("basket", re.compile(r"\b(?:baskets?|bins?|boxes)\b", re.I)),
    ("mirror", re.compile(r"\bmirrors?\b", re.I)),
    ("curtain", re.compile(r"\b(?:curtains?|drapes?|shades?)\b", re.I)),
    ("tray", re.compile(r"\b(?:trays?|catch[-\s]?alls?|dish|bowl)\b", re.I)),
    ("hooks", re.compile(r"\bhooks?\b", re.I)),
    ("shelf", re.compile(r"\bshel(?:f|ves)\b", re.I)),
)


def item_kind(name: str) -> str:
    for kind, pattern in _KIND_WORDS:
        if pattern.search(name or ""):
            return kind
    return "other"


def open_budget(lead: Optional[Dict[str, Any]]) -> bool:
    """True when the project budget is "open" (no cap)."""
    return effective_budget(lead) == "open"


def effective_budget(lead: Optional[Dict[str, Any]]) -> str:
    """The one budget id every surface states: the admin brief, then its notes, then the intake choice.

    The latest explicit instruction wins, so a brief that opens the budget
    replaces the band picked at intake everywhere (summary, drafter, documents).
    """
    lead = lead or {}
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    brief_budget = _clean(brief.get("budget"))
    if brief_budget:
        return brief_budget
    if OPEN_BUDGET_RE.search(brief_notes(lead)):
        return "open"
    intake = lead.get("intake") if isinstance(lead.get("intake"), dict) else {}
    return _clean(lead.get("budget") or intake.get("budget"))


# Pieces that count as a retained object in "keep / retain / preserve the X".
_OBJECT_NOUNS = {
    "tv", "television", "console", "cabinet", "credenza", "sideboard", "buffet", "bench", "bed", "bunk",
    "crib", "cot", "dresser", "chest", "sofa", "couch", "sectional", "chaise", "loveseat", "armchair",
    "chair", "chairs", "stool", "stools", "ottoman", "table", "desk", "artwork", "art", "painting",
    "print", "prints", "poster", "mirror", "playpen", "rug", "shelf", "shelves", "bookcase", "bookshelf",
    "wardrobe", "armoire", "lamp", "curtains", "drapes", "blinds", "piano", "guitar", "ukulele", "rack",
    "switch", "switches", "rocker", "glider", "cabinets", "unit",
}
_RETAIN_VERB = re.compile(r"\b(?:keep|keeping|retain|retaining|preserve|preserving)\b", re.I)
_LEAD_WORDS = {
    "the", "my", "our", "their", "her", "his", "its", "a", "an", "all", "both", "existing", "current",
    "original", "same", "that", "this", "these", "those",
}
_ITEM_STOP = {
    "clear", "free", "tidy", "open", "accessible", "visible", "usable", "reachable", "exactly", "intact",
    "as", "so", "to", "for", "while", "because", "but", "which", "in", "where", "when", "unchanged",
    "untouched", "without", "with", "and", "or", "is", "are", "stays", "stay", "if",
}
_NOT_RETAINED = re.compile(r"\b(?:wall\s+colou?r|walls?|paint|furniture|layout|floor|everything|feel|style|look)\b", re.I)
_VIEW_TAIL = re.compile(r"\s+(?:in|across|from)\s+(?:every|each|all)\s+(?:angles?|views?|photos?|images?)\b.*$", re.I)


def _word(token: str) -> str:
    return re.sub(r"(?:'s|’s)$", "", token.strip(".,;:!?()\"").lower())


def _display_name(name: str) -> str:
    return re.sub(r"\btv\b", "TV", name)


def _retained_from_fragment(fragment: str) -> Optional[Tuple[str, str, bool]]:
    """(name, details, possessive) for one listed object, or None when it names no piece."""
    tokens = fragment.split()
    while tokens and _word(tokens[0]) in _LEAD_WORDS:
        tokens = tokens[1:]
    if not tokens:
        return None
    last, stop, possessive = -1, len(tokens), False
    for index, token in enumerate(tokens):
        word = _word(token)
        if word in _ITEM_STOP:
            stop = index
            break
        if word in _OBJECT_NOUNS:
            last = index
            if re.search(r"(?:'s|’s)[.,;:!?]?$", token):
                possessive = True
                stop = index + 1
                break
    if last < 0:
        return None
    name = " ".join(tokens[: last + 1]).strip(".,;:!?\"")
    name = re.sub(r"(?:'s|’s)$", "", name)
    if _NOT_RETAINED.search(name):
        return None
    details = _VIEW_TAIL.sub("", " ".join(tokens[stop:])).strip(" .,;:!?")
    return name, details, possessive


def retained_from_sentence(sentence: str) -> List[Dict[str, str]]:
    """Objects a sentence says to keep, retain, or preserve, each with the structure it names.

    "Keep the TV console's exact structure and original glass doors" → TV console,
    "exact structure and original glass doors". "Preserve the existing shoe bench
    without baskets" → shoe bench, "without baskets". Lists after one verb split
    on commas; a clause that starts with another verb ends the list.
    """
    out: List[Dict[str, str]] = []
    matches = list(_RETAIN_VERB.finditer(sentence))
    for position, match in enumerate(matches):
        if _negated(sentence, match.start()):
            continue
        end = matches[position + 1].start() if position + 1 < len(matches) else len(sentence)
        rest = sentence[match.end() : end]
        fragments = re.split(
            r",\s*(?:and\s+)?|\s+and\s+(?=(?:the|my|our|their|her|his|its|a|an|all|existing|current|original)\b)",
            rest,
            flags=re.I,
        )
        previous: Optional[Dict[str, str]] = None
        for fragment in fragments:
            fragment = fragment.strip()
            if not fragment:
                continue
            first = _word(fragment.split()[0])
            starts_like_object = first in _LEAD_WORDS or first in _OBJECT_NOUNS or bool(
                re.match(r"^[A-Z][a-z]+(?:'s|’s)\s", fragment)
            )
            found = _retained_from_fragment(fragment) if starts_like_object or previous is None else None
            if found is None:
                if previous is not None and previous.get("possessive") and starts_like_object:
                    extra = _VIEW_TAIL.sub("", fragment).strip(" .,;:!?")
                    if extra and not _NOT_RETAINED.search(extra):
                        previous["details"] = f"{previous['details']} and {extra}" if previous["details"] else extra
                    continue
                if not starts_like_object:
                    break
                continue
            name, details, possessive = found
            previous = {"name": name, "details": details, "possessive": "1" if possessive else ""}
            out.append(previous)
    return [{"name": row["name"], "details": row["details"]} for row in out]


def keep_existing_items(lead: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Existing pieces the customer or the brief said to keep, retain, or preserve.

    Each row carries the structure the sentence names (``details``), so
    "keep the TV console's original glass doors" locks the glass doors too.
    """
    lead = lead or {}
    out: List[Dict[str, str]] = []
    seen: Dict[str, Dict[str, str]] = {}

    def add(name: str, note: str, details: str = "") -> None:
        name = _display_name(_clean(name).strip(" -+&/'").lower())
        key = name.lower()
        if not name or key in {"furniture", "layout", "wall color", "walls", "paint"}:
            return
        details = _clean(details)
        if key in seen:
            if details and details.lower() not in seen[key]["details"].lower():
                seen[key]["details"] = f"{seen[key]['details']}; {details}".strip("; ")
            return
        row = {"name": name, "kind": item_kind(name), "note": _clean(note), "details": details}
        seen[key] = row
        out.append(row)

    for sentence in _sentences(request_text(lead)):
        for match in _KEEP_EXISTING.finditer(sentence):
            add(match.group("item"), sentence)
        for found in retained_from_sentence(sentence):
            add(found["name"], sentence, found["details"])
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    for name in brief.get("keep_existing") or []:
        add(str(name), f"Keep the existing {name}.")
    for raw in brief.get("retained") or []:
        if isinstance(raw, dict):
            add(str(raw.get("name") or ""), f"Keep the existing {raw.get('name')}.", str(raw.get("details") or ""))
        elif isinstance(raw, str):
            add(raw, f"Keep the existing {raw}.")
    facts = lead.get("fact_sheet") if isinstance(lead.get("fact_sheet"), dict) else {}
    for entry in ((facts.get("keep") or {}).get("items") or []):
        if isinstance(entry, dict):
            add(str(entry.get("text") or ""), f"Keep {entry.get('text')}.")
    return out


# ──────────────────────────── Things no view may show ─────────────────────────────

_AVOID_RE = re.compile(
    r"\b(?:remove|no|never|without|avoid|take\s+(?:off|away)|don'?t\s+(?:add|put|place|show)|do\s+not\s+(?:add|put|place|show))\s+"
    r"(?:any\s+|the\s+|a\s+|all\s+)?(?P<what>baskets?|bins?|boxes|crates?|cubbies|open\s+cubbies)"
    r"(?P<where>\s+(?:placed\s+|sitting\s+|left\s+)?(?:on|under|in|inside|atop|across)\s+[^.;!?,]{2,60})",
    re.I,
)


def avoid_rules(lead: Optional[Dict[str, Any]]) -> List[str]:
    """Explicit "never show this" rules from the brief and the customer, in plain words.

    "Remove any basket placed on Sam's bed" → "basket on Sam's bed". A kept piece
    "without baskets" → "baskets on or under the shoe bench". Admin brief
    ``avoid`` entries are taken as written.
    """
    lead = lead or {}
    out: List[str] = []

    def add(text: str) -> None:
        text = _clean(text).strip(" .")
        if text and text.lower() not in {x.lower() for x in out}:
            out.append(text)

    for sentence in _sentences(request_text(lead)):
        for match in _AVOID_RE.finditer(sentence):
            where = re.sub(r"^\s*(?:placed|sitting|left)\s+", " ", match.group("where"))
            add(f"{match.group('what').lower()}{where}")
    for item in keep_existing_items(lead):
        found = re.search(r"\bwithout\s+(?:any\s+)?(baskets?|bins?|boxes|cubbies)\b", item.get("details") or "", re.I)
        if found:
            add(f"{found.group(1).lower()} on or under the {item['name']}")
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    for raw in brief.get("avoid") or []:
        add(str(raw))
    return out


def avoid_rails(lead: Optional[Dict[str, Any]]) -> str:
    rules = avoid_rules(lead)
    if not rules:
        return ""
    return "NEVER SHOW, IN ANY VIEW: " + "; ".join(rules) + "."


def brief_requests(lead: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Explicit asks from the customer answers and the admin brief.

    ``decor`` lists requested additions in request order, each with the
    customer's own sentence as ``note`` (it carries the placement, e.g. "on the
    wall linking dining and kitchen").
    """
    lead = lead or {}
    decor: List[Dict[str, str]] = []
    kinds = set()
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    for raw in brief.get("decor") or []:
        name = _clean(raw.get("name") if isinstance(raw, dict) else raw)
        if not name:
            continue
        kind = item_kind(name)
        label = next((label for k, label, _r, _p in DECOR_KINDS if k == kind), name[:1].upper() + name[1:])
        note = _clean(raw.get("placement") if isinstance(raw, dict) else "") or name
        if kind not in kinds or kind == "other":
            kinds.add(kind)
            decor.append({"kind": kind, "label": label, "note": note})
    for sentence in _sentences(request_text(lead)):
        for kind, label, pattern, _planned in DECOR_KINDS:
            if kind in kinds:
                continue
            match = pattern.search(sentence)
            if not match or _negated(sentence, match.start()):
                continue
            if kind == "art" and _KEEP_EXISTING.search(sentence) and not re.search(r"\b(?:larger|bigger|new|add|more|statement)\b", sentence, re.I):
                continue
            kinds.add(kind)
            decor.append({"kind": kind, "label": label, "note": sentence})
    return {
        "open_budget": open_budget(lead),
        "decor": decor,
        "keep_existing": keep_existing_items(lead),
    }


def brief_prompt_lines(lead: Optional[Dict[str, Any]]) -> List[str]:
    """Drafter lines for the brief. Every one is a hard requirement."""
    req = brief_requests(lead)
    lines: List[str] = []
    notes = brief_notes(lead)
    if notes:
        lines.append(f"Project brief notes (authoritative): {notes}")
    if req["open_budget"]:
        lines.append(
            "Budget: OPEN (no cap). Choose what serves the room best; still price every line and state one total."
        )
    for item in req["decor"]:
        lines.append(
            f"BRIEF REQUEST — include {item['label'].lower()} in additions and shopping_list, placed as asked: \"{item['note']}\""
        )
    for item in req["keep_existing"]:
        detail = f" ({item['details']})" if item.get("details") else ""
        lines.append(
            f"KEEP EXISTING — the customer's existing {item['name']}{detail} stays exactly as it is in every view; "
            "never replace, restyle, or remove it, and list it in fixed_items."
        )
    for rule in avoid_rules(lead):
        lines.append(f"NEVER SHOW — {rule}. Do not plan, buy, or describe it.")
    return lines


# ──────────────────────────── Fixed items ─────────────────────────────


def fixed_items(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Furniture and built-ins that stay, each with its exact structure. Derived once, used by every view."""
    deliverable = deliverable or {}
    out: List[Dict[str, str]] = []
    seen: Dict[str, Dict[str, str]] = {}

    def add(name: str, details: str, source: str) -> None:
        name = _clean(name)
        key = name.lower()
        if not name or key in seen:
            return
        row = {"name": name, "details": _clean(details), "source": source}
        seen[key] = row
        out.append(row)

    for item in deliverable.get("fixed_items") or []:
        if isinstance(item, dict):
            add(str(item.get("name") or ""), str(item.get("details") or item.get("structure") or ""), "photos")
        elif isinstance(item, str):
            add(item, "", "photos")
    for item in keep_existing_items(lead):
        kept = item["name"].lower()
        match = next((row for key, row in seen.items() if kept in key or key in kept), None)
        brief_details = item.get("details") or ""
        if match is None:
            add(item["name"], brief_details or "existing piece the customer keeps", "brief")
        elif brief_details and brief_details.lower() not in match["details"].lower():
            # The photo read can miss structure the brief names ("original glass doors"); lock both.
            match["details"] = f"{match['details']}; brief: {brief_details}".strip("; ")
    return out


CROSS_VIEW_RAILS = (
    "CROSS-VIEW CONSISTENCY: this photo is one view of a room photographed from several angles. "
    "Every fixed furniture piece, the rug, the artwork, and every planned addition must look identical "
    "in every view where it is visible — same structure, doors, drawers, shelves, color, material, size, "
    "and position. Never show a piece one way in one view and differently in another."
)

FIXED_RETRY_CONSTRAINT = (
    "FAILED QA: a fixed furniture piece changed structure. Keep every existing piece exactly as in the "
    "source photo: glass or solid doors stay doors (never open cubbies or baskets), and the number of "
    "drawers and shelves stays the same."
)


def fixed_items_rails(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]] = None) -> str:
    """Per-photo lock on existing furniture, from the one shared fixed-items list."""
    items = fixed_items(lead, deliverable)
    general = (
        "FIXED FURNITURE LOCK: existing furniture and built-ins keep their exact structure — doors stay doors "
        "(glass doors stay glass doors, closed cabinets stay closed), drawers and shelves keep their count, "
        "and finish, color, and size stay the same. Never turn doors into open cubbies, baskets, or bins, "
        "never swap a piece for a different one, and never remove, hide, or crop out a fixed piece that "
        "this photo shows (artwork, playpen, and equipment included)."
    )
    if not items:
        return f"{general} {CROSS_VIEW_RAILS}"
    listed = "; ".join(
        f"{index}) {item['name']}" + (f" — {item['details']}" if item["details"] else "")
        for index, item in enumerate(items, start=1)
    )
    return f"{general} THE FIXED PIECES IN THIS ROOM ARE: {listed}. {CROSS_VIEW_RAILS}"


def fixed_retry_constraint(changed: Iterable[str] = (), missing: Iterable[str] = ()) -> str:
    """Retry text naming the exact pieces QA saw change or disappear."""
    changed, missing = [_clean(x) for x in changed if _clean(x)], [_clean(x) for x in missing if _clean(x)]
    bits = [FIXED_RETRY_CONSTRAINT]
    if changed:
        bits.append("These pieces changed and must match the source photo exactly: " + "; ".join(changed) + ".")
    if missing:
        bits.append("These pieces disappeared and must stay visible where the source photo shows them: " + "; ".join(missing) + ".")
    return " ".join(bits)


# ──────────────────────────── Basket placement ─────────────────────────────

_BASKET = r"(?:baskets?|bins?|storage\s+boxes|boxes|crates?)"
_FORBIDDEN_SPOT = (
    r"(?:sofa|couch|sectional|chaise|loveseat|arm\s?chair|chairs?|seat(?:ing)?|cushions?|bed|bunk|crib|mattress|"
    r"shoe\s+bench|bench\s+seat|bench|ottoman\s+top)"
)
BASKET_ON_SEAT_RE = re.compile(
    rf"\b{_BASKET}\b[^.!?;]{{0,40}}\b(?:on|onto|atop|on\s+top\s+of|under|beneath|below|across|in)\s+(?:the\s+|a\s+|each\s+|your\s+)?(?:\w+\s+)?{_FORBIDDEN_SPOT}\b"
    rf"|\b{_FORBIDDEN_SPOT}\b[^.!?;]{{0,20}}\b{_BASKET}\b",
    re.I,
)
_SEAT_BASKET_OK = re.compile(r"\b(?:beside|next to|near|by|behind|floor)\b", re.I)

BASKET_PLACEMENT_RAILS = (
    "BASKET PLACEMENT RULE: never place a basket, bin, box, or crate on a seating surface (sofa, sectional, "
    "chaise, armchair, dining chair, bench seat), on or in a bed or crib, or on or under a shoe bench where "
    "shoes are kept — shoes stay visible and easy to reach, and every seat stays free to sit on. Put baskets "
    "on the floor beside furniture, inside existing shelving, or on a console top instead."
)

BASKET_DRAFT_RULE = (
    "- Never put a basket, bin, or box on a seating surface (sofa, sectional, chaise, chair, bench seat), on a bed or crib, "
    "or on or under a shoe bench's shoe area. Shoes stay reachable and the seat stays free. Only break this rule when the "
    "customer explicitly asked for that exact placement.\n"
)


def customer_basket_request(lead: Optional[Dict[str, Any]]) -> str:
    """The customer's own sentence asking for a basket on a seat, bed, or shoe bench. Empty when none."""
    for sentence in _sentences(request_text(lead)):
        match = BASKET_ON_SEAT_RE.search(sentence)
        if match and not _negated(sentence, match.start()):
            return sentence
    return ""


def basket_rails(lead: Optional[Dict[str, Any]]) -> str:
    asked = customer_basket_request(lead)
    if asked:
        return f"{BASKET_PLACEMENT_RAILS} Exception the customer asked for: \"{asked}\"."
    return BASKET_PLACEMENT_RAILS


def basket_placement_issues(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]]) -> List[str]:
    """Plan sentences that put a basket on a seat, a bed, or a shoe bench's shoe area."""
    if customer_basket_request(lead):
        return []
    found: List[str] = []
    for sentence in _sentences(_plan_text(deliverable or {})):
        match = BASKET_ON_SEAT_RE.search(sentence)
        if not match:
            continue
        span = sentence[match.start() : match.end()]
        if _SEAT_BASKET_OK.search(span) or _negated(sentence, match.start()):
            continue
        found.append(sentence)
    return found


# ──────────────────────────── Planned additions ─────────────────────────────


def _plan_text(doc: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("intro", "summary", "notes", "budget_note", "project_story"):
        parts.append(_clean(doc.get(key)))
    for key in ("needs", "strategy", "action_plan", "benefits"):
        parts.extend(_clean(x) for x in doc.get(key) or [])
    for zone in doc.get("zones") or []:
        if isinstance(zone, dict):
            parts.append(f"{_clean(zone.get('title'))}: {_clean(zone.get('desc'))}.")
    for item in doc.get("shopping_list") or []:
        if isinstance(item, dict):
            parts.append(_clean(item.get("name")) + ".")
    for item in doc.get("additions") or []:
        if isinstance(item, dict):
            parts.append(f"{_clean(item.get('name'))} {_clean(item.get('placement'))}.")
    return "\n".join(p for p in parts if p and p not in {".", ":"})


_PLACEMENT_RE = re.compile(
    r"\b(?:on|above|over|under|between|linking|connecting|beside|near|next to|in front of|behind|by the)\b", re.I
)


def planned_additions(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every new visible item, once. Brief requests first, then the plan's additions and shopping rows."""
    lead, doc = lead or {}, deliverable or {}
    out: List[Dict[str, Any]] = []
    by_kind: Dict[str, Dict[str, Any]] = {}

    def add(name: str, kind: str, placement: str, source: str, required: bool) -> None:
        name = _clean(name)
        if not name:
            return
        existing = by_kind.get(kind) if kind != "other" else None
        if existing is None:
            existing = next((x for x in out if x["name"].lower() == name.lower()), None)
        if existing is not None:
            existing["required"] = existing["required"] or required
            if existing["source"] == "brief" and source != "brief":
                existing["name"] = name
            if placement and not existing["placement"]:
                existing["placement"] = _clean(placement)
            return
        row = {
            "id": f"A{len(out) + 1}",
            "name": name,
            "kind": kind,
            "placement": _clean(placement),
            "source": source,
            "required": required,
        }
        out.append(row)
        if kind != "other":
            by_kind[kind] = row

    for item in brief_requests(lead)["decor"]:
        placement = item["note"] if _PLACEMENT_RE.search(item["note"]) else ""
        add(item["label"], item["kind"], placement, "brief", True)
    for item in doc.get("additions") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
            add(name, item_kind(name), str(item.get("placement") or item.get("zone") or ""), "plan", False)
    for item in doc.get("shopping_list") or []:
        if isinstance(item, dict):
            name = str(item.get("short_name") or item.get("name") or "")
            kind = item_kind(str(item.get("name") or name))
            add(name, kind, "", "shopping", False)
    return out


def additions_rails(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]]) -> str:
    """The only new items an after may show, and where they go."""
    items = planned_additions(lead, deliverable)
    if not items:
        return (
            "PLANNED ADDITIONS: none beyond tidying. Do not add new furniture or decor; only tidy loose items."
        )
    listed = "; ".join(
        f"{item['name']}" + (f" ({item['placement']})" if item["placement"] else "") for item in items
    )
    return (
        f"PLANNED ADDITIONS — the only new items allowed in any view: {listed}. When the spot for an item is "
        "visible in this photo, show that item there, the same in every view. When its spot is out of frame, "
        "do not move it into frame. Do not add other furniture or decor beyond small accessories."
    )


# ──────────────────────────── The room inventory ─────────────────────────────

INVENTORY_VERSION = 1


def room_inventory(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The one record every output reads: what stays, what changes, what never appears, walls, budget.

    ``hash`` covers everything an after image depends on. Each view's QA and the
    cross-view check record the hash they were verified against, so a brief or
    plan edit after generation shows up as stale views instead of shipping.
    """
    import hashlib
    import json

    from ai_image_generator import requested_wall_color
    from blueprint_consistency import prepare_deliverable
    from blueprint_layers import BUDGET_LABELS

    lead = lead or {}
    doc = prepare_deliverable(lead, deliverable or {})
    retained = [{"id": f"R{index}", **row} for index, row in enumerate(fixed_items(lead, doc), start=1)]
    changes = planned_additions(lead, doc)
    avoid = avoid_rules(lead)
    paint = requested_wall_color(lead, doc)
    exception = customer_basket_request(lead)
    budget_id = effective_budget(lead)
    core = {
        "retained": [[r["name"].lower(), r["details"].lower()] for r in retained],
        "changes": [[c["name"].lower(), c["placement"].lower()] for c in changes],
        "avoid": [a.lower() for a in avoid],
        "walls": paint.lower() or "keep",
        "basket_exception": exception.lower(),
    }
    digest = hashlib.sha1(json.dumps(core, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return {
        "version": INVENTORY_VERSION,
        "hash": digest,
        "retained": retained,
        "changes": changes,
        "avoid": avoid,
        "walls": {"keep": not paint, "paint": paint},
        "basket_exception": exception,
        "budget": {"id": budget_id, "label": BUDGET_LABELS.get(budget_id, ""), "open": budget_id == "open"},
    }


def view_check_inputs(inventory: Dict[str, Any]) -> Dict[str, Any]:
    """What every view's vision QA checks, taken from the inventory (``review_organized_render`` kwargs)."""
    return {
        "fixed_items": [f"{r['name']} ({r['details']})" if r["details"] else r["name"] for r in inventory["retained"]],
        "additions": [c["name"] for c in inventory["changes"]],
        "basket_exception": inventory.get("basket_exception") or "",
        "avoid": list(inventory.get("avoid") or []),
    }


_ADD_VERB = re.compile(
    r"\b(?:add(?:s|ing)?|bring(?:s|ing)?\s+in|hang(?:s|ing)?|introduce[sd]?|lay(?:s|ing)?(?:\s+down)?|place[sd]?|"
    r"set(?:s|ting)?|style[sd]?|layer(?:s|ing)?|swap\s+in|put(?:s|ting)?|mount(?:s|ing)?)\b",
    re.I,
)
_SHOWN_KINDS = {"art", "rug", "cozy", "table_setting", "plant", "lamp", "mirror", "curtain"}


def described_changes(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Visible additions the plan's own sentences promise ("Hang a larger print over the table")."""
    out: List[Dict[str, str]] = []
    kinds = set()
    for sentence in _sentences(_plan_text(doc)):
        verb = _ADD_VERB.search(sentence)
        if not verb or _negated(sentence, verb.start()):
            continue
        tail = sentence[verb.end() :]
        if re.search(r"\b(?:existing|current|original|you already have|your own)\b", tail[:40], re.I):
            continue
        for kind, pattern in _KIND_WORDS:
            if kind not in _SHOWN_KINDS or kind in kinds:
                continue
            if pattern.search(tail):
                kinds.add(kind)
                out.append({"kind": kind, "sentence": sentence})
    return out


# ──────────────────────────── Consistency report ─────────────────────────────

BLOCK = "block"
WARN = "warn"

# Fidelity failures that no override may ship to a customer.
NON_OVERRIDABLE = frozenset(
    {
        "fixed_item_changed",
        "fixed_item_missing",
        "cross_view_mismatch",
        "avoid_rule_broken",
        "basket_on_seat_or_bed",
    }
)

_REMOVE_RE = re.compile(r"\b(?:replace|replacing|remove|removing|swap|swapping|get rid of|take down|retire|discard)\b", re.I)
_NON_ENGLISH_RE = re.compile(
    r"\b(?:vers[ãa]o|revis[ãa]o|para\s+sua|sala\s+de|cozinha|tapete|quadro|mesa\s+de|não|você|"
    r"versión|para\s+su|cocina|alfombra|usted)\b",
    re.I,
)


def _issue(code: str, severity: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **extra}


def _kind_in_plan(kind: str, doc: Dict[str, Any]) -> bool:
    planned = next((p for k, _l, _r, p in DECOR_KINDS if k == kind), None)
    names = [str(i.get("name") or "") for i in doc.get("shopping_list") or [] if isinstance(i, dict)]
    names += [str(i.get("name") or "") for i in doc.get("additions") or [] if isinstance(i, dict)]
    if planned is None:
        return any(item_kind(n) == kind for n in names)
    return any(planned.search(n) for n in names)


def _view_entries(doc: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """(after label, source_afters row, its QA) for every after a package carries."""
    out = []
    for entry in doc.get("source_afters") or []:
        if isinstance(entry, dict) and entry.get("after_url"):
            label = str(entry.get("after_label") or entry.get("label") or "view")
            out.append((label, entry, dict(entry.get("qa") or {})))
    return out


def _view_check_issues(label: str, entry: Dict[str, Any], qa: Dict[str, Any], current: str) -> List[Dict[str, Any]]:
    """A view must pass the item check, against this inventory, on the image it now carries."""
    issues: List[Dict[str, Any]] = []
    if qa.get("skipped") or "visible_additions" not in qa:
        why = f" ({qa['error']})" if qa.get("error") else ""
        issues.append(
            _issue(
                "view_not_verified",
                BLOCK,
                f"{label} has not passed the vision check against the room inventory{why}. Run verify.",
                view=label,
            )
        )
    elif qa.get("inventory_hash") != current:
        issues.append(
            _issue(
                "view_inventory_stale",
                BLOCK,
                f"{label} was checked against a different room inventory (the brief or the plan changed since). "
                "Run verify, or regenerate the view.",
                view=label,
            )
        )
    elif str(qa.get("checked_after_url") or "") != str(entry.get("after_url") or ""):
        issues.append(
            _issue("view_changed_after_check", BLOCK, f"{label} was replaced after its check. Run verify.", view=label)
        )
    altered = [str(x) for x in qa.get("fixed_items_altered") or [] if str(x).strip()]
    if qa.get("fixed_items_changed") or altered:
        what = "; ".join(altered) if altered else "a fixed furniture piece"
        issues.append(_issue("fixed_item_changed", BLOCK, f"{label}: {what} changed structure.", view=label))
    for name in qa.get("fixed_items_missing") or []:
        issues.append(
            _issue("fixed_item_missing", BLOCK, f"{label}: {name} is missing from the organized view.", view=label, item=str(name))
        )
    if qa.get("baskets_misplaced"):
        issues.append(_issue("basket_on_seat_or_bed", BLOCK, f"{label}: a basket sits on a seat, a bed, or a shoe bench.", view=label))
    for rule in qa.get("avoid_seen") or []:
        issues.append(_issue("avoid_rule_broken", BLOCK, f"{label} shows {rule}, which the brief rules out.", view=label))
    return issues


def _cross_view_issues(
    raw: Dict[str, Any], entries: List[Tuple[str, Dict[str, Any], Dict[str, Any]]], current: str
) -> List[Dict[str, Any]]:
    """Two or more afters of one room must have been compared with each other, on these images."""
    approved = [entry for _label, entry, _qa in entries if str(entry.get("status") or "approved") == "approved"]
    if len(approved) < 2:
        return []
    cross = raw.get("cross_view") if isinstance(raw.get("cross_view"), dict) else {}
    urls = sorted(str(entry.get("after_url") or "") for entry in approved)
    if not cross or cross.get("skipped") or cross.get("error"):
        why = f" ({cross['error']})" if cross.get("error") else ""
        return [
            _issue(
                "cross_view_not_verified",
                BLOCK,
                f"The views have not been compared with each other for the kept pieces and planned additions{why}. Run verify.",
            )
        ]
    if cross.get("inventory_hash") != current or sorted(str(u) for u in cross.get("after_urls") or []) != urls:
        return [
            _issue(
                "cross_view_stale",
                BLOCK,
                "A view or the room inventory changed after the views were compared with each other. Run verify.",
            )
        ]
    issues = []
    for row in cross.get("mismatches") or []:
        views = ", ".join(str(v) for v in row.get("views") or []) or "the views"
        difference = f": {row['difference']}" if row.get("difference") else ""
        issues.append(
            _issue(
                "cross_view_mismatch",
                BLOCK,
                f"{row.get('name')} does not look the same across {views}{difference}.",
                item=str(row.get("name") or ""),
            )
        )
    return issues


def _budget_issues(
    lead: Dict[str, Any], doc: Dict[str, Any], inventory: Dict[str, Any], texts: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Every surface states the one effective budget; an open budget never shows an old band."""
    from blueprint_layers import BUDGET_LABELS
    from intake import BUDGETS

    budget = inventory["budget"]
    if not budget["id"]:
        return []
    shown = budget["label"] or BUDGETS.get(budget["id"], budget["id"])
    issues: List[Dict[str, Any]] = []
    others = {
        label
        for labels in (BUDGET_LABELS, BUDGETS)
        for key, label in labels.items()
        if key not in {budget["id"], "use_owned", "not_sure"} and label
    }
    for surface, text in texts.items():
        found = sorted(label for label in others if label in (text or ""))
        if found:
            issues.append(
                _issue(
                    "budget_mismatch",
                    BLOCK,
                    f"{surface} states {found[0]}, but the project budget is {shown}.",
                    surface=surface,
                )
            )
    facts = lead.get("fact_sheet") if isinstance(lead.get("fact_sheet"), dict) else {}
    recorded = _clean(((facts.get("budget") or {}) if isinstance(facts.get("budget"), dict) else {}).get("id"))
    if recorded and recorded != budget["id"]:
        issues.append(
            _issue(
                "budget_mismatch",
                BLOCK,
                f"The project record still lists {BUDGETS.get(recorded, recorded)}, but the project budget is {shown}.",
            )
        )
    stated = _clean(doc.get("stated_budget"))
    if budget["open"] and stated != budget["label"]:
        issues.append(
            _issue("budget_mismatch", BLOCK, f"The plan states {stated or 'no budget'}, but the project budget is {shown}.")
        )
    return issues


def _matches(addition: Dict[str, Any], seen: Iterable[str]) -> bool:
    name = addition["name"].lower()
    for raw in seen:
        text = _clean(raw).lower()
        if not text:
            continue
        if text == name or text in name or name in text:
            return True
        if addition["kind"] != "other" and item_kind(text) == addition["kind"]:
            return True
    return False


def customer_text_issues(texts: Dict[str, str]) -> List[Dict[str, Any]]:
    """Time-sensitive or non-English copy on a customer surface."""
    from evergreen_copy import find_time_sensitive

    issues: List[Dict[str, Any]] = []
    for surface, text in texts.items():
        stale = find_time_sensitive(text)
        if stale:
            issues.append(
                _issue("not_evergreen", BLOCK, f"{surface} names an age, date, or week label: {', '.join(stale[:3])}", surface=surface)
            )
        foreign = sorted({m.group(0) for m in _NON_ENGLISH_RE.finditer(text or "")})
        if foreign:
            issues.append(
                _issue("not_english", BLOCK, f"{surface} has non-English copy: {', '.join(foreign[:3])}", surface=surface)
            )
    return issues


def consistency_report(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    *,
    texts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Mismatches between the shared item list, the plan, the shopping rows, the views, and the copy.

    ``texts`` maps a surface name ("Design Plan", "Room Flow", "Companion Guide")
    to its customer text; pass it to lint the rendered copy as well.
    """
    from blueprint_consistency import prepare_deliverable
    from package_facts import package_facts

    lead = lead or {}
    raw = deliverable or {}
    doc = prepare_deliverable(lead, raw)
    req = brief_requests(lead)
    additions = planned_additions(lead, doc)
    issues: List[Dict[str, Any]] = []

    for item in req["decor"]:
        if not _kind_in_plan(item["kind"], doc):
            issues.append(
                _issue(
                    "brief_request_missing",
                    BLOCK,
                    f"The brief asks for {item['label'].lower()} but the plan and shopping list do not include it.",
                    request=item,
                )
            )

    plan_sentences = _sentences(_plan_text(doc))
    for kept in req["keep_existing"]:
        words = [w for w in re.findall(r"[a-z]+", kept["name"]) if len(w) > 2]
        for sentence in plan_sentences:
            if _REMOVE_RE.search(sentence) and words and all(w in sentence.lower() for w in words) and "existing" not in sentence.lower():
                issues.append(
                    _issue(
                        "keep_existing_contradicted",
                        BLOCK,
                        f"The brief keeps the existing {kept['name']}, but the plan says: \"{sentence}\"",
                    )
                )
                break

    for sentence in basket_placement_issues(lead, doc):
        issues.append(
            _issue(
                "basket_on_seat_or_bed",
                BLOCK,
                f"A basket sits on a seat, a bed, or a shoe bench's shoe area: \"{sentence}\"",
            )
        )

    inventory = room_inventory(lead, raw)
    current = inventory["hash"]
    entries = _view_entries(raw)
    checked: List[Tuple[str, Dict[str, Any]]] = []
    for label, entry, qa in entries:
        issues.extend(_view_check_issues(label, entry, qa, current))
        if not qa.get("skipped") and "visible_additions" in qa:
            checked.append((label, qa))
    if checked:
        seen_all: List[str] = []
        for _label, qa in checked:
            seen_all.extend(str(x) for x in qa.get("visible_additions") or [])
        for addition in additions:
            if addition["kind"] in {"tray", "hooks", "other"} and not addition["required"]:
                continue
            if not _matches(addition, seen_all):
                issues.append(
                    _issue(
                        "addition_not_shown",
                        BLOCK if addition["required"] or addition["kind"] in _SHOWN_KINDS else WARN,
                        f"The plan adds {addition['name'].lower()} but no organized view shows it. Show it where its "
                        "spot is visible, or take it out of the plan.",
                        addition=addition["id"],
                    )
                )
        for label, qa in checked:
            for extra in qa.get("unlisted_additions") or []:
                if not _matches({"name": str(extra), "kind": item_kind(str(extra))}, [a["name"] for a in additions]):
                    issues.append(
                        _issue(
                            "view_shows_unplanned_item",
                            BLOCK if item_kind(str(extra)) in {"rug", "art", "basket"} else WARN,
                            f"{label} shows {_clean(extra).lower()}, which the plan and shopping list do not mention.",
                            view=label,
                        )
                    )
    issues.extend(_cross_view_issues(raw, entries, current))

    planned_kinds = {a["kind"] for a in additions}
    for change in described_changes(doc):
        if change["kind"] not in planned_kinds:
            issues.append(
                _issue(
                    "change_not_in_inventory",
                    BLOCK,
                    f"The plan says \"{change['sentence']}\" but the item list has no {change['kind'].replace('_', ' ')}. "
                    "Add it to the additions and shopping list so the views show it, or take the sentence out.",
                )
            )

    issues.extend(_budget_issues(lead, doc, inventory, texts or {}))

    facts = package_facts(lead, raw, prepared=doc)
    for row in facts["items"]:
        if row["link"]["kind"] != "tested":
            issues.append(
                _issue(
                    "product_link_not_direct",
                    BLOCK,
                    f"{row['short']} has no tested direct product link yet.",
                    item=row["name"],
                )
            )

    from room_flow import resolve_room_flow, validate_room_flow

    for problem in validate_room_flow(resolve_room_flow(lead, raw)):
        issues.append(_issue("room_flow", BLOCK, f"Room Flow: {problem}."))

    issues.extend(customer_text_issues(texts or {}))
    blocking = [i for i in issues if i["severity"] == BLOCK]
    return {
        "ok": not blocking,
        "issues": issues,
        "blocking": len(blocking),
        "fixed_items": inventory["retained"],
        "additions": additions,
        "avoid": inventory["avoid"],
        "inventory_hash": current,
        "budget": inventory["budget"],
        "brief": req,
    }


def final_send_block_reason(report: Optional[Dict[str, Any]]) -> Optional[str]:
    """Why the customer final must wait on the consistency check. ``None`` when it may go."""
    if not report:
        return None
    blocking = [i for i in report.get("issues") or [] if i.get("severity") == BLOCK]
    if not blocking:
        return None
    head = "; ".join(str(i.get("message")) for i in blocking[:3])
    more = f" (+{len(blocking) - 3} more)" if len(blocking) > 3 else ""
    return f"Consistency check failed: {head}{more}"


def customer_texts(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    images: Optional[Dict[str, Any]] = None,
    *,
    companion_pdf: Optional[bytes] = None,
) -> Dict[str, str]:
    """The customer copy of each document, for ``consistency_report(texts=...)``."""
    import io

    from image_board import board_spec, customer_board_text
    from room_flow import zone_map_spec, zone_map_text

    texts = {
        "Design Plan": customer_board_text(board_spec(lead, deliverable, images or {})),
        "Room Flow": zone_map_text(zone_map_spec(lead, deliverable, images or {})),
    }
    if companion_pdf:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(companion_pdf))
            texts["Companion Guide"] = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            texts["Companion Guide"] = ""
    return texts
