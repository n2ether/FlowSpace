"""FlowSpace Design Plan standards — the defaults every new project renders with.

Camila approved these on Nicholas's Nursery (Design Plan v5). The board
(``image_board``), the Room Flow sheet (``room_flow``), the Companion Guide
(``pdf_generator``), the phone page (``blueprint_presentation``), the emails
(``email_service``), and the drafter prompt (``ai_drafter``) read them from
here, so a new lead gets the same structure without per-lead code.

1. Brand: FlowSpace lockup, Montserrat hierarchy, the approved palette, the
   tagline, simple line icons, a calm editorial layout.
2. Design Plan board, top to bottom: a small "FlowSpace Design Plan" label,
   the project name as the main title, an inviting hero, Project Story, What
   Changed & Why, The Zones, a materials + shopping snapshot, a small
   warm-neutral palette, a three-step roadmap, and a short Why It Works close.
3. The Room Flow map is its own attachment. The board never draws it.
4. Type stays readable on a phone; board copy is short.
5. Safety, climate, maintenance, styling rules, and the full designer
   assessment live in the modular Companion Guide, not on the board.
6. Every surface reads DRAFT / REVIEW until the package is released.
7. Copy is evergreen (see ``evergreen_copy``).
8. A package is three separate pieces (Design Plan, Room Flow, Companion
   Guide) with one version number; their facts come from ``package_facts``.

Nicholas's Nursery keeps its approved v5 copy (the ``NURSERY_*`` defaults).
Every other room uses the general standard below: a functional / optional
decorative shopping split, the three-step Measure → Set up → Style roadmap,
the Intake → Reset process, and the companion sections that go with them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ──────────────────────────── Brand ─────────────────────────────

BRAND_NAME = "FlowSpace"
TAGLINE = "Clear space. Create flow. Live better."

BRAND_GREEN = "#2F5D50"
BRAND_SAGE = "#A8C3B0"
BRAND_OFF = "#F6F7F4"
BRAND_GREIGE = "#E6E1DB"
BRAND_CHAR = "#2B2B2B"
BRAND_PALETTE = {
    "green": BRAND_GREEN,
    "sage": BRAND_SAGE,
    "off": BRAND_OFF,
    "greige": BRAND_GREIGE,
    "char": BRAND_CHAR,
}
# Tints the approved board derives from the palette.
BRAND_TINTS = {
    "sage_light": "#E4ECE6",
    "sage_line": "#D3E0D6",
    "greige_light": "#F1EEE9",
    "line": "#E2DED7",
    "muted": "#5E625F",
    "body": "#454845",
    "white": "#FFFFFF",
}


def hex_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


FONTS_DIR = Path(__file__).resolve().parent / "fonts"
MONTSERRAT = {
    "light": "Montserrat-Light.ttf",
    "regular": "Montserrat-Regular.ttf",
    "medium": "Montserrat-Medium.ttf",
    "semibold": "Montserrat-SemiBold.ttf",
    "bold": "Montserrat-Bold.ttf",
}


def montserrat_path(weight: str) -> str:
    return str(FONTS_DIR / MONTSERRAT.get(weight, MONTSERRAT["regular"]))


# CSS stack for HTML surfaces (email, app). Mail clients without Montserrat fall back cleanly.
FONT_STACK = "Montserrat,'Helvetica Neue',Helvetica,Arial,sans-serif"

# ──────────────────────────── Review controls ─────────────────────────────

REVIEW_STATUS = "DRAFT. Review version. Not yet approved. Customer release held."
REVIEW_PILL = "DRAFT / REVIEW"
REVIEW_NOTE = ("Internal review only", "Not final · not released")
RELEASED_STATUS = "final"

# ──────────────────────────── Package and versions ─────────────────────────────

BRAND_ATTRIBUTION = BRAND_NAME
DESIGN_SYSTEM_NAME = "FlowSpace Design System"

# The three separate files of every package, in reading order.
PACKAGE_PIECES: Tuple[Tuple[str, str], ...] = (
    ("design_plan", "Design Plan"),
    ("room_flow", "Room Flow"),
    ("companion_guide", "Companion Guide"),
)

FIRST_PACKAGE_VERSION = 1


def package_version(deliverable: Optional[Dict[str, Any]]) -> int:
    """Version of the stored package. A package from before versioning is version 1."""
    try:
        version = int((deliverable or {}).get("package_version") or FIRST_PACKAGE_VERSION)
    except (TypeError, ValueError):
        version = FIRST_PACKAGE_VERSION
    return max(FIRST_PACKAGE_VERSION, version)


def version_label(version: int) -> str:
    """Internal review chrome. The same Portuguese sentence for every version.

    Customer copy stays English. File names use :func:`version_tag` instead.
    """
    return f"Versão {int(version)} para sua análise"


def version_tag(version: int) -> str:
    """ASCII tag for file names."""
    return f"V{int(version)}"


def is_released(deliverable: Optional[Dict[str, Any]]) -> bool:
    """True only once a package is final or a reviewer set ``design_plan_approved``.

    Everything else — new, review, incomplete — reads DRAFT / REVIEW. Nothing in
    the pipeline sets either flag on its own.
    """
    doc = deliverable or {}
    if doc.get("design_plan_approved") is True:
        return True
    return str(doc.get("package_status") or "").strip().lower() == RELEASED_STATUS


# ──────────────────────────── Design Plan board ─────────────────────────────

DESIGN_PLAN_NAME = "Design Plan"
DESIGN_PLAN_LABEL = "FlowSpace Design Plan"
DESIGN_PLAN_FOOTER = "FlowSpace Design Plan"
DESIGN_PLAN_FOOTER_REVIEW = "FlowSpace Design Plan · DRAFT / REVIEW · Internal"

# Numbered sections in board order.
DESIGN_PLAN_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("01", "Project Story"),
    ("02", "What Changed & Why"),
    ("03", "The Zones"),
    ("04", "Materials + Shopping Snapshot"),
    ("05", "Palette"),
    ("06", "Three-Step Roadmap"),
    ("07", "Why It Works"),
)
SECTION_TITLES = {number: title for number, title in DESIGN_PLAN_SECTIONS}

# What the board deliberately leaves to other files.
BOARD_EXCLUDES = (
    "room_flow_map",
    "safety",
    "climate",
    "maintenance",
    "styling_rules",
    "designer_assessment",
)

ZONES_NOTE = "One clear job for each part of the room."
ROADMAP_NOTE = "A simple sequence to follow at your own pace."
STORY_HEADLINE = "A calmer room for everyday routines."
DEFAULT_STORY = "We kept the room you already have and gave every part a clear job."
WHY_IT_WORKS_HEADLINE = "Each part of the room gets one clear job."
WHY_IT_WORKS_BODY = (
    "With an open path and a simple home for everyday items, daily routines require fewer "
    "decisions, resets happen faster, and the room becomes calmer and easier to use."
)
DEFAULT_SUBTITLE = "A calmer flow for the room you already have"

SHOPPING_DISCLAIMER = "Representative examples for reference; prices and availability may vary."
SNAPSHOT_TOTAL_LABEL = "Illustrative reference total"
SNAPSHOT_MAX_ITEMS = 5
KEPT_LABEL = "Kept as-is"

# Word budgets for board copy. The full sentence stays in the Companion Guide.
BOARD_WORDS = {
    "story": 26,
    "change": 16,
    "zone_job": 10,
    "roadmap": 14,
}

# ──────────────────────────── Zones ─────────────────────────────

# The four nursery zones. ``object`` is what anchors the zone in the room.
NURSERY_ZONES: Tuple[Dict[str, str], ...] = (
    {"id": "sleep", "title": "Sleep", "object": "Crib", "job": "The quiet anchor, kept simple.", "map_label": "SLEEP ZONE"},
    {"id": "change", "title": "Change", "object": "Dresser", "job": "Everyday care within easy reach.", "map_label": "CHANGE ZONE"},
    {"id": "comfort", "title": "Comfort", "object": "Rocker", "job": "For feeding, connection, and rest.", "map_label": "COMFORT ZONE"},
    {"id": "play", "title": "Play + Storage", "object": "Rug + basket", "job": "Open floor and one easy-reset basket.", "map_label": "PLAY + STORAGE"},
)
NURSERY_SUBTITLE = "A calmer flow for sleep, change, comfort & play"

# ──────────────────────────── Nursery defaults ─────────────────────────────

# (title, full body, short body). The full body is used when the plan supports it.
NURSERY_CHANGES: Dict[str, Tuple[str, str, str]] = {
    "keep": (
        "Keep this room",
        "Keep the room and the dresser you already have, so putting things away stays simple.",
        "Keep the room and the dresser you already have, so putting things away stays simple.",
    ),
    "climate": (
        "Reduce drafts",
        "Layer thermal curtains, seal the glass with film, and close the gap under the door.",
        "Layer a thermal curtain and close the gap under the door.",
    ),
    "path": (
        "Clear the path",
        "Keep a clear path from the door to the crib and the dresser.",
        "Keep a clear path from the door to the crib and the dresser.",
    ),
    "care": (
        "Everyday care at the dresser",
        "Fewer steps at changing time.",
        "Fewer steps at changing time.",
    ),
}
NURSERY_CHANGE_ORDER = ("keep", "climate", "path", "care")

NURSERY_ROADMAP: Tuple[Tuple[str, str], ...] = (
    ("Clear the path", "Open the center floor and settle each piece into its zone."),
    ("Soften the drafts", "Layer curtains, seal the glass, and close the door gap."),
    ("Make daily care easy", "Mount the wall caddy and give diapering essentials a home."),
)
NURSERY_ROADMAP_NO_CLIMATE = ("Soften the room", "Layer warm textiles and keep the window clear.")

DEFAULT_ROADMAP: Tuple[str, ...] = (
    "Clear the floor path and put everyday items back where they live.",
    "Finish the storage that uses furniture you already own.",
    "Do a short reset now and then so the room stays easy.",
)

# ──────────────────────────── General standard (every room but the nursery) ─────────────────────────────

# (title, board body, companion detail). The same three steps print on all three pieces.
GENERAL_ROADMAP: Tuple[Tuple[str, str, str], ...] = (
    (
        "Measure and verify",
        "Measure walls, tables, and niches, then check each item against them.",
        "Measure the walls, tables, and niches where new pieces will go. Check every size, finish, "
        "and price against those measurements before you buy.",
    ),
    (
        "Set up functional storage",
        "Place the functional items first so everyday things have a home.",
        "Set up the functional items first. Give everyday things one home each and keep the path clear.",
    ),
    (
        "Add styling",
        "Add the optional decorative pieces once storage is working.",
        "Add the optional decorative pieces last, once the functional storage is working.",
    ),
)

# How every FlowSpace project runs, in order.
PROCESS_STEPS: Tuple[Tuple[str, str], ...] = (
    ("Intake", "You shared photos of the room and how you use it."),
    ("Clarify", "We confirmed what stays and what each area needs."),
    ("Design", "The Design Plan, the Room Flow, and this guide."),
    ("Verify", "Measure and check each item before you buy."),
    ("Set up", "Functional storage first, styling after."),
    ("Reset", "A self-paced reset keeps the room working."),
)
PROCESS_LINE = " · ".join(name for name, _ in PROCESS_STEPS)

WHAT_STAYS_TEXT = "Keep the original wall color and all current furniture."
WHAT_STAYS_CHIPS = ("Original wall color", "All current furniture")

LIVING_ROOM_SUBTITLE = "A calmer flow through the living, dining, and entry areas."

# Project names by room. The nursery names the child (``customer_project_title``).
PROJECT_TITLES = {"living_room": "Living Room"}

MEASURE_BEFORE_BUYING = "measure before buying"

SHOPPING_FUNCTIONAL = "Functional"
SHOPPING_DECORATIVE = "Optional decorative"
TAX_SHIPPING_NOTE = "before tax and shipping"
LINK_TESTED = "Tested product link"
LINK_REFERENCE = "Reference search"
LINK_KIND_NOTE = (
    "Tested product links open the exact product page we checked. "
    "Reference searches open a labeled retailer search to compare options."
)

SELF_PACED_RESET_TITLE = "Self-paced reset"
SELF_PACED_RESET = (
    "Whenever the room starts to drift, go at your own pace: return each item to its home, "
    "clear the path, and empty the catch-all. The reset keeps the system. It is not a remodel."
)
SELF_PACED_RESET_NO_CATCH_ALL = (
    "Whenever the room starts to drift, go at your own pace: return each item to its home "
    "and clear the path. The reset keeps the system. It is not a remodel."
)

# ──────────────────────────── Palette ─────────────────────────────

WARM_NEUTRAL_PALETTE: Tuple[Tuple[str, str], ...] = (
    ("Soft beige", "#E6E1DB"),
    ("Cream", "#F4EFE6"),
    ("Clay", "#C08A6C"),
    ("Muted sage", "#A8C3B0"),
    ("Warm wood", "#A97B52"),
)
# Customer color preferences (textiles and accessories, never walls).
COLOR_PREF_SWATCHES = {
    "warm_neutrals": ("Soft beige", "#E6E1DB"),
    "white": ("Cream", "#F4EFE6"),
    "sage": ("Muted sage", "#A8C3B0"),
    "earth": ("Clay", "#C08A6C"),
    "wood": ("Warm wood", "#A97B52"),
    "blue": ("Soft blue", "#8AA4B5"),
    "dark": ("Charcoal", "#3E4744"),
    "black": ("Soft charcoal", "#3A3A3A"),
}
PALETTE_SIZE = 5
PALETTE_BLURB = "Warm neutrals and natural texture beside the original wall color."
PALETTE_BLURB_THEMED = "Warm neutrals and natural texture beside the original wall color, with gentle space-themed accents."

# ──────────────────────────── Companion Guide ─────────────────────────────

# Modules in print order. A deliverable may list ``companion_modules`` to pick a subset.
COMPANION_GUIDE_MODULES: Tuple[str, ...] = (
    "safety",
    "climate",
    "maintenance",
    "styling",
    "assessment",
    "shopping",
    "views",
)
# The general guide: process and first step up front, then what to check and what comes first,
# the essentials, styling and assessment, the reset, the shopping list, and one page per view.
GENERAL_COMPANION_MODULES: Tuple[str, ...] = (
    "process",
    "first_step",
    "check",
    "priority",
    "safety",
    "climate",
    "styling",
    "assessment",
    "reset",
    "shopping",
    "views",
)
COMPANION_MODULE_TITLES = {
    "safety": "SAFETY ESSENTIALS",
    "climate": "CLIMATE COMFORT",
    "maintenance": "MAINTENANCE",
    "styling": "STYLING RULES",
    "assessment": "DESIGNER ASSESSMENT",
    "shopping": "SHOPPING LIST",
    "views": "BEFORE AND AFTER",
    "process": "HOW FLOWSPACE WORKS",
    "first_step": "FIRST STEP",
    "check": "CHECK BEFORE BUYING",
    "priority": "FUNCTIONAL VS DECORATIVE PRIORITY",
    "reset": "SELF-PACED RESET",
}
COMPANION_NAME = "Companion Guide"


def companion_modules(deliverable: Optional[Dict[str, Any]], *, general: bool = False) -> Tuple[str, ...]:
    """Modules this package prints. Unknown names are ignored; the order is always the standard one.

    ``general`` picks the general guide; the nursery keeps its approved module list.
    """
    standard = GENERAL_COMPANION_MODULES if general else COMPANION_GUIDE_MODULES
    chosen = (deliverable or {}).get("companion_modules")
    if not isinstance(chosen, (list, tuple)) or not chosen:
        return standard
    wanted = {str(name).strip().lower() for name in chosen}
    return tuple(name for name in standard if name in wanted)


# ──────────────────────────── Email ─────────────────────────────

EMAIL_DESIGN_PLAN_COPY = "Your Design Plan is shown below and attached as a full-size image."
EMAIL_ROOM_FLOW_COPY = "The Room Flow map is its own page, shown below and attached as a separate full-size image."
EMAIL_COMPANION_COPY = (
    "Next, open the attached Companion Guide on your phone for safety, climate comfort, maintenance, "
    "styling rules, the designer assessment, the shopping list, and each before and after."
)

# ──────────────────────────── Drafter rails ─────────────────────────────

DRAFTER_DESIGN_PLAN_RULES = """
FlowSpace Design Plan standards (every plan):
- The customer reads a light editorial Design Plan, not a technical report. Write short, calm, concrete sentences (about 20 words or fewer).
- intro opens with one or two sentences that tell the project story: what stays, and what each part of the room is for.
- strategy lists up to four changes, each one whole sentence that starts with a verb and says why it helps.
- action_plan is exactly three steps in order. No "Week 1", "Day 2", dates, or durations.
- zones: up to four, each with one clear job. For a nursery use Sleep, Change, Comfort, and Play + Storage.
- shopping_list names are generic product descriptions (no brand or retailer names). Prices are typical mid-range retail examples.
- Give each shopping_list item "priority": "functional" (storage, organizing, safety, the entry catch-all) or "decorative" (optional styling: art, frames, pillows, throws, plants).
- Do not state an exact size for a frame, basket, print, tray, pillow, or any other product unless the customer gave wall, table, or niche measurements; write "measure before buying" instead.
- A playpen is an item inside a zone, never a zone of its own.
- Outside a nursery, action_plan is: measure and verify, set up functional storage, then add styling.
- Safety, climate, maintenance, and styling detail belong in the companion guide; keep them out of intro and summary.
"""
