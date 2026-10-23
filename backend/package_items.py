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

``consistency_report`` compares the plan text, the shopping rows, the per-view
QA results, and the customer copy against these lists and returns issues. A
``block`` issue stops the customer final send (``final_send_block_reason``).
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
            r"\bcoz(?:y|ier|iness)|\bcos(?:y|ier)\b|\bwarm(?:er)?\s+(?:touch|textile|feel)|\bthrow\s+(?:pillows?|blanket)|\bsoft\s+textiles\b",
            re.I,
        ),
        re.compile(r"\b(?:throw|pillows?|cushions?|textiles?|blanket|coz(?:y|ier))\b", re.I),
    ),
    (
        "table_setting",
        "Set dining table",
        re.compile(
            r"\bset\s+(?:the\s+)?(?:dining\s+)?table\b|\btable\s+(?:set|setting|settings|styled|styling)\b|"
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
    """True when the intake budget is "open" or the brief says there is no cap."""
    lead = lead or {}
    budget = _clean(lead.get("budget") or ((lead.get("intake") or {}) if isinstance(lead.get("intake"), dict) else {}).get("budget"))
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    if budget == "open" or _clean(brief.get("budget")).lower() == "open":
        return True
    return bool(OPEN_BUDGET_RE.search(request_text(lead)))


def keep_existing_items(lead: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Existing pieces the customer or the brief said to keep ("keep the existing art")."""
    lead = lead or {}
    out: List[Dict[str, str]] = []
    seen = set()

    def add(name: str, note: str) -> None:
        name = _clean(name).strip(" -+&/'").lower()
        if not name or name in seen or name in {"furniture", "layout", "wall color", "walls", "paint"}:
            return
        seen.add(name)
        out.append({"name": name, "kind": item_kind(name), "note": _clean(note)})

    for sentence in _sentences(request_text(lead)):
        for match in _KEEP_EXISTING.finditer(sentence):
            add(match.group("item"), sentence)
    brief = lead.get("brief") if isinstance(lead.get("brief"), dict) else {}
    for name in brief.get("keep_existing") or []:
        add(str(name), f"Keep the existing {name}.")
    facts = lead.get("fact_sheet") if isinstance(lead.get("fact_sheet"), dict) else {}
    for entry in ((facts.get("keep") or {}).get("items") or []):
        if isinstance(entry, dict):
            add(str(entry.get("text") or ""), f"Keep {entry.get('text')}.")
    return out


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
        lines.append(
            f"KEEP EXISTING — the customer's existing {item['name']} stays exactly as it is; never replace or remove it."
        )
    return lines


# ──────────────────────────── Fixed items ─────────────────────────────


def fixed_items(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Furniture and built-ins that stay, each with its exact structure. Derived once, used by every view."""
    deliverable = deliverable or {}
    out: List[Dict[str, str]] = []
    seen = set()

    def add(name: str, details: str, source: str) -> None:
        name = _clean(name)
        key = name.lower()
        if not name or key in seen:
            return
        seen.add(key)
        out.append({"name": name, "details": _clean(details), "source": source})

    for item in deliverable.get("fixed_items") or []:
        if isinstance(item, dict):
            add(str(item.get("name") or ""), str(item.get("details") or item.get("structure") or ""), "photos")
        elif isinstance(item, str):
            add(item, "", "photos")
    for item in keep_existing_items(lead):
        if not any(item["name"] in existing.lower() or existing.lower() in item["name"] for existing in seen):
            add(item["name"], "existing piece the customer keeps", "brief")
    return out


def fixed_item_names(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]] = None) -> List[str]:
    return [f"{i['name']} ({i['details']})" if i["details"] else i["name"] for i in fixed_items(lead, deliverable)]


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
        "and never swap a piece for a different one."
    )
    if not items:
        return f"{general} {CROSS_VIEW_RAILS}"
    listed = "; ".join(
        f"{index}) {item['name']}" + (f" — {item['details']}" if item["details"] else "")
        for index, item in enumerate(items, start=1)
    )
    return f"{general} THE FIXED PIECES IN THIS ROOM ARE: {listed}. {CROSS_VIEW_RAILS}"


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


# ──────────────────────────── Consistency report ─────────────────────────────

BLOCK = "block"
WARN = "warn"

_REMOVE_RE = re.compile(r"\b(?:replace|replacing|remove|removing|swap|swapping|get rid of|take down|retire|discard)\b", re.I)
_NON_ENGLISH_RE = re.compile(
    r"\b(?:vers[ãa]o|revis[ãa]o|para\s+sua|sala\s+de|cozinha|tapete|quadro|mesa\s+de|não|você|"
    r"versión|para\s+su|cocina|alfombra|usted)\b",
    re.I,
)


_DRILLING_RE = re.compile(
    r"\b(?:drill(?:s|ed|ing)?|(?:wall|ceiling)[- ]mount(?:s|ed|ing)?|"
    r"mount(?:s|ed|ing)?\s+(?:[\w-]+\s+){0,4}?(?:on|to|onto)\s+(?:the\s+)?(?:[\w-]+\s+){0,2}?(?:wall|ceiling)s?|"
    r"screw(?:s|ed|ing)?\s+(?:[\w-]+\s+){0,3}?(?:in|into)|"
    r"anchor(?:s|ed|ing)?\s+(?:[\w-]+\s+){0,4}?to\s+(?:the\s+)?(?:wall|studs?))\b",
    re.I,
)


def stated_limits(lead: Optional[Dict[str, Any]]) -> List[str]:
    intake = (lead or {}).get("intake")
    limits = intake.get("limits") if isinstance(intake, dict) else None
    return [str(x) for x in limits] if isinstance(limits, list) else []


def no_drilling_conflicts(lead: Optional[Dict[str, Any]], doc: Dict[str, Any]) -> List[str]:
    """Plan sentences that drill, wall-mount or anchor when the customer chose "No drilling"."""
    if "no_drilling" not in stated_limits(lead):
        return []
    hits: List[str] = []
    for sentence in _sentences(_plan_text(doc)):
        match = _DRILLING_RE.search(sentence)
        if match and not _negated(sentence, match.start()) and sentence not in hits:
            hits.append(sentence)
    return hits


def _issue(code: str, severity: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **extra}


def _kind_in_plan(kind: str, doc: Dict[str, Any]) -> bool:
    planned = next((p for k, _l, _r, p in DECOR_KINDS if k == kind), None)
    names = [str(i.get("name") or "") for i in doc.get("shopping_list") or [] if isinstance(i, dict)]
    names += [str(i.get("name") or "") for i in doc.get("additions") or [] if isinstance(i, dict)]
    if planned is None:
        return any(item_kind(n) == kind for n in names)
    return any(planned.search(n) for n in names)


def _view_qa(doc: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    for entry in doc.get("source_afters") or []:
        if isinstance(entry, dict) and entry.get("after_url"):
            out.append((str(entry.get("after_label") or entry.get("label") or "view"), dict(entry.get("qa") or {})))
    return out


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

    for sentence in no_drilling_conflicts(lead, doc):
        issues.append(
            _issue(
                "limit_no_drilling_contradicted",
                BLOCK,
                f"The customer chose \"No drilling\", but the plan says: \"{sentence}\"",
            )
        )

    views = _view_qa(raw)
    checked = [(label, qa) for label, qa in views if not qa.get("skipped") and "visible_additions" in qa]
    for label, qa in views:
        if qa.get("fixed_items_changed"):
            issues.append(_issue("fixed_item_changed", BLOCK, f"{label}: a fixed furniture piece changed structure.", view=label))
        if qa.get("baskets_misplaced"):
            issues.append(_issue("basket_on_seat_or_bed", BLOCK, f"{label}: a basket sits on a seat, a bed, or a shoe bench.", view=label))
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
                        BLOCK if addition["required"] or addition["kind"] in {"rug", "art"} else WARN,
                        f"The plan adds {addition['name'].lower()} but no organized view shows it.",
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
    elif views:
        issues.append(_issue("views_not_checked", WARN, "The organized views were not checked against the item list."))

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
        "fixed_items": fixed_items(lead, doc),
        "additions": additions,
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
