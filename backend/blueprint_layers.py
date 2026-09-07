"""
FlowSpace Blueprint Brain layers.

Six explicit reasoning layers — customer-visible on the PDF and persisted
as structured JSON on the deliverable. Not hidden logs.

    1. Observation
    2. Human need
    3. Spatial constraint
    4. Recommendation
    5. Validation
    6. Customer instruction

Ryan bake-off questions map as:
    routine          → human_need.routine
    possessions      → observation.possessions + validation.possession_respect
    physical fit     → spatial_constraint + validation.fit
    budget           → validation.budget_band
    why it should work → recommendation.why_it_should_work + validation checks
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "blueprint_layers.schema.json"

LAYER_KEYS = (
    "observation",
    "human_need",
    "spatial_constraint",
    "recommendation",
    "validation",
    "customer_instruction",
)

LAYER_TITLES = {
    "observation": "Observation",
    "human_need": "Human need",
    "spatial_constraint": "Spatial constraint",
    "recommendation": "Recommendation",
    "validation": "Validation",
    "customer_instruction": "Customer instruction",
}

CHECK_KEYS = ("fit", "flow", "budget_band", "possession_respect")
CHECK_STATUSES = ("pass", "watch", "fail")

BUDGET_LABELS = {
    "under_100": "Under $100",
    "100_300": "$100 – $300",
    "300_700": "$300 – $700",
    "700_plus": "$700+",
}
BOTHERS = {
    "clutter": "Too much clutter",
    "no_storage": "Not enough storage",
    "hard_clean": "Hard to clean",
    "stressful": "Feels stressful/overwhelming",
    "not_cozy": "Doesn't feel cozy",
    "no_function": "Doesn't function well",
    "bad_layout": "Poor furniture layout",
    "too_dark": "Too dark",
    "no_hobby": "No space for hobbies/work",
}
FEELING = {
    "calm": "Calm",
    "cozy": "Cozy",
    "minimal": "Clean / minimal",
    "airy": "Airy / open",
    "elegant": "Elegant",
    "warm": "Warm",
    "functional": "Functional",
    "modern": "Modern",
    "luxurious": "Luxurious",
    "practical": "Practical",
}
STORAGE = {
    "clothing": "Clothing",
    "shoes": "Shoes",
    "paperwork": "Paperwork",
    "hobby": "Hobby / craft items",
    "decor": "Decor",
    "laundry": "Laundry",
    "tools": "Tools",
    "sports": "Sports gear",
}

# Qualitative shell notes only — never invent footage or window counts.
SPACE_SHELL_HINTS = {
    "garage": [
        "Keep the existing parking stall as a destination, not a dump.",
        "Use the walls and door path the photo already shows.",
    ],
    "closet": [
        "Keep the existing rod / shelf run; do not invent a new footprint.",
        "Work within the opening and depth the photo shows.",
    ],
    "laundry": [
        "Keep machines and existing hookups where they are.",
        "Organize around the aisle the photo already allows.",
    ],
    "laundry_room": [
        "Keep machines and existing hookups where they are.",
        "Organize around the aisle the photo already allows.",
    ],
    "pantry": [
        "Keep the existing cabinet/shelf box; no new walls.",
        "Zone by frequency on the shelves already in the photo.",
    ],
    "mudroom": [
        "Keep the door swing and existing bench/hooks if present.",
        "Landing zone stays at the entry the photo shows.",
    ],
    "storage": [
        "Keep the existing shell and access path.",
        "Contain on walls/shelves already in the photo.",
    ],
}


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _as_str_list(v: Any, limit: int = 6) -> List[str]:
    if not v:
        return []
    if isinstance(v, str):
        text = v.strip()
        return [text] if text else []
    out: List[str] = []
    for item in v:
        text = _as_str(item)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _as_bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() not in {"0", "false", "no", ""}
    return bool(v)


def _check(raw: Any, default_note: str = "") -> Dict[str, str]:
    if isinstance(raw, str):
        return {"status": "watch", "note": raw.strip() or default_note}
    data = raw if isinstance(raw, dict) else {}
    status = _as_str(data.get("status")).lower()
    if status not in CHECK_STATUSES:
        status = "watch" if (data or default_note) else "watch"
    note = _as_str(data.get("note")) or default_note
    out = {"status": status, "note": note}
    band = _as_str(data.get("band"))
    if band:
        out["band"] = band
    return out


def empty_layers() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "observation": {
            "space_seen": "",
            "current_state": [],
            "possessions": [],
            "evidence": [],
        },
        "human_need": {
            "routine": "",
            "desired_feeling": "",
            "jobs_to_be_done": [],
            "pain": "",
        },
        "spatial_constraint": {
            "preserve_shell": True,
            "windows_dims_fidelity": "~95%",
            "known_from_photo": [],
            "unknowns": [
                "Exact footage, window counts, and opening sizes were not measured — we do not invent them.",
            ],
            "no_invented_floor_plan": True,
            "paint_optional": True,
        },
        "recommendation": {
            "system": "",
            "zones": [],
            "why_it_should_work": "",
        },
        "validation": {
            "fit": {"status": "watch", "note": ""},
            "flow": {"status": "watch", "note": ""},
            "budget_band": {"status": "watch", "note": "", "band": ""},
            "possession_respect": {"status": "watch", "note": ""},
            "conflicts": [],
            "assumptions": [],
        },
        "customer_instruction": {
            "start_here": "",
            "do_this_week": [],
            "do_not": [
                "Do not add walls, windows, or doors.",
                "Do not invent room dimensions.",
                "Paint is optional — skip it unless it helps the goal.",
            ],
            "weekly_reset": "",
        },
    }


def coerce_layers(raw: Any) -> Dict[str, Any]:
    """Normalize a model/admin payload into the persisted blueprint_layers shape."""
    base = empty_layers()
    data = raw if isinstance(raw, dict) else {}

    obs = data.get("observation") if isinstance(data.get("observation"), dict) else {}
    base["observation"] = {
        "space_seen": _as_str(obs.get("space_seen")),
        "current_state": _as_str_list(obs.get("current_state")),
        "possessions": _as_str_list(obs.get("possessions")),
        "evidence": _as_str_list(obs.get("evidence")),
    }

    need = data.get("human_need") if isinstance(data.get("human_need"), dict) else {}
    feeling = need.get("desired_feeling")
    if isinstance(feeling, list):
        feeling = ", ".join(_as_str_list(feeling, limit=4))
    base["human_need"] = {
        "routine": _as_str(need.get("routine")),
        "desired_feeling": _as_str(feeling),
        "jobs_to_be_done": _as_str_list(need.get("jobs_to_be_done")),
        "pain": _as_str(need.get("pain")),
    }

    spat = data.get("spatial_constraint") if isinstance(data.get("spatial_constraint"), dict) else {}
    fidelity = _as_str(spat.get("windows_dims_fidelity")) or "~95%"
    base["spatial_constraint"] = {
        "preserve_shell": _as_bool(spat.get("preserve_shell"), True),
        "windows_dims_fidelity": fidelity,
        "known_from_photo": _as_str_list(spat.get("known_from_photo")),
        "unknowns": _as_str_list(spat.get("unknowns"))
        or base["spatial_constraint"]["unknowns"],
        "no_invented_floor_plan": _as_bool(spat.get("no_invented_floor_plan"), True),
        "paint_optional": _as_bool(spat.get("paint_optional"), True),
    }

    rec = data.get("recommendation") if isinstance(data.get("recommendation"), dict) else {}
    zones: List[Dict[str, str]] = []
    for z in rec.get("zones") or []:
        if isinstance(z, dict):
            title = _as_str(z.get("title") or z.get("name"))
            why = _as_str(z.get("why") or z.get("role") or z.get("desc"))
            if title or why:
                zones.append({"title": title, "why": why})
        elif isinstance(z, str) and z.strip():
            zones.append({"title": z.strip(), "why": ""})
    base["recommendation"] = {
        "system": _as_str(rec.get("system")),
        "zones": zones[:6],
        "why_it_should_work": _as_str(
            rec.get("why_it_should_work") or rec.get("why")
        ),
    }

    val = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    budget = _check(val.get("budget_band"))
    if not budget.get("band"):
        budget["band"] = _as_str(val.get("band"))
    base["validation"] = {
        "fit": _check(val.get("fit")),
        "flow": _check(val.get("flow")),
        "budget_band": budget,
        "possession_respect": _check(val.get("possession_respect")),
        "conflicts": _as_str_list(val.get("conflicts")),
        "assumptions": _as_str_list(val.get("assumptions")),
    }

    inst = (
        data.get("customer_instruction")
        if isinstance(data.get("customer_instruction"), dict)
        else {}
    )
    do_not = _as_str_list(inst.get("do_not")) or base["customer_instruction"]["do_not"]
    base["customer_instruction"] = {
        "start_here": _as_str(inst.get("start_here")),
        "do_this_week": _as_str_list(inst.get("do_this_week")),
        "do_not": do_not,
        "weekly_reset": _as_str(inst.get("weekly_reset")),
    }
    return base


def _humanize_codes(values: List[str], mapping: Dict[str, str]) -> List[str]:
    out = []
    for v in values or []:
        key = _as_str(v)
        if not key:
            continue
        out.append(mapping.get(key, key.replace("_", " ")))
    return out


def _space_key(lead: Dict[str, Any]) -> str:
    return _as_str(lead.get("space_type") or "space").lower().replace(" ", "_")


def _budget_label(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    note = _as_str(deliverable.get("budget_note"))
    if note:
        return note
    raw = _as_str(lead.get("budget"))
    return BUDGET_LABELS.get(raw, raw.replace("_", " ") if raw else "")


def _shopping_total(deliverable: Dict[str, Any]) -> float:
    total = 0.0
    for it in deliverable.get("shopping_list") or []:
        if not isinstance(it, dict):
            continue
        try:
            total += float(it.get("qty", 1) or 1) * float(it.get("price", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _band_status(lead: Dict[str, Any], total: float) -> Tuple[str, str]:
    raw = _as_str(lead.get("budget"))
    ranges = {
        "under_100": (0, 100),
        "100_300": (100, 300),
        "300_700": (300, 700),
        "700_plus": (700, 10_000),
    }
    if raw not in ranges or total <= 0:
        return "watch", "Typical retail range — confirm prices before you buy."
    lo, hi = ranges[raw]
    if lo <= total <= hi:
        return "pass", f"Kit totals ${total:,.0f}, inside the {BUDGET_LABELS[raw]} band."
    if total < lo:
        return "pass", f"Kit totals ${total:,.0f}, under the {BUDGET_LABELS[raw]} band."
    return "watch", f"Kit totals ${total:,.0f}, above the stated {BUDGET_LABELS[raw]} band."


def derive_layers(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> Dict[str, Any]:
    """Build honest layers from questionnaire + plan fields (no invented dimensions)."""
    layers = empty_layers()
    space = _space_key(lead)
    space_label = space.replace("_", " ") or "space"
    must_stay = _as_str(lead.get("must_stay"))
    possessions = [p.strip() for p in must_stay.split(",") if p.strip()] if must_stay else []
    possessions += _humanize_codes(lead.get("storage_needs") or [], STORAGE)
    # de-dupe, keep order
    seen = set()
    unique_possessions = []
    for p in possessions:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            unique_possessions.append(p)

    challenge = _as_str(lead.get("biggest_challenge") or lead.get("goals"))
    bothers = _humanize_codes(lead.get("bothers_about") or [], BOTHERS)
    if lead.get("bothers_other"):
        bothers.append(_as_str(lead["bothers_other"]))
    feelings = _humanize_codes(lead.get("desired_feeling") or [], FEELING)
    if lead.get("feeling_other"):
        feelings.append(_as_str(lead["feeling_other"]))

    layers["observation"] = {
        "space_seen": _as_str(deliverable.get("intro"))
        or f"A {space_label} organized from the customer's photo and answers — same walls and openings.",
        "current_state": bothers[:5]
        or [_as_str(deliverable.get("summary")) or f"{space_label.capitalize()} needs a calmer system."],
        "possessions": unique_possessions[:6] or ["Items the customer already owns — keep and house them."],
        "evidence": [
            x
            for x in [
                f"Space type from intake: {space_label}.",
                challenge and f"Customer stated: {challenge}",
                must_stay and f"Must keep: {must_stay}",
                "Photo is the source of truth for the shell. No invented footage.",
            ]
            if x
        ],
    }

    routine = _as_str(lead.get("daily_improvement")) or (
        f"Daily in-and-out of the {space_label}: find what you need, put it back, leave a path."
    )
    layers["human_need"] = {
        "routine": routine,
        "desired_feeling": ", ".join(feelings) if feelings else "Calm and functional",
        "jobs_to_be_done": _as_str_list(deliverable.get("needs")) or [
            f"Give every {space_label} item a labeled home",
            "Clear the floor / path",
        ],
        "pain": challenge or (bothers[0] if bothers else "Clutter creates daily friction and decision fatigue."),
    }

    layers["spatial_constraint"] = {
        "preserve_shell": True,
        "windows_dims_fidelity": "~95%",
        "known_from_photo": SPACE_SHELL_HINTS.get(space, [
            "Keep the walls, windows, and openings the photo already shows.",
            "Change bins, furniture, and layout only.",
        ]),
        "unknowns": [
            "Exact footage, window counts, and opening sizes were not measured — we do not invent them.",
        ],
        "no_invented_floor_plan": True,
        "paint_optional": True,
    }

    rec_zones = []
    for z in deliverable.get("zones") or []:
        if isinstance(z, dict) and (_as_str(z.get("title")) or _as_str(z.get("desc"))):
            rec_zones.append({
                "title": _as_str(z.get("title")),
                "why": _as_str(z.get("desc")),
            })
    layers["recommendation"] = {
        "system": _as_str(deliverable.get("summary") or deliverable.get("intro"))
        or f"Zone the existing {space_label}, contain what you own, leave the shell alone.",
        "zones": rec_zones[:6],
        "why_it_should_work": _as_str(
            (deliverable.get("benefits") or [None])[0]
        )
        or "Labeled homes plus a clear path reduce visual noise and the daily hunt.",
    }

    total = _shopping_total(deliverable)
    band_label = _budget_label(lead, deliverable)
    band_status, band_note = _band_status(lead, total)
    layers["validation"] = {
        "fit": {
            "status": "pass" if rec_zones else "watch",
            "note": "Zones hang on the existing shell — shelves, bins, and hooks, no new walls."
            if rec_zones
            else "Zones will follow the real layout in the photo.",
        },
        "flow": {
            "status": "pass" if rec_zones else "watch",
            "note": "Circulation stays on the path the photo already shows; floor / stall stays a destination.",
        },
        "budget_band": {
            "status": band_status,
            "note": band_note,
            "band": band_label or (f"${total:,.0f} typical kit" if total else "Typical retail — confirm before you buy"),
        },
        "possession_respect": {
            "status": "pass" if must_stay else "watch",
            "note": f"Plan keeps: {must_stay}." if must_stay else "Keep what the customer already owns; house it, do not replace it.",
        },
        "conflicts": [],
        "assumptions": [
            "Existing walls can take light shelving / hooks.",
            "Customer will confirm prices before buying.",
        ],
    }

    actions = _as_str_list(deliverable.get("action_plan"))
    layers["customer_instruction"] = {
        "start_here": actions[0] if actions else "Clear what does not belong on the floor / path.",
        "do_this_week": actions[:5] or [
            "Declutter what does not belong",
            "Install the storage system on existing walls",
            "Sort into labeled homes",
        ],
        "do_not": [
            "Do not add walls, windows, or doors.",
            "Do not invent room dimensions.",
            "Paint is optional — skip it unless it helps the goal.",
        ],
        "weekly_reset": "Return items to their labeled bin, clear the landing zone / floor path, wipe one surface.",
    }
    return layers


def merge_layers(primary: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer filled fields from primary; backfill from fallback (usually derived)."""
    a = coerce_layers(primary)
    b = coerce_layers(fallback)

    def pick_str(x: str, y: str) -> str:
        return x or y

    def pick_list(x: List[str], y: List[str]) -> List[str]:
        return x or y

    a["observation"]["space_seen"] = pick_str(a["observation"]["space_seen"], b["observation"]["space_seen"])
    a["observation"]["current_state"] = pick_list(a["observation"]["current_state"], b["observation"]["current_state"])
    a["observation"]["possessions"] = pick_list(a["observation"]["possessions"], b["observation"]["possessions"])
    a["observation"]["evidence"] = pick_list(a["observation"]["evidence"], b["observation"]["evidence"])

    a["human_need"]["routine"] = pick_str(a["human_need"]["routine"], b["human_need"]["routine"])
    a["human_need"]["desired_feeling"] = pick_str(
        a["human_need"]["desired_feeling"], b["human_need"]["desired_feeling"]
    )
    a["human_need"]["jobs_to_be_done"] = pick_list(
        a["human_need"]["jobs_to_be_done"], b["human_need"]["jobs_to_be_done"]
    )
    a["human_need"]["pain"] = pick_str(a["human_need"]["pain"], b["human_need"]["pain"])

    a["spatial_constraint"]["known_from_photo"] = pick_list(
        a["spatial_constraint"]["known_from_photo"],
        b["spatial_constraint"]["known_from_photo"],
    )
    a["spatial_constraint"]["unknowns"] = pick_list(
        a["spatial_constraint"]["unknowns"], b["spatial_constraint"]["unknowns"]
    )

    a["recommendation"]["system"] = pick_str(a["recommendation"]["system"], b["recommendation"]["system"])
    a["recommendation"]["zones"] = a["recommendation"]["zones"] or b["recommendation"]["zones"]
    a["recommendation"]["why_it_should_work"] = pick_str(
        a["recommendation"]["why_it_should_work"],
        b["recommendation"]["why_it_should_work"],
    )

    for key in CHECK_KEYS:
        if not a["validation"][key].get("note"):
            a["validation"][key] = b["validation"][key]
        elif key == "budget_band" and not a["validation"][key].get("band"):
            a["validation"][key]["band"] = b["validation"][key].get("band", "")
    a["validation"]["conflicts"] = pick_list(a["validation"]["conflicts"], b["validation"]["conflicts"])
    a["validation"]["assumptions"] = pick_list(
        a["validation"]["assumptions"], b["validation"]["assumptions"]
    )

    a["customer_instruction"]["start_here"] = pick_str(
        a["customer_instruction"]["start_here"],
        b["customer_instruction"]["start_here"],
    )
    a["customer_instruction"]["do_this_week"] = pick_list(
        a["customer_instruction"]["do_this_week"],
        b["customer_instruction"]["do_this_week"],
    )
    a["customer_instruction"]["weekly_reset"] = pick_str(
        a["customer_instruction"]["weekly_reset"],
        b["customer_instruction"]["weekly_reset"],
    )
    return a


def resolve_layers(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> Dict[str, Any]:
    """Layers stored on the deliverable, backfilled from lead + plan so PDFs never go blank."""
    derived = derive_layers(lead or {}, deliverable or {})
    stored = (deliverable or {}).get("blueprint_layers")
    if not stored:
        return derived
    return merge_layers(stored, derived)


def layers_complete(layers: Dict[str, Any]) -> bool:
    """True when a reviewer can answer Ryan's five questions without guessing."""
    try:
        answers = ryan_answers(layers)
    except Exception:
        return False
    return all(_as_str(v) for v in answers.values())


def ryan_answers(layers: Dict[str, Any]) -> Dict[str, str]:
    """Extract the five bake-off answers from structured layers."""
    data = coerce_layers(layers)
    possessions = data["observation"]["possessions"]
    poss_note = data["validation"]["possession_respect"].get("note") or ""
    fit_note = data["validation"]["fit"].get("note") or ""
    known = data["spatial_constraint"]["known_from_photo"]
    budget = data["validation"]["budget_band"]
    budget_text = " ".join(
        x for x in [budget.get("band"), budget.get("note")] if x
    )
    why = data["recommendation"]["why_it_should_work"]
    return {
        "routine": data["human_need"]["routine"],
        "possessions": "; ".join(possessions) + (f" — {poss_note}" if poss_note else ""),
        "physical_fit": fit_note
        + (" " + " ".join(known[:2]) if known else "")
        + f" Shell preserved; windows/dims {data['spatial_constraint']['windows_dims_fidelity']}.",
        "budget": budget_text,
        "why_it_should_work": why,
    }


def layer_card_copy(layers: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(number, title, body) for the six customer-visible PDF cards."""
    data = coerce_layers(layers)
    obs = data["observation"]
    need = data["human_need"]
    spat = data["spatial_constraint"]
    rec = data["recommendation"]
    val = data["validation"]
    inst = data["customer_instruction"]

    obs_body = obs["space_seen"]
    if obs["possessions"]:
        obs_body += " Possessions: " + ", ".join(obs["possessions"][:4]) + "."

    spat_bits = [
        f"Windows/dims stay {spat['windows_dims_fidelity']} true to the photo.",
        "Keep the shell — no invented floor plan.",
    ]
    if spat["known_from_photo"]:
        spat_bits.append(spat["known_from_photo"][0])

    checks = []
    for key, label in (
        ("fit", "Fit"),
        ("flow", "Flow"),
        ("budget_band", "Budget"),
        ("possession_respect", "Possessions"),
    ):
        item = val[key]
        checks.append(f"{label}: {item.get('status', 'watch')}")
    val_body = " · ".join(checks)
    if val["fit"].get("note"):
        val_body += ". " + val["fit"]["note"]
    if val.get("conflicts"):
        val_body += " Conflicts: " + "; ".join(val["conflicts"][:2]) + "."
    if val.get("assumptions"):
        val_body += " Assumptions: " + "; ".join(val["assumptions"][:2]) + "."

    inst_body = inst["start_here"]
    if inst["do_this_week"]:
        inst_body += " This week: " + "; ".join(inst["do_this_week"][:3]) + "."

    return [
        ("01", "Observation", obs_body or "What the photo and answers actually show."),
        (
            "02",
            "Human need",
            (f"Routine: {need['routine']}" if need["routine"] else "")
            + (f" Pain: {need['pain']}" if need["pain"] else "")
            or "A calmer daily system for this space.",
        ),
        ("03", "Spatial constraint", " ".join(spat_bits)),
        (
            "04",
            "Recommendation",
            (rec["system"] + (" " + rec["why_it_should_work"] if rec["why_it_should_work"] else "")).strip()
            or "Zone the room you already have.",
        ),
        ("05", "Validation", val_body),
        ("06", "Customer instruction", inst_body or "Start with the floor path, then label homes."),
    ]


def load_json_schema() -> Dict[str, Any]:
    if SCHEMA_PATH.is_file():
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {"title": "blueprint_layers", "type": "object"}


# Compact schema snippet embedded in the Claude system prompt.
DRAFTER_SCHEMA_SNIPPET = """
  "blueprint_layers": {
    "observation": {
      "space_seen": "what the photo/answers show — no invented dimensions",
      "current_state": ["short facts about the current mess / unused capacity"],
      "possessions": ["named items they own or must keep"],
      "evidence": ["questionnaire or photo facts only"]
    },
    "human_need": {
      "routine": "how they use this space daily/weekly — answer 'what is the routine?'",
      "desired_feeling": "calm / functional / …",
      "jobs_to_be_done": ["park the car", "find the bag in 30 seconds"],
      "pain": "the human problem in one sentence"
    },
    "spatial_constraint": {
      "preserve_shell": true,
      "windows_dims_fidelity": "~95%",
      "known_from_photo": ["qualitative: existing stall, door path, wall they already have"],
      "unknowns": ["exact footage not measured — do not invent"],
      "no_invented_floor_plan": true,
      "paint_optional": true
    },
    "recommendation": {
      "system": "one-sentence org system",
      "zones": [{"title": "Parking Zone", "why": "keep the stall a destination"}],
      "why_it_should_work": "causal: why this system fits the routine + shell"
    },
    "validation": {
      "fit": {"status": "pass|watch|fail", "note": "does the kit fit the existing shell?"},
      "flow": {"status": "pass|watch|fail", "note": "is the daily path clear?"},
      "budget_band": {"status": "pass|watch|fail", "note": "kit vs stated band", "band": "$100 – $300"},
      "possession_respect": {"status": "pass|watch|fail", "note": "must-keep items still have a home"},
      "conflicts": ["real tension, or empty"],
      "assumptions": ["what we assumed because it was not measured"]
    },
    "customer_instruction": {
      "start_here": "first move this week",
      "do_this_week": ["concrete steps, no construction, no required paint"],
      "do_not": ["do not invent dimensions", "do not add walls"],
      "weekly_reset": "10-minute reset"
    }
  }
"""
