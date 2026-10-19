"""One set of facts for the three pieces of a package.

The Design Plan board, the Room Flow sheet, the Companion Guide, and the phone
page all read their items, prices, totals, steps, and size rules from here, so
a version never says one thing on the board and another in the guide.

Rules applied to the plan before anything is drawn (``apply_package_rules``):

- A playpen is an item inside a zone, never a zone of its own.
- Without wall, table, or niche measurements, a frame or basket never carries an
  exact size; the copy says "measure before buying" instead.

Facts read at render time (``package_facts``):

- Every shopping row is functional or optional decorative, with one link that is
  either a direct tested product page or a labeled reference search.
- The total is computed from the rows, names the catch-all it includes, and is
  before tax and shipping (general standard).
- The three roadmap steps and the six process steps.
- The package version and its review label.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from design_plan_standards import (
    GENERAL_ROADMAP,
    LINK_REFERENCE,
    LINK_TESTED,
    MEASURE_BEFORE_BUYING,
    PROCESS_STEPS,
    SHOPPING_DECORATIVE,
    SHOPPING_FUNCTIONAL,
    SNAPSHOT_TOTAL_LABEL,
    TAX_SHIPPING_NOTE,
    WHAT_STAYS_CHIPS,
    WHAT_STAYS_TEXT,
    is_released,
    package_version,
    version_label,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def uses_general_standard(lead: Optional[Dict[str, Any]]) -> bool:
    """Every room except the nursery, which keeps its approved v5 copy."""
    from space_rails import is_nursery_space

    return not is_nursery_space(lead)


# ──────────────────────────── Playpen: an item, not a zone ─────────────────────────────

PLAYPEN = re.compile(r"\b(?:play\s?pens?|play[-\s]?yards?|pack\s?(?:'n'?|n'|n|and|&)\s?plays?)\b", re.I)
PLAYPEN_ITEM = {"name": "Playpen", "class": "item"}


def _playpen_zone_title(title: str) -> str:
    renamed = _clean(PLAYPEN.sub("Play", title))
    renamed = re.sub(r"\bPlay\s+Play\b", "Play", renamed, flags=re.I)
    if not renamed or renamed.lower() in {"zone", "area", "corner", "spot"}:
        return "Play"
    return renamed[:1].upper() + renamed[1:]


def _mentions_playpen(lead: Dict[str, Any], doc: Dict[str, Any]) -> bool:
    blob = [str(lead.get(key) or "") for key in ("must_stay", "goals", "notes", "biggest_challenge")]
    blob += [str(doc.get(key) or "") for key in ("intro", "summary", "notes")]
    for key in ("strategy", "needs", "action_plan"):
        blob += [str(x) for x in doc.get(key) or []]
    for zone in doc.get("zones") or []:
        if isinstance(zone, dict):
            blob += [str(zone.get("title") or ""), str(zone.get("desc") or "")]
    for item in doc.get("shopping_list") or []:
        if isinstance(item, dict):
            blob.append(str(item.get("name") or ""))
    return bool(PLAYPEN.search(" ".join(blob)))


def apply_item_classes(lead: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    """A zone named for the playpen becomes a play zone that holds the playpen as an item."""
    issues: List[str] = []
    for zone in doc.get("zones") or []:
        if not isinstance(zone, dict):
            continue
        title = _clean(zone.get("title"))
        if not PLAYPEN.search(title):
            continue
        zone["title"] = _playpen_zone_title(title)
        items = [str(x) for x in zone.get("items") or []]
        if PLAYPEN_ITEM["name"] not in items:
            items.append(PLAYPEN_ITEM["name"])
        zone["items"] = items
        issues.append("the playpen is an item inside a zone, not a zone")
    for item in doc.get("shopping_list") or []:
        if isinstance(item, dict) and PLAYPEN.search(str(item.get("name") or "")):
            item["item_class"] = "item"
    if _mentions_playpen(lead, doc):
        room_items = [dict(x) for x in doc.get("room_items") or [] if isinstance(x, dict)]
        if not any(_clean(x.get("name")).lower() == "playpen" for x in room_items):
            room_items.append(dict(PLAYPEN_ITEM))
        for entry in room_items:
            if _clean(entry.get("name")).lower() == "playpen":
                entry["class"] = "item"
        doc["room_items"] = room_items
    return issues


# ──────────────────────────── Frame and basket sizes ─────────────────────────────

# Any of these product words plus a size is an invented dimension until the room is measured.
_SIZED_PIECE = re.compile(
    r"\b(?:picture\s+)?(?:frames?|baskets?|bins?|prints?|trays?|pillows?|covers?|cushions?|mats?|rugs?)\b",
    re.I,
)
_UNIT = r"(?:\s?(?:in(?:\.|ches)?\b|\"|”|cm\b|ft\b\.?|feet\b)|-in\.?)"
_NUM = r"(?<![\d$.,])\d+(?:\.\d+)?(?:\s?[-–]\s?\d+(?:\.\d+)?)?"
DIMENSION = re.compile(rf"{_NUM}{_UNIT}?(?:\s?(?:×|x|X|by)\s?{_NUM}{_UNIT}?)+|{_NUM}{_UNIT}")
_MEASURE_KEYS = re.compile(r"wall|table|niche|shelf|console|alcove", re.I)


def has_measurements(lead: Optional[Dict[str, Any]], doc: Optional[Dict[str, Any]]) -> bool:
    """True when the record carries wall, table, or niche measurements (a measured outline counts)."""
    from room_flow import resolve_room_flow

    lead, doc = lead or {}, doc or {}
    if resolve_room_flow(lead, doc).get("outline_source") == "measured":
        return True
    for source in (doc.get("measurements"), lead.get("measurements")):
        if isinstance(source, dict) and any(_MEASURE_KEYS.search(str(k)) and v for k, v in source.items()):
            return True
    return False


def strip_dimensions(text: str) -> str:
    raw = str(text or "")
    out = DIMENSION.sub(" ", raw)
    removed = _clean(out) != _clean(raw)
    out = re.sub(r"\(\s*[,;]?\s*", "(", out)
    out = re.sub(r"\s*[,;]?\s*\)", ")", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+([,.;:)])", r"\1", out)
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\b(an?)\s+(?=an?\b)", "", out)
    if removed:
        # "16x20 inches each" — "each" only qualified the size that was removed.
        out = re.sub(r"\s+\beach\b(?=\s*[.!?]?$)", "", out, flags=re.I)
    return _clean(out).strip(" ,;")


def _measure_sentence(sentence: str) -> str:
    if not (_SIZED_PIECE.search(sentence) and DIMENSION.search(sentence)):
        return sentence
    body = strip_dimensions(sentence).rstrip(".!? ")
    body = re.sub(r"\ban\s+(?=[bcdfghjklmnpqrstvwxyz])", "a ", body, flags=re.I)
    return f"{body} ({MEASURE_BEFORE_BUYING})."


def measure_text(text: str) -> str:
    """Copy with invented product sizes removed and "measure before buying" in their place."""
    sentences = re.findall(r"[^.!?]+(?:[.!?](?!\d)|$)", str(text or ""))
    if not sentences:
        return str(text or "")
    out = " ".join(_measure_sentence(_clean(s)) for s in sentences if _clean(s))
    return out if out != _clean(text) else str(text or "")


def apply_measurement_rule(lead: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    if has_measurements(lead, doc):
        return []
    changed = False
    for item in doc.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        named = " ".join(str(item.get(key) or "") for key in ("name", "short_name"))
        # Any size on a shopping line is invented until the room is measured.
        if not DIMENSION.search(named):
            continue
        for key in ("name", "short_name"):
            if item.get(key):
                stripped = strip_dimensions(str(item[key]))
                if stripped != item[key]:
                    item[key] = stripped
                    changed = True
        item["measure_first"] = True
    for key in ("intro", "summary", "notes", "budget_note"):
        if isinstance(doc.get(key), str) and doc[key]:
            updated = measure_text(doc[key])
            changed = changed or updated != doc[key]
            doc[key] = updated
    for key in ("needs", "strategy", "action_plan", "benefits"):
        rows = [measure_text(str(x)) for x in doc.get(key) or []]
        if rows != [str(x) for x in doc.get(key) or []]:
            doc[key] = rows
            changed = True
    for zone in doc.get("zones") or []:
        if isinstance(zone, dict) and zone.get("desc"):
            updated = measure_text(str(zone["desc"]))
            changed = changed or updated != zone["desc"]
            zone["desc"] = updated
    layers = doc.get("blueprint_layers")
    instruction = layers.get("customer_instruction") if isinstance(layers, dict) else None
    if isinstance(instruction, dict) and instruction.get("do_this_week"):
        instruction["do_this_week"] = [measure_text(str(x)) for x in instruction["do_this_week"]]
    return ["product sizes need measurements; the plan says measure before buying"] if changed else []


def apply_package_rules(lead: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    """Item classes and the measurement rule. Mutates ``doc``; idempotent."""
    return apply_item_classes(lead, doc) + apply_measurement_rule(lead, doc)


# ──────────────────────────── Shopping rows ─────────────────────────────

CATCH_ALL = re.compile(
    r"\bcatch[-\s]?alls?\b|\bvalet\s+tray\b|\bkey\s+(?:tray|bowl|dish)\b|\bentry(?:way)?\s+(?:tray|bowl|dish)\b|\bdrop\s+tray\b",
    re.I,
)
DECORATIVE = re.compile(
    r"\b(?:art|artwork|wall\s+(?:decor|décor|art)|decor|décor|decorative|prints?|posters?|frames?|"
    r"pillows?|pillow\s+covers?|throws?|vases?|plants?|faux|greenery|candles?|garland|wreath|"
    r"sculptures?|figurines?|accent\s+pieces?|bookends?)\b",
    re.I,
)


def item_priority(item: Dict[str, Any]) -> str:
    """``functional`` or ``decorative``. An explicit field wins; the catch-all is always functional."""
    explicit = _clean(item.get("priority") or item.get("category")).lower()
    if explicit in {"functional", "decorative"}:
        return explicit
    if item.get("optional") is True:
        return "decorative"
    name = _clean(item.get("name"))
    if CATCH_ALL.search(name):
        return "functional"
    return "decorative" if DECORATIVE.search(name) else "functional"


def is_catch_all(item: Dict[str, Any]) -> bool:
    return bool(CATCH_ALL.search(_clean(item.get("name")))) or item.get("catch_all") is True


def money(value: float) -> str:
    from blueprint_consistency import format_money

    return format_money(value)


def short_item_name(item: Dict[str, Any]) -> str:
    """Retailer-neutral line for the snapshot. The full product line is in the guide."""
    short = _clean(item.get("short_name"))
    if short:
        return short
    name = _clean(item.get("name"))
    base = re.split(r"\s+\(|,\s|\s[—–-]\s", name, maxsplit=1)[0].strip() or name
    try:
        qty = float(item.get("qty", 1) or 1)
    except (TypeError, ValueError):
        qty = 1.0
    if qty > 1 and qty.is_integer():
        base = f"{base} ({int(qty)})"
    return base


def _link_for(item: Dict[str, Any], by_name: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    from shopping_links import fallback_search_links

    name = _clean(item.get("name"))
    link = dict(by_name.get(name.lower()) or {})
    if not link and name:
        link = (fallback_search_links({"shopping_list": [item]}) or [{}])[0]
    url = _clean(link.get("url"))
    link_type = _clean(link.get("link_type")).lower() or ("search" if "/s?" in url else "product")
    retailer = _clean(link.get("retailer")) or "Target"
    label = _clean(link.get("label")) or (f"Search at {retailer}" if link_type == "search" else f"View at {retailer}")
    tested = link_type == "product" and bool(url) and bool(link.get("verified"))
    kind = "tested" if tested else "reference"
    return {
        "url": url,
        "label": label,
        "retailer": retailer,
        "link_type": link_type,
        "kind": kind,
        "kind_label": LINK_TESTED if tested else LINK_REFERENCE,
    }


def shopping_rows(lead: Dict[str, Any], doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every shopping line of a prepared plan, with its priority, catch-all flag, and link."""
    from shopping_links import resolve_shopping_links

    links = resolve_shopping_links(lead, doc)
    by_name = {_clean(link.get("name")).lower(): link for link in links if isinstance(link, dict)}
    rows: List[Dict[str, Any]] = []
    for item in doc.get("shopping_list") or []:
        if not isinstance(item, dict) or not _clean(item.get("name")):
            continue
        try:
            qty = float(item.get("qty", 1) or 1)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            qty, price = 1.0, 0.0
        name = _clean(item.get("name"))
        subtotal = qty * price
        rows.append(
            {
                "name": name,
                "short": short_item_name(item),
                "qty": int(qty) if qty.is_integer() else qty,
                "unit_price": price,
                "subtotal": subtotal,
                "price": money(subtotal) if subtotal else "Confirm price",
                "priority": item_priority(item),
                "catch_all": is_catch_all(item),
                "measure_first": bool(item.get("measure_first")),
                "item_class": _clean(item.get("item_class")) or "product",
                "link": _link_for(item, by_name),
            }
        )
    return rows


def total_line(total_display: str, catch_all: Optional[Dict[str, Any]], *, general: bool) -> str:
    """The one total sentence. The general standard names the catch-all and the tax and shipping basis."""
    from blueprint_consistency import reference_total_line

    display = _clean(total_display)
    if not display or display in {"—", "-"}:
        return ""
    if not general:
        return reference_total_line(display)
    if catch_all and catch_all.get("subtotal"):
        return (
            f"{SNAPSHOT_TOTAL_LABEL}: {display}, including the {money(catch_all['subtotal'])} catch-all, "
            f"{TAX_SHIPPING_NOTE}."
        )
    return f"{SNAPSHOT_TOTAL_LABEL}: {display}, {TAX_SHIPPING_NOTE}."


def total_note(catch_all: Optional[Dict[str, Any]]) -> str:
    """The board's short line under the total figure."""
    tax = TAX_SHIPPING_NOTE[:1].upper() + TAX_SHIPPING_NOTE[1:]
    if catch_all and catch_all.get("subtotal"):
        return f"Includes the {money(catch_all['subtotal'])} catch-all · {tax}"
    return tax


def roadmap_steps(lead: Dict[str, Any], doc: Dict[str, Any]) -> List[Dict[str, str]]:
    if uses_general_standard(lead):
        return [{"title": title, "body": body, "detail": detail} for title, body, detail in GENERAL_ROADMAP]
    from image_board import _roadmap

    return [{**step, "detail": step["body"]} for step in _roadmap(doc, lead)]


def what_stays(lead: Dict[str, Any], doc: Dict[str, Any]) -> str:
    from ai_drafter import is_keep_existing_wall

    if is_keep_existing_wall(doc):
        return WHAT_STAYS_TEXT
    return "Keep all current furniture."


def what_stays_chips(doc: Dict[str, Any]) -> List[str]:
    from ai_drafter import is_keep_existing_wall

    return list(WHAT_STAYS_CHIPS) if is_keep_existing_wall(doc) else [WHAT_STAYS_CHIPS[1]]


def sent_review_version(deliverable: Optional[Dict[str, Any]]) -> int:
    """The highest package version actually emailed for review. Missing means none."""
    try:
        return max(0, int((deliverable or {}).get("sent_for_review") or 0))
    except (TypeError, ValueError):
        return 0


def next_release(deliverable: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The review copy to prepare next. Never emails and never marks it final.

    The version counts copies sent to the customer for review, not regenerations.
    The original unlabeled package is version 1. Regenerating before anything has
    been emailed prepares Version 2, and further regenerations of that unsent copy
    keep 2 — including a copy whose stored number was bumped by mistake. A package
    already marked final, with no ``sent_for_review``, counts as sent at its
    current version. After a successful send, the next regeneration starts the
    following number; regenerating that newer unsent copy keeps it.
    """
    raw_status = str((deliverable or {}).get("package_status") or "").strip().lower()
    recorded = sent_review_version(deliverable)
    current = package_version(deliverable)
    sent = current if recorded <= 0 and raw_status == "final" else recorded
    status = "review" if raw_status in {"", "final"} else raw_status
    if sent <= 0:
        version = 2
    elif current <= sent:
        version = sent + 1
    else:
        version = current
    release = {
        "package_version": version,
        "version_label": version_label(version),
        "package_status": status,
        "design_plan_approved": False,
        "emailed": False,
    }
    if sent > 0:
        release["sent_for_review"] = sent
    return release


def package_facts(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    *,
    prepared: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Items, prices, totals, steps, size rule, and version for every piece of this package."""
    from blueprint_consistency import prepare_deliverable

    lead = lead or {}
    raw = deliverable or {}
    doc = prepared if prepared is not None else prepare_deliverable(lead, raw)
    general = uses_general_standard(lead)
    rows = shopping_rows(lead, doc)
    functional = [row for row in rows if row["priority"] == "functional"]
    decorative = [row for row in rows if row["priority"] == "decorative"]
    total = sum(row["subtotal"] for row in rows)
    catch_all = next((row for row in rows if row["catch_all"]), None)
    total_display = money(total) if total else "—"
    version = package_version(raw)
    return {
        "general": general,
        "version": version,
        "version_label": version_label(version),
        "released": is_released(raw),
        "items": rows,
        "functional": functional,
        "decorative": decorative,
        "total": total,
        "total_display": total_display,
        "functional_total": money(sum(row["subtotal"] for row in functional)),
        "decorative_total": money(sum(row["subtotal"] for row in decorative)),
        "catch_all": catch_all,
        "total_line": total_line(total_display, catch_all, general=general),
        "total_note": total_note(catch_all) if general else "",
        "tested_links": sum(1 for row in rows if row["link"]["kind"] == "tested"),
        "reference_links": sum(1 for row in rows if row["link"]["kind"] == "reference"),
        "steps": roadmap_steps(lead, doc),
        "measured": has_measurements(lead, doc),
        "measure_items": [row["short"] for row in rows if row["measure_first"]],
        "room_items": [dict(x) for x in doc.get("room_items") or [] if isinstance(x, dict)],
        "what_stays": what_stays(lead, doc) if general else "",
        "process": [{"name": name, "body": body} for name, body in PROCESS_STEPS],
        "groups": [
            {"title": SHOPPING_FUNCTIONAL, "priority": "functional", "items": functional},
            {"title": SHOPPING_DECORATIVE, "priority": "decorative", "items": decorative},
        ],
    }
