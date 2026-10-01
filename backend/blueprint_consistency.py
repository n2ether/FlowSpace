"""Make a Blueprint agree with itself before it is drawn or emailed.

The rejected kids' room PDF showed two kit prices ($124–$154 and a $174
line-item total) and storage advice that would replace a dresser. This
module is the single place that:

- drops nursery recommendations that swap drawers for baskets or add large cubbies
- rewrites a budget note whose stated kit range is below the shopping-list total
- builds the companion-guide sections from the cleaned plan
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import quote_plus

from blueprint_layers import BUDGET_LABELS
from space_rails import NURSERY_DO_NOT, is_nursery_space, mentions_six_drawer

_RANGE = re.compile(
    r"\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?\s*(?:–|—|-|to)\s*\$?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?",
    re.I,
)
_MONEY = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?")
_BAD_SENTENCE = re.compile(
    r"[^.!?\n]*\b(?:cubby|cubbies|kallax|cube storage|open cubby|open cubbies)\b[^.!?\n]*[.!?]?"
    r"|[^.!?\n]*\b(?:replace|swap)\b[^.!?\n]*\bdrawers?\b[^.!?\n]*\bbaskets?\b[^.!?\n]*[.!?]?"
    r"|[^.!?\n]*\bbaskets?\b[^.!?\n]*\b(?:replace|instead of)\b[^.!?\n]*\bdrawers?\b[^.!?\n]*[.!?]?",
    re.I,
)
_CLIMATE = re.compile(
    r"draft|thermal|temperature|heater|hvac|winter|cold|curtain|humidity|warmth|insulat",
    re.I,
)
_KEEP_FALLBACK = "Keep the existing dresser and all of its drawers."
_KEEP_SIX = "Keep the existing six-drawer dresser — all six drawers stay."
_ONE_STEP = "Use the drawers you already have so putting things away stays one step."
_REMOVED_NOTE = (
    "We left out anything that would replace dresser drawers with baskets or add large open cubbies."
)


def format_money(value: float) -> str:
    if value <= 0:
        return "—"
    if abs(value - round(value)) < 0.009:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def shopping_total(deliverable: Dict[str, Any] | None) -> float:
    total = 0.0
    for item in (deliverable or {}).get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        try:
            qty = float(item.get("qty", 1) or 1)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            continue
        total += qty * price
    return total


def stated_budget_label(lead: Dict[str, Any] | None) -> str:
    raw = str((lead or {}).get("budget") or "").strip()
    return BUDGET_LABELS.get(raw, "")


def _parse_amounts(text: str) -> Tuple[List[Tuple[float, float]], List[float]]:
    ranges: List[Tuple[float, float]] = []
    spans: List[Tuple[int, int]] = []
    for match in _RANGE.finditer(text or ""):
        lo = float(match.group(1).replace(",", ""))
        hi = float(match.group(2).replace(",", ""))
        ranges.append((min(lo, hi), max(lo, hi)))
        spans.append(match.span())
    singles: List[float] = []
    for match in _MONEY.finditer(text or ""):
        if any(start <= match.start() < end for start, end in spans):
            continue
        singles.append(float(match.group(1).replace(",", "")))
    return ranges, singles


def note_conflicts(text: str, total: float) -> bool:
    """True when copy prices the kit below the line items, or names a different total.

    A customer budget band that the kit sits inside — or under — is not a conflict.
    "$100 – $300" with a $227 list is fine. "$124 – $154" with a $174 list is not.
    """
    if not text or total <= 0:
        return False
    ranges, singles = _parse_amounts(text)
    for _lo, hi in ranges:
        if total > hi + 1:
            return True
    for amount in singles:
        if abs(amount - total) > 1:
            return True
    return False


def canonical_budget_note(display: str) -> str:
    return f"Shopping list total {display}. The list total is the figure to shop."


def item_forbidden(name: str) -> bool:
    """Nursery shopping lines that replace the dresser or add large open cubbies."""
    n = (name or "").lower()
    if re.search(r"\b(cubby|cubbies|kallax)\b", n):
        return True
    if re.search(r"\bcube\s+(storage|organizer|shelf|unit|shelves)\b", n):
        return True
    if "basket" in n and ("drawer" in n or "dresser" in n):
        return True
    if re.search(r"\breplace\b", n) and "drawer" in n:
        return True
    return False


def scrub_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _BAD_SENTENCE.sub(" " + _KEEP_FALLBACK, str(text))
    return " ".join(cleaned.split()).strip()


def _source_blob(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    parts = [
        str(lead.get("must_stay") or ""),
        str(lead.get("goals") or ""),
        str(lead.get("notes") or ""),
        str(deliverable.get("intro") or ""),
        str(deliverable.get("summary") or ""),
        str(deliverable.get("notes") or ""),
    ]
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            parts.append(str(zone.get("title") or ""))
            parts.append(str(zone.get("desc") or ""))
    return " ".join(parts)


def dresser_keep_line(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    if mentions_six_drawer(_source_blob(lead, deliverable)):
        return _KEEP_SIX
    return _KEEP_FALLBACK


def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _append_unique(items: List[str], line: str) -> List[str]:
    if line and line not in items:
        items.append(line)
    return items


def apply_nursery_rules(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[str]:
    """Mutate a nursery plan in place. Returns issue strings. No-op for other rooms."""
    if not is_nursery_space(lead):
        return []
    issues: List[str] = []
    kept = []
    removed: List[str] = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if item_forbidden(name):
            removed.append(name)
        elif name:
            kept.append(item)
    if removed:
        deliverable["shopping_list"] = kept
        issues.append(
            "removed storage that would replace dresser drawers or add large open cubbies"
        )

    for key in ("intro", "summary", "notes", "budget_note"):
        if deliverable.get(key):
            deliverable[key] = scrub_text(str(deliverable.get(key) or ""))
    for key in ("needs", "strategy", "action_plan", "benefits"):
        deliverable[key] = _dedupe(
            [
                scrub_text(str(item))
                for item in (deliverable.get(key) or [])
                if scrub_text(str(item))
            ]
        )
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            zone["title"] = scrub_text(str(zone.get("title") or ""))
            zone["desc"] = scrub_text(str(zone.get("desc") or ""))

    strategy = list(deliverable.get("strategy") or [])
    keep = dresser_keep_line(lead, deliverable)
    if "dresser" not in " ".join(strategy).lower():
        strategy.insert(0, keep)
    if not any("one step" in line.lower() for line in strategy):
        strategy.append(_ONE_STEP)
    deliverable["strategy"] = strategy

    layers = deliverable.get("blueprint_layers")
    if isinstance(layers, dict):
        instruction = layers.get("customer_instruction")
        if not isinstance(instruction, dict):
            instruction = {}
            layers["customer_instruction"] = instruction
        dont = [str(x) for x in (instruction.get("do_not") or []) if str(x).strip()]
        for line in NURSERY_DO_NOT:
            _append_unique(dont, line)
        instruction["do_not"] = dont
        instruction["do_this_week"] = [
            scrub_text(str(x))
            for x in (instruction.get("do_this_week") or [])
            if scrub_text(str(x))
        ]
        if instruction.get("start_here"):
            instruction["start_here"] = scrub_text(str(instruction.get("start_here") or ""))
        if instruction.get("weekly_reset"):
            instruction["weekly_reset"] = scrub_text(str(instruction.get("weekly_reset") or ""))
    else:
        extra = [str(x) for x in (deliverable.get("safety_lines") or []) if str(x).strip()]
        for line in NURSERY_DO_NOT:
            _append_unique(extra, line)
        deliverable["safety_lines"] = extra

    if removed:
        notes = str(deliverable.get("notes") or "").strip()
        if _REMOVED_NOTE not in notes:
            deliverable["notes"] = (notes + " " + _REMOVED_NOTE).strip()
    return issues


def _record(deliverable: Dict[str, Any], issues: List[str]) -> None:
    if not issues:
        return
    notes = [str(x) for x in (deliverable.get("consistency_notes") or [])]
    for issue in issues:
        if issue not in notes:
            notes.append(issue)
    deliverable["consistency_notes"] = notes


def align_budget(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[str]:
    """Set budget_display from the shopping list. Rewrite a note that under-prices it."""
    issues: List[str] = []
    total = shopping_total(deliverable)
    display = format_money(total) if total else ""
    deliverable["budget_display"] = display
    deliverable["stated_budget"] = stated_budget_label(lead)
    if not total:
        return issues
    note = str(deliverable.get("budget_note") or "")
    if note_conflicts(note, total):
        deliverable["budget_note"] = canonical_budget_note(display)
        issues.append(
            "budget figures did not match the shopping list; the list total is now the only kit price"
        )
    elif not note:
        deliverable["budget_note"] = canonical_budget_note(display)

    layers = deliverable.get("blueprint_layers")
    if isinstance(layers, dict):
        validation = layers.get("validation")
        if isinstance(validation, dict):
            band = validation.get("budget_band")
            if isinstance(band, dict):
                band_text = str(band.get("band") or "")
                stated = deliverable.get("stated_budget") or ""
                if (
                    band_text
                    and note_conflicts(band_text, total)
                    and not _same_phrase(band_text, stated)
                ):
                    band["band"] = display
                    issues.append("budget band was below the shopping-list total and was corrected")
    return issues


def _same_phrase(a: str, b: str) -> bool:
    def norm(value: str) -> str:
        return re.sub(r"\s+", "", (value or "").lower()).replace("–", "-").replace("—", "-")

    left, right = norm(a), norm(b)
    return bool(left) and left == right


def prepare_deliverable(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a copy safe to render. Idempotent."""
    lead = lead or {}
    out = copy.deepcopy(deliverable or {})
    issues = apply_nursery_rules(lead, out)
    issues.extend(align_budget(lead, out))
    _record(out, issues)
    return out


def search_links(deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    """Prefer admin-curated links. Otherwise a retailer search, not an invented SKU."""
    provided = []
    for link in deliverable.get("shopping_links") or []:
        if not isinstance(link, dict):
            continue
        name = str(link.get("name") or link.get("url") or "").strip()
        url = str(link.get("url") or "").strip()
        if name or url:
            provided.append({"name": name or url, "url": url})
    if provided:
        return provided
    links = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        links.append(
            {
                "name": name,
                "url": f"https://www.target.com/s?searchTerm={quote_plus(name)}",
            }
        )
    return links


def _climate_lines(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[str]:
    blobs: List[str] = []
    for key in ("strategy", "action_plan", "needs", "benefits"):
        blobs.extend(str(x) for x in (deliverable.get(key) or []))
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict) and zone.get("desc"):
            blobs.append(str(zone.get("desc")))
    if deliverable.get("notes"):
        blobs.append(str(deliverable.get("notes")))
    lines: List[str] = []
    for blob in blobs:
        text = " ".join(blob.split())
        if text and _CLIMATE.search(text) and text not in lines:
            lines.append(text)
    if is_nursery_space(lead):
        standing = (
            "Keep sleep comfort in a normal nursery range, about 68–72°F, using the heating you already have. "
            "Do not add a portable heater, electric blanket, or loose cord near the crib."
        )
    else:
        standing = (
            "Use the heating and cooling already in the room. This plan does not add portable heaters or new vents."
        )
    if standing not in lines:
        lines.append(standing)
    return lines[:6]


def _maintenance(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    layers = deliverable.get("blueprint_layers") if isinstance(deliverable.get("blueprint_layers"), dict) else {}
    instruction = layers.get("customer_instruction") if isinstance(layers.get("customer_instruction"), dict) else {}
    reset = " ".join(str(instruction.get("weekly_reset") or "").split())
    if reset:
        return reset
    if is_nursery_space(lead):
        return (
            "Once a week, take ten minutes: check that the dresser is still anchored, "
            "the crib is bare except a fitted sheet, the floor path is clear, and the room is a comfortable temperature. "
            "Put diaper supplies back in the existing drawers."
        )
    return (
        "Once a week, take ten minutes to return each item to its home, clear the floor path, and wipe one surface. "
        "The reset keeps the system. It is not a remodel."
    )


def companion_sections(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Long-form companion copy plus the prepared deliverable."""
    lead = lead or {}
    doc = prepare_deliverable(lead, deliverable)
    layers = doc.get("blueprint_layers") if isinstance(doc.get("blueprint_layers"), dict) else {}
    instruction = layers.get("customer_instruction") if isinstance(layers.get("customer_instruction"), dict) else {}
    steps = [
        str(x).strip()
        for x in (instruction.get("do_this_week") or doc.get("action_plan") or [])
        if str(x).strip()
    ]
    if not steps:
        steps = ["Start with a clear floor path, then give everyday items a home you already have."]
    safety: List[str] = []
    for source in (instruction.get("do_not") or []), (doc.get("safety_lines") or []):
        for line in source:
            text = str(line).strip()
            if text and text not in safety:
                safety.append(text)
    if not safety:
        safety = [
            "Do not add walls, windows, or doors.",
            "Do not invent room dimensions.",
        ]
    needs = [str(x).strip() for x in (doc.get("needs") or []) if str(x).strip()]
    if not needs:
        needs = ["A clear floor path", "A home for everyday items"]
    zones = []
    for zone in doc.get("zones") or []:
        if isinstance(zone, dict) and (zone.get("title") or zone.get("desc")):
            zones.append({"title": str(zone.get("title") or "Zone"), "desc": str(zone.get("desc") or "")})
        elif isinstance(zone, str) and zone.strip():
            zones.append({"title": zone.strip(), "desc": ""})
    space = str(lead.get("space_type") or "space").replace("_", " ")
    intro = str(doc.get("intro") or "").strip() or (
        f"A calmer {space} — organized around the room you already have."
    )
    removed = _REMOVED_NOTE if _REMOVED_NOTE in str(doc.get("notes") or "") else ""
    sections = {
        "intro": intro,
        "needs": needs,
        "zones": zones,
        "steps": steps,
        "safety": safety,
        "climate": _climate_lines(lead, doc),
        "maintenance": _maintenance(lead, doc),
        "list_total": doc.get("budget_display") or "—",
        "stated_budget": doc.get("stated_budget") or "",
        "budget_note": str(doc.get("budget_note") or ""),
        "links": search_links(doc),
        "links_are_search": not any(
            isinstance(link, dict) and link.get("url") for link in (deliverable or {}).get("shopping_links") or []
        ),
        "removed_note": removed,
        "notes": str(doc.get("notes") or "").strip(),
    }
    return sections, doc
