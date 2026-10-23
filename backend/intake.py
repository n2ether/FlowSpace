"""Beta intake: server-side validation and the shared project fact sheet.

The four-screen intake posts its structured answers as ``lead["intake"]``.
This module re-checks the rules the browser enforces (the browser is not
trusted), decides whether a lead may be charged for a personalized plan, and
builds the one fact sheet every deliverable — Design Plan, Room Flow and
Companion Guide — reads, with stable photo / item / measurement IDs.

Pure functions only: no FastAPI or Mongo, so they are unit-tested directly.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

INTAKE_VERSION = "beta-4screen-v1"

PRIORITIES = {
    "everyday_use": "Easier everyday use",
    "storage": "More useful storage",
    "less_clutter": "Less visual clutter",
    "better_layout": "Better room layout",
    "calmer_look": "A calmer, more cohesive look",
}
KEEP = {
    "keep_all": "Keep all current furniture",
    "keep_selected": "Keep selected items",
    "open": "Open to replacements",
}
LIMITS = {
    "no_drilling": "No drilling",
    "no_painting": "No painting",
    "keep_layout": "Keep the layout",
    "easy_reach": "Easy-to-reach storage",
    "other": "Other",
    "none": "No specific limits",
}
NO_DRILLING_RULE = (
    "No drilling: recommend only freestanding, over-door, tension or removable adhesive options. "
    "Do not suggest wall-mounted, ceiling-mounted, screwed-in or wall-anchored items."
)
BUDGETS = {
    "use_owned": "Use what I own",
    "under_100": "Under $100",
    "100_300": "$100–$300",
    "300_700": "$300–$700",
    "700_plus": "$700+",
    "open": "Open budget (no cap)",
    "not_sure": "Not sure yet",
}
VISUAL_MODES = {"match_current", "choose_style", "suggest"}
SHOTS = {"wide", "detail"}
COVERAGE = {"whole", "partial"}
MEASURE_MODES = {"provided", "not_to_scale"}
ROOM_FLOW_MODES = {"measured", "not_to_scale", "conceptual"}

ROOM_FLOW_NOTES = {
    "measured": "Functional map using the customer's confirmed measurements. Furniture footprints and zones stay approximate.",
    "not_to_scale": "Functional map, not to scale. Do not state exact dimensions, clearances, or product fit.",
    "conceptual": "Conceptual zone diagram. Not based on the customer's room and not to scale. Do not draw a room outline.",
}

OUT_OF_SCOPE_RE = re.compile(
    r"\b(whole (house|home|apartment|flat)|entire (house|home)|every room|yard|garden|lawn|patio|deck|pool|roof|"
    r"exterior|outside|office building|store|shop floor|restaurant|warehouse|commercial|car interior|boat|rv|camper)\b",
    re.I,
)


# Hard ceiling for an admin per-lead photo override (test / QA projects only).
# Customer plan caps live in server.PACKAGES and are never raised by this.
PHOTO_OVERRIDE_MAX = 6
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_PREVIEW_ENVS = {"development", "dev", "local", "test", "preview", "staging"}


def photo_override_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """Whether admins may raise a lead's photo cap on this deployment.

    ``ADMIN_PHOTO_OVERRIDE=1`` turns it on, ``=0`` off. Unset, it is on only
    for development / preview / staging environments, never in production.
    """
    import os

    env = os.environ if env is None else env
    flag = str(env.get("ADMIN_PHOTO_OVERRIDE") or "").strip().lower()
    if flag in _TRUE:
        return True
    if flag in _FALSE:
        return False
    names = {
        str(env.get(key) or "").strip().lower()
        for key in ("ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT")
    }
    if "production" in names or "prod" in names:
        return False
    return bool(names & _PREVIEW_ENVS) or any("preview" in n or "staging" in n for n in names)


def max_photos_for(package: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> int:
    """The plan's photo cap, or the lead's admin override (never above ``PHOTO_OVERRIDE_MAX``)."""
    base = int(package.get("max_photos") or 0)
    try:
        override = int((lead or {}).get("photo_limit_override") or 0)
    except (TypeError, ValueError):
        override = 0
    if override > base:
        return min(override, PHOTO_OVERRIDE_MAX)
    return base


class IntakeError(ValueError):
    def __init__(self, code: str, message: str, errors: List[Dict[str, str]]):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors

    def as_detail(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "errors": self.errors}


def _s(value: Any) -> str:
    return " ".join(str(value or "").split())


def _num(value: Any) -> Optional[float]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def wants_layout_change(intake: Dict[str, Any]) -> bool:
    limits = intake.get("limits") or []
    return (
        intake.get("priority") == "better_layout"
        and "keep_layout" not in limits
        and not intake.get("layout_within_current")
    )


def measurements_needed(intake: Dict[str, Any]) -> bool:
    garage_fit = intake.get("space_type") == "garage" and (intake.get("space_answers") or {}).get("vehicle") == "yes"
    return wants_layout_change(intake) or garage_fit or bool(intake.get("needs_exact_fit"))


def unresolved_contradictions(intake: Dict[str, Any]) -> List[Dict[str, str]]:
    limits = intake.get("limits") or []
    out: List[Dict[str, str]] = []
    if "none" in limits and any(item != "none" for item in limits):
        out.append({"field": "limits", "message": "“No specific limits” can't be combined with a selected limit."})
    if intake.get("priority") == "better_layout" and "keep_layout" in limits and not intake.get("layout_within_current"):
        out.append({"field": "limits", "message": "A better layout and “Keep the layout” conflict. Choose one."})
    if intake.get("budget") == "use_owned" and intake.get("needs_exact_fit"):
        out.append({"field": "budget", "message": "“Use what I own” conflicts with needing something new to fit."})
    return out


def accepted_wide_views(intake: Dict[str, Any]) -> int:
    return sum(1 for p in intake.get("photos") or [] if (p or {}).get("shot", "wide") == "wide")


def validate_intake(
    intake: Dict[str, Any],
    *,
    package: Dict[str, Any],
    photos: List[Any],
    lead: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Field errors for a submitted intake. Empty list means valid.

    ``lead`` is only passed for a stored lead, so an admin photo override applies;
    a new customer submission is always held to the plan cap.
    """
    errors: List[Dict[str, str]] = []

    def err(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    if intake.get("version") != INTAKE_VERSION:
        err("submit", "This form is out of date. Refresh the page and try again.")
        return errors

    space = _s(intake.get("space_type"))
    if not space:
        err("space_type", "Choose the type of space.")
    if space == "other":
        name = _s(intake.get("other_label"))
        if len(name) < 2:
            err("other_label", "Tell us which space this is.")
        elif OUT_OF_SCOPE_RE.search(name):
            err("other_label", "The beta plans one indoor room or storage area at a time.")
    if intake.get("priority") not in PRIORITIES:
        err("priority", "Choose what would make the biggest difference.")

    max_photos = max_photos_for(package, lead)
    if len(photos) > max_photos:
        err("photos", f"The {package['name']} plan includes up to {max_photos} photos.")
    paid = float(package.get("price") or 0) > 0
    mode = intake.get("photo_mode")
    if mode == "conceptual":
        if paid:
            err("photos", "Paid plans need at least one clear, wide photo of your space.")
        if photos:
            err("photos", "A conceptual plan can't include photos.")
    else:
        if not photos or accepted_wide_views(intake) < 1:
            err(
                "photos",
                "Add one clear, wide photo. We don't charge for a personalized plan without a usable photo of your space.",
            )
        listed = [str((p or {}).get("url") or "") for p in intake.get("photos") or []]
        if [str(u) for u in photos] != listed:
            err("photos", "Your photo list changed. Go back to Photos and check them again.")
        for p in intake.get("photos") or []:
            if (p or {}).get("shot", "wide") not in SHOTS:
                err("photos", "Each photo must be a wide view or a close-up.")
                break
        if intake.get("coverage") not in COVERAGE:
            err("coverage", "Tell us whether your photos show the whole area.")

    if intake.get("keep") not in KEEP:
        err("keep", "Tell us what needs to stay.")
    if intake.get("keep") == "keep_selected" and len(_s(intake.get("keep_items"))) < 2:
        err("keep_items", "List the items that need to stay.")
    limits = intake.get("limits") or []
    if not limits or any(item not in LIMITS for item in limits):
        err("limits", "Choose any limits, or “No specific limits”.")
    if "other" in limits and len(_s(intake.get("limit_other"))) < 2:
        err("limit_other", "Describe the other limit.")
    if intake.get("budget") not in BUDGETS:
        err("budget", "Choose a budget for changes and purchases, or “Not sure yet”.")

    visual = intake.get("visual") or {}
    if visual.get("mode", "match_current") not in VISUAL_MODES:
        err("visual_mode", "Choose a visual preference.")

    if measurements_needed(intake):
        m_mode = intake.get("measure_mode")
        if m_mode not in MEASURE_MODES:
            err("measure_mode", "Add measurements, or choose a functional map that is not to scale.")
        elif m_mode == "provided":
            m = intake.get("measurements") or {}
            if _num(m.get("width")) is None:
                err("measure_width", "Enter the width.")
            if _num(m.get("length")) is None:
                err("measure_length", "Enter the length.")

    if package.get("id") == "premium" and intake.get("budget") not in (None, "", "use_owned"):
        if not _s(intake.get("shop_country")):
            err("shop_country", "Choose where you'll shop.")

    errors.extend(unresolved_contradictions(intake))
    return errors


def chargeable_block_reason(lead: Dict[str, Any], package: Dict[str, Any]) -> Optional[str]:
    """Why a paid plan must not be charged yet; ``None`` when checkout may proceed.

    Applies to every paid lead, with or without a structured intake: no
    personalized charge without usable visual evidence.
    """
    if float(package.get("price") or 0) <= 0:
        return None
    photos = lead.get("photos") or []
    if not photos:
        return "Add one clear, wide photo of your space before payment."
    intake = lead.get("intake")
    if isinstance(intake, dict):
        if intake.get("photo_mode") == "conceptual" or accepted_wide_views(intake) < 1:
            return "Add one clear, wide photo of your space before payment."
    if len(photos) > max_photos_for(package, lead):
        return f"The {package.get('name')} plan includes up to {package.get('max_photos')} photos."
    return None


def room_flow_mode(intake: Dict[str, Any]) -> str:
    if intake.get("photo_mode") == "conceptual":
        return "conceptual"
    if measurements_needed(intake) and intake.get("measure_mode") == "provided":
        return "measured"
    return "not_to_scale"


def _split_items(text: str) -> List[str]:
    parts = re.split(r"[;\n]|,(?![^()]*\))", text or "")
    return [p.strip(" .-") for p in parts if p.strip(" .-")]


def build_fact_sheet(lead: Dict[str, Any]) -> Dict[str, Any]:
    """The single record of project facts. IDs here are the IDs every deliverable uses.

    Photos are P1..Pn in lead order and map to SOURCE_01..; each accepted
    source gets exactly one AFTER_nn. Kept items are K1.., measurements M1..
    Unknowns are listed rather than guessed.
    """
    intake = lead.get("intake") or {}
    photo_urls = [str(u) for u in lead.get("photos") or []]
    by_url = {str((p or {}).get("url")): p for p in intake.get("photos") or []}
    photos = []
    for i, url in enumerate(photo_urls, start=1):
        meta = by_url.get(url) or {}
        photos.append(
            {
                "id": f"P{i}",
                "label": f"Photo {i}",
                "custom_label": _s(meta.get("custom_label")),
                "shot": meta.get("shot") or "wide",
                "url": url,
                "photo_id": url.rsplit("/", 1)[-1],
                "source_label": f"SOURCE_{i:02d}",
                "after_label": f"AFTER_{i:02d}",
            }
        )

    keep = intake.get("keep") or ""
    keep_items = (
        [{"id": f"K{i}", "text": t} for i, t in enumerate(_split_items(intake.get("keep_items") or ""), start=1)]
        if keep == "keep_selected"
        else []
    )

    measurements: List[Dict[str, Any]] = []
    m = intake.get("measurements") or {}
    if intake.get("measure_mode") == "provided" and m:
        unit = _s(m.get("unit")) or "ft"
        for key, label in (("width", "Area width"), ("length", "Area length")):
            value = _num(m.get(key))
            if value is not None:
                measurements.append({"id": f"M{len(measurements) + 1}", "what": label, "value": value, "unit": unit})
        for key, label in (("fixed", "Doors, windows and fixed items"), ("items", "Items or spot that must fit")):
            if _s(m.get(key)):
                measurements.append({"id": f"M{len(measurements) + 1}", "what": label, "note": _s(m.get(key))})

    mode = room_flow_mode(intake) if intake else "not_to_scale"
    limits = [l for l in intake.get("limits") or [] if l in LIMITS]
    limit_labels = [
        f"Other: {_s(intake.get('limit_other'))}" if l == "other" else LIMITS[l] for l in limits if l != "none"
    ]
    budget = intake.get("budget") or lead.get("budget") or ""

    unknowns: List[str] = []
    if mode != "measured":
        unknowns.append("Room dimensions and clearances are not confirmed.")
    if intake.get("coverage") == "partial":
        unknowns.append("Areas outside the photos are unknown; plan only the documented area.")
    if mode == "conceptual":
        unknowns.append("No photos: the customer's room layout, furniture and openings are unknown.")
    if budget == "not_sure":
        unknowns.append("Budget not set: prioritise reorganising owned items; purchases optional.")

    visual = intake.get("visual") or {}
    space_type = intake.get("space_type") or lead.get("space_type") or ""
    return {
        "version": INTAKE_VERSION,
        "lead_id": lead.get("id"),
        "plan": lead.get("package_id") or intake.get("plan") or "free",
        "space": {
            "type": space_type,
            "label": _s(intake.get("other_label")) if space_type == "other" else space_type.replace("_", " "),
        },
        "priority": {"id": intake.get("priority") or "", "label": PRIORITIES.get(intake.get("priority") or "", "")},
        "specifics": _s(intake.get("specifics")),
        "photos": photos,
        "coverage": intake.get("coverage") or ("none" if mode == "conceptual" else ""),
        "conceptual": mode == "conceptual",
        "keep": {"mode": keep, "label": KEEP.get(keep, ""), "items": keep_items},
        "limits": {"ids": limits, "labels": limit_labels, "none": limits == ["none"]},
        "layout_within_current": bool(intake.get("layout_within_current")),
        "change_avoid": _s(intake.get("change_avoid")),
        "budget": {"id": budget, "label": BUDGETS.get(budget, "")},
        "visual": {
            "mode": visual.get("mode") or "match_current",
            "style": visual.get("style") or "",
            "palette": visual.get("palette") or "",
        },
        "space_answers": intake.get("space_answers") or {},
        "measurements": measurements,
        "room_flow": {"mode": mode, "note": ROOM_FLOW_NOTES[mode]},
        "climate": _s(intake.get("climate")),
        "shopping": {"country": _s(intake.get("shop_country")), "postal": _s(intake.get("shop_postal"))},
        "unknowns": unknowns,
    }


def fact_sheet_prompt(fact_sheet: Optional[Dict[str, Any]]) -> str:
    """Prompt block for the drafter. Same facts, same IDs, for every deliverable."""
    if not fact_sheet:
        return ""
    fs = fact_sheet
    lines = ["", "PROJECT FACT SHEET (authoritative — every deliverable uses these facts and IDs):"]
    lines.append(f"- Space: {fs['space']['label']}. Main priority: {fs['priority']['label'] or 'not stated'}.")
    if fs.get("specifics"):
        lines.append(f"- Customer wants to solve: {fs['specifics']}")
    if fs.get("conceptual"):
        lines.append("- CONCEPTUAL PLAN: no customer photos. Present ideas for this type of space; never call an image the customer's room.")
    else:
        refs = ", ".join(
            f"{p['id']} ({p['label']}{' — ' + p['custom_label'] if p['custom_label'] else ''}, {p['shot']})"
            for p in fs["photos"]
        )
        lines.append(f"- Photos: {refs}. One after-view per photo; do not invent angles.")
        if fs.get("coverage") == "partial":
            lines.append("- Coverage: PARTIAL. Plan only the areas the photos show.")
    keep = fs["keep"]
    if keep["items"]:
        lines.append("- Must keep: " + "; ".join(f"{k['id']} {k['text']}" for k in keep["items"]))
    elif keep["label"]:
        lines.append(f"- Keep: {keep['label']}.")
    if fs["limits"]["labels"]:
        lines.append("- Limits to respect: " + ", ".join(fs["limits"]["labels"]) + ".")
        if "no_drilling" in fs["limits"]["ids"]:
            lines.append(f"- {NO_DRILLING_RULE}")
    elif fs["limits"]["none"]:
        lines.append("- Limits: customer stated no specific limits.")
    if fs.get("layout_within_current"):
        lines.append("- Keep the current layout; improve within it.")
    if fs.get("change_avoid"):
        lines.append(f"- Change or avoid: {fs['change_avoid']}")
    if fs["budget"]["label"]:
        lines.append(f"- Budget for changes and purchases: {fs['budget']['label']}.")
    if fs["budget"]["id"] == "use_owned":
        lines.append("- Use only what the customer owns; no shopping list beyond optional labels.")
    v = fs["visual"]
    if v["mode"] == "choose_style":
        lines.append(f"- Visual: style {v['style']}, palette {v['palette']} (textiles/accessories only; no repaint or furniture replacement implied).")
    elif v["mode"] == "match_current" and not fs.get("conceptual"):
        lines.append("- Visual: match the current space.")
    if fs.get("space_answers"):
        lines.append(f"- Use of the space: {fs['space_answers']}")
    for m in fs["measurements"]:
        if "value" in m:
            lines.append(f"- {m['id']} {m['what']}: {m['value']} {m['unit']}")
        else:
            lines.append(f"- {m['id']} {m['what']}: {m['note']}")
    lines.append(f"- Room Flow: {fs['room_flow']['note']}")
    if fs.get("climate"):
        lines.append(f"- Condition to account for: {fs['climate']} (practical tips only, no technical diagnosis).")
    if fs["shopping"]["country"]:
        lines.append(f"- Shopping market: {fs['shopping']['country']}.")
    for u in fs.get("unknowns") or []:
        lines.append(f"- Unknown: {u}")
    return "\n".join(lines)
