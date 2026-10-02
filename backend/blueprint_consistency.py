"""Make a Blueprint agree with itself before it is drawn or emailed.

The rejected kids' room PDF showed two kit prices and storage advice that
would replace a dresser. A later pass also priced the kit at $150 in the
prose while a blanket line pushed the shopping list to $230, and it mixed
"add a heater / blanket layer" with "do not add a heater or a crib blanket".

This module is the single place that:

- drops nursery recommendations that swap drawers for baskets, add large cubbies, or sell a blanket
- rewrites every kit-price claim so it matches the shopping-list total
- keeps one safety story for the board and the companion PDF
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


def item_is_blanket_sku(name: str) -> bool:
    """Bedding blankets are not a shopping line. A window treatment is not a blanket."""
    n = (name or "").lower()
    if "blanket" not in n:
        return False
    if any(word in n for word in ("curtain", "window", "shade", "drape")):
        return False
    return True


def clarify_item_name(name: str) -> str:
    if "blanket" in (name or "").lower() and any(
        word in name.lower() for word in ("curtain", "window", "shade", "drape")
    ):
        return re.sub(r"blanket[-\s]?layer", "thermal window layer", name, flags=re.I)
    return name


def clarify_blanket_wording(text: str) -> str:
    """A warmer window is a thermal window layer, not a blanket product.

    Safety lines that forbid a blanket ("not a blanket", "no loose blankets") stay put.
    """
    if not text:
        return ""
    text = re.sub(r"\bblanket[-\s]?layer\b", "thermal window layer", str(text), flags=re.I)

    def repl(match: re.Match) -> str:
        chunk = match.group(0)
        if re.search(r"\b(not a|no|do not|don't|never)\b", chunk, re.I):
            return chunk
        return re.sub(r"\bblanket\b", "thermal window layer", chunk, count=1, flags=re.I)

    return re.sub(
        r"\b(?:window|curtain|shade|drape)s?\b[^.]{0,60}\bblanket\b",
        repl,
        text,
        flags=re.I,
    )


_SENTENCE_SPLIT = re.compile(r"[^.!?\n]+[.!?]?")
_DO_NOT_LINE = re.compile(r"\b(do not|don't|never|no loose|no portable)\b", re.I)
_ADD_HEATER = re.compile(r"\b(add|install|use|consider|place|buy|mount|get)\b", re.I)
_HEATER_WORD = re.compile(r"\b(heaters?|space heater)\b", re.I)
_BUY_BLANKET = re.compile(r"\b(buy|purchase|shop|include|add)\b[^.]{0,48}\bblanket\b", re.I)
_PRICE_CLAIM = re.compile(
    r"\b(total|budget|estimated|estimate|approx(?:imately)?|about|around|typical|kit|refresh)\b",
    re.I,
)
_BLANKET_NOTE = (
    "We left bedding blankets off the shopping list. The crib stays bare except a fitted sheet, "
    "and a warmer window is a thermal curtain or shade, not a blanket."
)

NURSERY_SAFETY = (
    "Anchor the dresser to the wall and keep every drawer.",
    "The crib stays clear except a fitted sheet and a wearable sleep sack — no teddy bears, loose cushions, pillows, loose blankets, or bumpers.",
    "Do not add a portable heater, wall heater, or electric blanket near the sleep area.",
    "Keep window cords out of reach.",
    "Keep a clear floor path to the door.",
)


def _drop_recommendation_sentences(text: str) -> str:
    kept: List[str] = []
    for match in _SENTENCE_SPLIT.findall(text or ""):
        sentence = " ".join(match.split()).strip()
        if not sentence:
            continue
        if _DO_NOT_LINE.search(sentence):
            kept.append(sentence)
            continue
        if _HEATER_WORD.search(sentence) and _ADD_HEATER.search(sentence):
            continue
        if _BUY_BLANKET.search(sentence):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def clarify_plan_text(text: str) -> str:
    return _drop_recommendation_sentences(clarify_blanket_wording(scrub_text(text)))


def _keep_safety_line(text: str) -> bool:
    if "blanket layer" in text.lower():
        return False
    if _DO_NOT_LINE.search(text):
        return True
    if _HEATER_WORD.search(text) and _ADD_HEATER.search(text):
        return False
    if _BUY_BLANKET.search(text):
        return False
    return True


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
    removed_blanket = False
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        name = clarify_item_name(str(item.get("name") or ""))
        item["name"] = name
        if item_forbidden(name) or item_is_blanket_sku(name):
            removed.append(name)
            if item_is_blanket_sku(name):
                removed_blanket = True
        elif name:
            kept.append(item)
    if removed:
        deliverable["shopping_list"] = kept
    if any(item_forbidden(name) for name in removed):
        issues.append(
            "removed storage that would replace dresser drawers or add large open cubbies"
        )
    if removed_blanket:
        issues.append("removed a blanket product so the shopping list matches the crib safety rule")

    for key in ("intro", "summary", "notes", "budget_note"):
        if deliverable.get(key):
            deliverable[key] = clarify_plan_text(str(deliverable.get(key) or ""))
    for key in ("needs", "strategy", "action_plan", "benefits"):
        deliverable[key] = _dedupe(
            [
                clarify_plan_text(str(item))
                for item in (deliverable.get(key) or [])
                if clarify_plan_text(str(item))
            ]
        )
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            zone["title"] = clarify_plan_text(str(zone.get("title") or ""))
            zone["desc"] = clarify_plan_text(str(zone.get("desc") or ""))

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
            clarify_plan_text(str(x))
            for x in (instruction.get("do_this_week") or [])
            if clarify_plan_text(str(x))
        ]
        if instruction.get("start_here"):
            instruction["start_here"] = clarify_plan_text(str(instruction.get("start_here") or ""))
        if instruction.get("weekly_reset"):
            instruction["weekly_reset"] = clarify_plan_text(str(instruction.get("weekly_reset") or ""))
    else:
        extra = [str(x) for x in (deliverable.get("safety_lines") or []) if str(x).strip()]
        for line in NURSERY_DO_NOT:
            _append_unique(extra, line)
        deliverable["safety_lines"] = extra

    if removed and not removed_blanket:
        notes = str(deliverable.get("notes") or "").strip()
        if _REMOVED_NOTE not in notes:
            deliverable["notes"] = (notes + " " + _REMOVED_NOTE).strip()
    if removed_blanket:
        notes = str(deliverable.get("notes") or "").strip()
        if _BLANKET_NOTE not in notes:
            deliverable["notes"] = (notes + " " + _BLANKET_NOTE).strip()
        if any(item_forbidden(name) for name in removed):
            if _REMOVED_NOTE not in notes and _REMOVED_NOTE not in str(deliverable.get("notes") or ""):
                deliverable["notes"] = (str(deliverable.get("notes") or "") + " " + _REMOVED_NOTE).strip()
    return issues


def _record(deliverable: Dict[str, Any], issues: List[str]) -> None:
    if not issues:
        return
    notes = [str(x) for x in (deliverable.get("consistency_notes") or [])]
    for issue in issues:
        if issue not in notes:
            notes.append(issue)
    deliverable["consistency_notes"] = notes


def _strip_stated_band(text: str, stated: str) -> str:
    if not stated:
        return text
    variants = {
        stated,
        stated.replace("–", "-"),
        stated.replace("—", "-"),
        stated.replace("-", "–"),
    }
    out = text
    for variant in variants:
        if variant:
            out = re.sub(re.escape(variant), " ", out, flags=re.I)
    return out


def _stated_band_only(text: str, stated: str, total: float) -> bool:
    """True when the only money in the sentence is the customer's stated budget band."""
    if not stated or not text:
        return False
    folded = re.sub(r"\s+", "", text.lower().replace("–", "-").replace("—", "-"))
    band = re.sub(r"\s+", "", stated.lower().replace("–", "-").replace("—", "-"))
    if band not in folded:
        return False
    return not note_conflicts(_strip_stated_band(text, stated), total)


def rewrite_kit_prices(text: str, total: float, display: str, stated: str, *, aggressive: bool = False) -> str:
    """Replace a kit price that is not the shopping-list total.

    A stated budget band the kit sits inside is left alone. Line-item prices
    in strategy copy are left alone unless the sentence claims a kit total.
    ``aggressive`` rewrites intro, summary, and notes even without a claim word.
    """
    if not text or total <= 0 or not display:
        return text
    if _stated_band_only(text, stated, total):
        return text
    if not note_conflicts(text, total):
        return text
    if not aggressive and not _PRICE_CLAIM.search(text):
        return text

    def repl_range(match: re.Match) -> str:
        lo = float(match.group(1).replace(",", ""))
        hi = float(match.group(2).replace(",", ""))
        if total > max(lo, hi) + 1:
            return display
        return match.group(0)

    updated = _RANGE.sub(repl_range, text)
    ranges_left = [match.span() for match in _RANGE.finditer(updated)]

    def repl_single(match: re.Match) -> str:
        if any(start <= match.start() < end for start, end in ranges_left):
            return match.group(0)
        amount = float(match.group(1).replace(",", ""))
        if abs(amount - total) <= 1:
            return match.group(0)
        return display

    return _MONEY.sub(repl_single, updated)


def _rewrite_doc_prices(deliverable: Dict[str, Any], total: float, display: str, stated: str) -> bool:
    changed = False
    for key in ("intro", "summary", "notes", "budget_note"):
        raw = str(deliverable.get(key) or "")
        if not raw:
            continue
        updated = rewrite_kit_prices(raw, total, display, stated, aggressive=True)
        if updated != raw:
            deliverable[key] = updated
            changed = True
    for key in ("needs", "strategy", "action_plan", "benefits"):
        rows = []
        field_changed = False
        for item in deliverable.get(key) or []:
            raw = str(item)
            updated = rewrite_kit_prices(raw, total, display, stated, aggressive=False)
            rows.append(updated)
            if updated != raw:
                field_changed = True
        if field_changed:
            deliverable[key] = rows
            changed = True
    for zone in deliverable.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        for key in ("title", "desc"):
            raw = str(zone.get(key) or "")
            updated = rewrite_kit_prices(raw, total, display, stated, aggressive=False)
            if updated != raw:
                zone[key] = updated
                changed = True
    return changed


def align_budget(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[str]:
    """Set budget_display from the shopping list. Rewrite copy that prices the kit differently."""
    issues: List[str] = []
    total = shopping_total(deliverable)
    display = format_money(total) if total else ""
    deliverable["budget_display"] = display
    stated = stated_budget_label(lead)
    deliverable["stated_budget"] = stated
    if not total:
        return issues
    if _rewrite_doc_prices(deliverable, total, display, stated):
        issues.append(
            "budget figures did not match the shopping list; the list total is now the only kit price"
        )
    note = str(deliverable.get("budget_note") or "")
    if note and note_conflicts(note, total) and not _stated_band_only(note, stated, total):
        deliverable["budget_note"] = canonical_budget_note(display)
        if "budget figures did not match the shopping list; the list total is now the only kit price" not in issues:
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
                if (
                    band_text
                    and note_conflicts(band_text, total)
                    and not _same_phrase(band_text, stated)
                    and not _stated_band_only(band_text, stated, total)
                ):
                    band["band"] = display
                    issues.append("budget band was below the shopping-list total and was corrected")
                band_note = str(band.get("note") or "")
                updated_note = rewrite_kit_prices(band_note, total, display, stated, aggressive=True)
                if updated_note != band_note:
                    band["note"] = updated_note
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
    nursery = is_nursery_space(lead)
    for blob in blobs:
        text = " ".join(blob.split())
        if nursery:
            text = clarify_plan_text(text)
        if text and _CLIMATE.search(text) and text not in lines and _keep_safety_line(text):
            lines.append(text)
    if nursery:
        standing = (
            "Keep sleep comfort in a normal nursery range, about 68–72°F, using the heating you already have. "
            "Warm the window with a thermal curtain or shade — a thermal window layer, not a blanket. "
            "Do not add a portable heater, wall heater, or electric blanket."
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
            "the crib holds only a fitted sheet and a wearable sleep sack, the floor path is clear, and the room is a comfortable temperature. "
            "Put diaper supplies back in the existing drawers."
        )
    return (
        "Once a week, take ten minutes to return each item to its home, clear the floor path, and wipe one surface. "
        "The reset keeps the system. It is not a remodel."
    )


def safety_guidance(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None) -> List[str]:
    """One safety list for the image board and the companion PDF."""
    lead = lead or {}
    deliverable = deliverable or {}
    lines: List[str] = []
    if is_nursery_space(lead):
        lines.extend(NURSERY_SAFETY)
    layers = deliverable.get("blueprint_layers") if isinstance(deliverable.get("blueprint_layers"), dict) else {}
    instruction = layers.get("customer_instruction") if isinstance(layers.get("customer_instruction"), dict) else {}
    extras: List[str] = []
    for source in (instruction.get("do_not") or []), (deliverable.get("safety_lines") or []):
        for line in source:
            text = clarify_blanket_wording(str(line).strip())
            if text and _keep_safety_line(text):
                extras.append(text)
    for text in extras:
        if text not in lines:
            lines.append(text)
    if not lines:
        lines = [
            "Do not add walls, windows, or doors.",
            "Do not invent room dimensions.",
        ]
    return lines


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
    safety = safety_guidance(lead, doc)
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
