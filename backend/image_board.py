"""Primary visual FlowSpace Blueprint.

One portrait PNG (~2:3) per Blueprint, assembled here from real text layers
and the FlowSpace mark. Photos are pasted in as themselves. The image model
never draws this board or its type. Safety, climate, the weekly reset,
and the full steps live in the companion guide. A short shopping block
is drawn here only when the plan already has line items — never an
isolated total, and never invented products or prices.

Photos are only the customer's before image and renders the pipeline actually
produced. Each room photo is placed with contain: its own aspect ratio and
field of view, never cover-cropped into a wide fixed slot. When several room
photos were required, the hero is the first complete after and each remaining
after is a full frame. A missing after stays empty — it is not a crop of
another angle. Detail crops are extras for a single organized photo only.
The room plan is a top-down sketch of this room — window, door, and the
furniture already in it — not a stack of bars and not a measured drawing.
Customer pixels never carry SOURCE_/AFTER_ codes or a lead id. Those stay
on the review contact sheet.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from blueprint_consistency import prepare_deliverable, safety_guidance
from pdf_generator import customer_project_title, plan_title, space_label
from photo_contain import contain_pixels, frame_size
from pdf_images import (
    HERO_PLACEHOLDER_LABEL,
    HERO_PLACEHOLDER_SUB,
    coerce_image_bytes,
    normalize_pdf_images,
)

# Portrait shareable board. 2:3, text and mark drawn in code.
PORTRAIT_W, PORTRAIT_H = 1200, 1800
W, H = PORTRAIT_W, PORTRAIT_H
BRAND_LINE = "BOUTIQUE  ·  FUNCTIONAL  ·  INTENTIONAL  ·  AFFORDABLE"

PAPER = (243, 238, 230)
INK = (42, 38, 34)
MUTED = (110, 101, 92)
RULE = (226, 217, 204)
CARD = (255, 252, 248)
GREEN = (31, 61, 44)
GREEN_SOFT = (207, 226, 215)
CLAY = (193, 123, 74)
WHITE = (255, 255, 255)

_FONT_PATHS = {
    "serif": (
        "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ),
    "serif-bold": (
        "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ),
    "serif-italic": (
        "/usr/share/fonts/truetype/noto/NotoSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    ),
    "sans": (
        "/usr/share/fonts/truetype/macos/Inter-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    "sans-medium": (
        "/usr/share/fonts/truetype/macos/Inter-Medium.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    "sans-bold": (
        "/usr/share/fonts/truetype/macos/Inter-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
}

_PALETTE = {
    "warm_neutrals": ("Warm neutral", "#E4D3BC"),
    "white": ("Soft white", "#F7F4EF"),
    "sage": ("Sage", "#9CAF9A"),
    "earth": ("Clay", "#C17B4A"),
    "blue": ("Soft blue", "#8AA4B5"),
    "dark": ("Charcoal", "#3E4744"),
    "wood": ("Natural oak", "#C4A574"),
    "black": ("Soft charcoal", "#3A3A3A"),
}

_fonts: Dict[Tuple[str, int], ImageFont.ImageFont] = {}


def _font(kind: str, size: int) -> ImageFont.ImageFont:
    key = (kind, size)
    if key in _fonts:
        return _fonts[key]
    for path in _FONT_PATHS.get(kind, ()):
        try:
            face = ImageFont.truetype(path, size=size)
            _fonts[key] = face
            return face
        except OSError:
            continue
    face = ImageFont.load_default()
    _fonts[key] = face
    return face


def _hex(value: str, fallback: str) -> str:
    v = (value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
        return v.upper()
    return fallback


def _rgb(value: str) -> Tuple[int, int, int]:
    value = _hex(value, "#C5C8C6")
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> List[str]:
    words = _clean(text).split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int) -> List[str]:
    """Wrap on word boundaries. If it still overflows, end on a whole sentence or phrase."""
    text = _clean(text)
    if not text:
        return []
    lines = _wrap(draw, text, font, width)
    if len(lines) <= max_lines:
        return lines
    words = text.split()
    best = words[0]
    for count in range(1, len(words) + 1):
        candidate = " ".join(words[:count])
        if len(_wrap(draw, candidate, font, width)) <= max_lines:
            best = candidate
        else:
            break
    if best != text:
        punct = max(best.rfind("."), best.rfind("!"), best.rfind("?"))
        if punct >= int(len(best) * 0.45):
            best = best[: punct + 1]
        elif not best.endswith((".", "!", "?")):
            best = best.rstrip(".,;:—- ") + "."
        lines = _wrap(draw, best, font, width)[:max_lines]
    return lines


def _open_image(data: Optional[bytes]) -> Optional[Image.Image]:
    raw = coerce_image_bytes(data)
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img) or img
        return img.convert("RGB")
    except Exception:
        return None


def _crop_frac(img: Image.Image, box: Tuple[float, float, float, float]) -> Image.Image:
    w, h = img.size
    l, t, r, b = box
    return img.crop((int(l * w), int(t * h), max(int(l * w) + 1, int(r * w)), max(int(t * h) + 1, int(b * h))))


def _paste_round(base: Image.Image, img: Image.Image, xy: Tuple[int, int], radius: int) -> None:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=radius, fill=255)
    base.paste(img, xy, mask)


def _rounded(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _first_name(lead: Dict[str, Any]) -> str:
    name = _clean(str(lead.get("name") or "Your")).split(" ")[0] or "Your"
    if name.lower() == "your":
        return "Your"
    return name


def _possessive(name: str) -> str:
    if name == "Your":
        return "Your"
    if name.endswith("s"):
        return name + "'"
    return name + "'s"


def _tagline(lead: Dict[str, Any]) -> str:
    feelings = [str(x).replace("_", " ") for x in (lead.get("desired_feeling") or []) if str(x).strip()]
    words = [w.strip().upper() for w in feelings[:3] if w.strip()]
    if not words:
        words = ["CALMER", "EASIER TO LIVE IN"]
    return "SAME ROOM. " + ". ".join(words) + "."


def _nursery_materials(space_theme: bool) -> List[Dict[str, str]]:
    if space_theme:
        return [
            {"name": "Natural oak", "hex": "#C4A574", "note": "Wood you have"},
            {"name": "Moon", "hex": "#E4E0D4", "note": "Space theme"},
            {"name": "Rocket", "hex": "#C44536", "note": "Space theme"},
            {"name": "Planet", "hex": "#3E7C78", "note": "Space theme"},
        ]
    return [
        {"name": "Cream", "hex": "#F4EFE6", "note": "Textile"},
        {"name": "Natural oak", "hex": "#C4A574", "note": "Wood you have"},
        {"name": "Clay", "hex": "#C17B4A", "note": "Accent"},
        {"name": "Muted teal", "hex": "#5E8A84", "note": "Textile"},
        {"name": "Soft charcoal", "hex": "#3E4744", "note": "Accent"},
    ]


def _palette(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    from space_rails import is_nursery_space, is_space_theme

    swatches = [{"name": "Existing walls", "hex": "#C5C8C6", "note": "Not repainted"}]
    if is_nursery_space(lead):
        swatches.extend(_nursery_materials(is_space_theme(lead, deliverable)))
        return swatches[:6]
    hex_color = str(deliverable.get("wall_color_hex") or "")
    name = str(deliverable.get("wall_color_name") or "")
    if hex_color and "keep existing" not in name.lower() and "no paint" not in name.lower():
        swatches.append({"name": name or "Optional paint", "hex": _hex(hex_color, "#CFD7D3"), "note": "Optional"})
    for pref in lead.get("color_prefs") or []:
        key = str(pref)
        if key in _PALETTE:
            label, color = _PALETTE[key]
            swatches.append({"name": label, "hex": color, "note": "Textiles"})
    if len(swatches) == 1:
        swatches.append({"name": "Cream", "hex": "#F3EEE6", "note": "Textile"})
        swatches.append({"name": "Natural oak", "hex": "#C4A574", "note": "Wood you have"})
    seen = set()
    out = []
    for swatch in swatches:
        if swatch["hex"] in seen:
            continue
        seen.add(swatch["hex"])
        out.append(swatch)
        if len(out) == 6:
            break
    return out


def _subtitle(deliverable: Dict[str, Any], draw: ImageDraw.ImageDraw) -> str:
    summary = _clean(str(deliverable.get("summary") or deliverable.get("intro") or ""))
    sentence = re.split(r"(?<=[.!?])\s+", summary)[0] if summary else ""
    if not sentence:
        return "A calmer refresh of the room you already have."
    font = _font("serif-italic", 22)
    lines = _fit(draw, sentence, font, 1100, 1)
    return lines[0] if lines else "A calmer refresh of the room you already have."


def _moves(deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    strategy = [_clean(str(x)) for x in (deliverable.get("strategy") or []) if _clean(str(x))]
    moves = [{"title": _move_title(text, i), "body": text} for i, text in enumerate(strategy[:6])]
    return moves


def _move_title(text: str, index: int) -> str:
    """Short label taken from the sentence itself, so the title matches the body."""
    words = [word.strip(".,;:") for word in text.split() if word.strip(".,;:")]
    picked = words[:3]
    while picked and picked[-1].lower() in {"with", "and", "or", "to", "of", "for", "so"}:
        picked.pop()
    title = " ".join(picked).upper()
    return title or f"MOVE {index + 1}"


def _roadmap(deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    layers = deliverable.get("blueprint_layers") if isinstance(deliverable.get("blueprint_layers"), dict) else {}
    instruction = layers.get("customer_instruction") if isinstance(layers.get("customer_instruction"), dict) else {}
    steps = [_clean(str(x)) for x in (instruction.get("do_this_week") or deliverable.get("action_plan") or []) if _clean(str(x))]
    titles = ("START HERE", "SET THE ROOM", "KEEP IT")
    while len(steps) < 3:
        steps.append(
            (
                "Clear the floor path and put everyday items back where they live.",
                "Finish the storage that uses furniture you already own.",
                "Do the short weekly reset so the room stays easy.",
            )[len(steps)]
        )
    return [{"title": titles[i], "body": steps[i]} for i in range(3)]


def _products(deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = _clean(str(item.get("name") or ""))
        if not name:
            continue
        try:
            qty = float(item.get("qty", 1) or 1)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            qty, price = 1.0, 0.0
        sub = qty * price
        price_label = f"${sub:,.0f}" if sub and abs(sub - round(sub)) < 0.01 else (f"${sub:,.2f}" if sub else "Confirm price")
        rows.append({"name": name, "price": price_label})
    return rows


def _zone_labels(deliverable: Dict[str, Any]) -> List[str]:
    labels = []
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            title = _clean(str(zone.get("title") or ""))
        else:
            title = _clean(str(zone))
        if title:
            labels.append(title)
    return labels[:4]


_NURSERY_VIEW_NAMES = (
    "Window and crib",
    "Crib wall",
    "Rocker",
    "Dresser and door",
)

# Wall-anchored blocks. None spans the room, so the plan cannot become bars.
_NURSERY_PLACES = (
    {"id": "sleep", "label": "SLEEP", "role": "SLEEP", "number": "1", "zone": "Sleep", "box": (0.34, 0.16, 0.86, 0.42)},
    {"id": "change", "label": "CHANGE", "role": "CHANGE", "number": "2", "zone": "Change", "box": (0.68, 0.48, 0.94, 0.84)},
    {"id": "comfort", "label": "COMFORT", "role": "COMFORT", "number": "3", "zone": "Comfort", "box": (0.05, 0.60, 0.32, 0.93)},
    {"id": "play", "label": "PLAY", "role": "STORAGE", "number": "4", "zone": "Play/Storage", "box": (0.36, 0.70, 0.62, 0.93)},
)
_NURSERY_LEGEND = (
    {"number": "1", "name": "Sleep"},
    {"number": "2", "name": "Change"},
    {"number": "3", "name": "Comfort"},
    {"number": "4", "name": "Play/Storage"},
)
# Room-relative. The first point sits on the door wall so the stroke meets the opening.
_CLEAR_PATH = ((0.0, 0.32), (0.18, 0.50), (0.40, 0.48))
_GENERIC_PLACE_BOXES = (
    (0.42, 0.08, 0.92, 0.36),
    (0.06, 0.44, 0.40, 0.78),
    (0.50, 0.48, 0.92, 0.84),
)


def customer_view_caption(index: int, lead: Optional[Dict[str, Any]], *, missing: bool = False) -> str:
    """Short customer label for one room photo. Never a SOURCE_/AFTER_ code."""
    from space_rails import is_nursery_space

    if is_nursery_space(lead) and 0 <= index < len(_NURSERY_VIEW_NAMES):
        name = _NURSERY_VIEW_NAMES[index]
    elif index <= 0:
        name = "Organized view"
    else:
        name = f"Room view {index + 1}"
    if missing:
        return f"{name} — still coming"
    return name


def _board_phrase(title: str, body: str, words: int = 8) -> str:
    """One short clause for the board. The full sentence stays in the guide."""
    body = _clean(body)
    title = _clean(title)
    rest = body
    if title and rest.lower().startswith(title.lower()):
        rest = rest[len(title) :].lstrip(" .,;:—-")
    picked = rest.split()[:words]
    if not picked:
        return ""
    phrase = " ".join(picked)
    if len(rest.split()) > words and not phrase.endswith((".", "!", "?")):
        phrase = phrase.rstrip(".,;:") + "."
    return phrase


def _role_label(title: str) -> str:
    low = title.lower()
    if any(key in low for key in ("sleep", "crib")):
        return "SLEEP"
    if any(key in low for key in ("dress", "change", "diaper", "dresser")):
        return "CHANGE"
    if any(key in low for key in ("comfort", "feed", "rock", "seat")):
        return "COMFORT"
    if any(key in low for key in ("path", "play", "circulat", "floor", "walk", "door")):
        return "CLEAR PATH"
    if "park" in low:
        return "PARK"
    if any(key in low for key in ("stor", "bin", "shelf")):
        return "STORAGE"
    if "work" in low:
        return "WORK"
    words = [word for word in title.split() if word]
    return " ".join(words[:2]).upper() or "ZONE"


def topdown_layout(
    deliverable: Dict[str, Any],
    *,
    organized: bool,
    space_theme: bool = False,
    lead: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Approximate top-down plan of this room: window, door, furniture, path.

    A diagram, not a generated floor-plan photo and not a measured drawing.
    Places sit on walls. They are not full-width bars.
    """
    from space_rails import is_nursery_space

    if is_nursery_space(lead):
        places = [dict(place) for place in _NURSERY_PLACES]
    else:
        roles: List[str] = []
        for zone in _zone_labels(deliverable):
            label = _role_label(zone)
            if label == "CLEAR PATH" or label in roles:
                continue
            roles.append(label)
        if not roles:
            roles = ["DAILY", "STORAGE", "COMFORT"]
        places = []
        for role, box in zip(roles[:3], _GENERIC_PLACE_BOXES):
            places.append({"id": role.lower().replace(" ", "-"), "label": role, "role": role, "box": box})
    furniture = [str(place["role"]) for place in places]
    if space_theme:
        caption = (
            "Approximate plan. Space theme stays: planets, moon, rockets, and astronauts. Not a measured plan."
        )
    elif organized:
        caption = (
            "Approximate top view of the organized room — furniture, window, door, and the clear path. Not a measured plan."
        )
    else:
        caption = (
            "Approximate top view from the plan — furniture, window, door, and the clear path. Not a photo and not a measured plan."
        )
    legend = list(_NURSERY_LEGEND) if is_nursery_space(lead) else []
    return {
        "window": "WINDOW",
        "door": "DOOR",
        "furniture": furniture,
        "places": places,
        "legend": legend,
        "path": [list(point) for point in _CLEAR_PATH],
        "circulation": "CLEAR PATH",
        "approximate": True,
        "matches_after": organized,
        "space_theme": space_theme,
        "drawing": "room",
        "caption": caption,
        "board_caption": "Approximate plan of this room. Not measured.",
    }


def plan_geometry(box: Tuple[int, int, int, int], topdown: Dict[str, Any]) -> Dict[str, Any]:
    """Room rectangle and wall-anchored furniture inside a plan card.

    The room stays recognizably a room (not a thin strip). Each furniture
    block stays under 58% of the room width, so it cannot become a bar.
    """
    x0, y0, x1, y1 = box
    title_h = 42
    caption_h = 28
    inner_l, inner_t = x0 + 14, y0 + title_h
    inner_r, inner_b = x1 - 14, max(inner_t + 48, y1 - caption_h)
    iw = max(48, inner_r - inner_l)
    ih = max(48, inner_b - inner_t)
    room_w, room_h = iw, ih
    # A very wide card stays a room, not a ribbon. A tall card stays a room too.
    if room_w > int(room_h * 2.35):
        room_w = int(room_h * 2.35)
    if room_h > int(room_w * 1.2):
        room_h = int(room_w * 1.2)
    rx0 = inner_l + max(0, (iw - room_w) // 2)
    ry0 = inner_t + max(0, (ih - room_h) // 2)
    room = (rx0, ry0, rx0 + room_w, ry0 + room_h)
    placed = []
    for place in topdown.get("places") or []:
        l, t, r, b = place.get("box") or (0.08, 0.08, 0.32, 0.28)
        rect = (
            rx0 + int(l * room_w),
            ry0 + int(t * room_h),
            rx0 + int(r * room_w),
            ry0 + int(b * room_h),
        )
        max_w = max(24, int(room_w * 0.56))
        if rect[2] - rect[0] > max_w:
            rect = (rect[0], rect[1], rect[0] + max_w, rect[3])
        if rect[2] <= rect[0] + 8:
            rect = (rect[0], rect[1], rect[0] + 12, rect[3])
        if rect[3] <= rect[1] + 8:
            rect = (rect[0], rect[1], rect[2], rect[1] + 12)
        placed.append({**place, "rect": rect})
    win_w = max(36, room_w // 3)
    win_x = rx0 + (room_w - win_w) // 2
    door_h = max(28, room_h // 5)
    door_y = ry0 + int(room_h * 0.22)
    return {
        "room": room,
        "window": (win_x, ry0, win_x + win_w, ry0 + max(10, room_h // 18)),
        "door": (rx0, door_y, rx0 + max(16, room_w // 28), door_y + door_h),
        "places": placed,
    }


def _crop_slots(after: Image.Image) -> List[Dict[str, Any]]:
    """Honest crops. The caption says they are details, not new camera angles."""
    boxes = (
        (0.0, 0.04, 0.58, 0.70),
        (0.42, 0.04, 1.0, 0.70),
        (0.10, 0.40, 0.90, 1.0),
    )
    return [
        {
            "image": _crop_frac(after, box),
            "caption": "Detail from the organized view",
            "source": "after_crop",
        }
        for box in boxes
    ]


def _source_pairs(images: Dict[str, Any]) -> List[Dict[str, Any]]:
    pairs = images.get("source_pairs") or []
    if not isinstance(pairs, list):
        return []
    return [pair for pair in pairs if isinstance(pair, dict)]


def _pair_slots(pairs: Sequence[Dict[str, Any]], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """One slot per required source. A missing after stays empty — never a crop."""
    slots = []
    for index, pair in enumerate(pairs):
        label = str(pair.get("label") or f"SOURCE_{index + 1:02d}")
        img = _open_image(pair.get("after"))
        missing = img is None
        slots.append(
            {
                "image": img,
                "caption": customer_view_caption(index, lead, missing=missing),
                "source": label,
                "missing": missing,
            }
        )
    return slots


def _detail_slots(images: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Per-source afters when the lead has several room photos.

    Crops and hero-derived extra views are optional details for a single
    organized photo. They never stand in for a missing source angle.
    """
    from space_rails import supporting_view_caption

    pairs = _source_pairs(images)
    if len(pairs) >= 2:
        return _pair_slots(pairs, lead)

    after = _open_image(images.get("after"))
    real = []
    for key in ("view_1", "view_2", "view_3"):
        img = _open_image(images.get(key))
        if img is not None:
            real.append({"image": img, "caption": supporting_view_caption(lead, key), "source": key})
    crops = _crop_slots(after) if after is not None else []
    if len(real) >= 2:
        return real[:4]
    if real:
        return (real + crops)[:4]
    return crops[:3]


def board_spec(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None, images: Dict[str, Any] | None) -> Dict[str, Any]:
    """Text and honesty flags for the board. Rendering uses this same spec."""
    lead = lead or {}
    images = normalize_pdf_images(images)
    doc = prepare_deliverable(lead, deliverable)
    kind = str(images.get("front_view_kind") or "placeholder")
    after = coerce_image_bytes(images.get("after"))
    before = coerce_image_bytes(images.get("before"))
    if after:
        hero_mode = "before_after" if before else "after_only"
        hero_label = "Organized view"
    elif before or kind == "original":
        hero_mode = "before_only"
        hero_label = "Your photo"
    else:
        hero_mode = "placeholder"
        hero_label = HERO_PLACEHOLDER_LABEL
    from space_rails import is_space_theme

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    pairs = _source_pairs(images)
    multi = len(pairs) >= 2
    details = _detail_slots(images, lead)
    themed = is_space_theme(lead, doc)
    if multi:
        complete = all(not slot.get("missing") for slot in details) and bool(details)
        # One strong hero plus the remaining full-room afters. Customer captions
        # name the view. SOURCE_/AFTER_ codes stay off the board.
        hero_mode = "hero_plus_afters"
        hero_missing = bool(details and details[0].get("missing"))
        hero_label = customer_view_caption(0, lead, missing=hero_missing)
        claims_organized = complete
    else:
        claims_organized = hero_mode in {"before_after", "after_only"}
    return {
        "deliverable": doc,
        "images": images,
        "headline": customer_project_title(lead, doc)
        or f"{_possessive(_first_name(lead))} {space_label(lead.get('space_type'))}",
        "plan_title": customer_project_title(lead, doc) or plan_title(lead.get("space_type")),
        "subtitle": _subtitle(doc, probe),
        "tagline": _tagline(lead),
        "moves": _moves(doc),
        "palette": _palette(lead, doc),
        "products": _products(doc),
        "roadmap": _roadmap(doc),
        "zones": _zone_labels(doc),
        "priorities": [_clean(str(x)) for x in (doc.get("needs") or []) if _clean(str(x))][:4],
        "budget_display": doc.get("budget_display") or "—",
        "stated_budget": doc.get("stated_budget") or "",
        "hero_mode": hero_mode,
        "hero_label": hero_label,
        "claims_organized_photo": claims_organized,
        "detail_captions": [slot["caption"] for slot in details],
        "detail_sources": [slot["source"] for slot in details],
        "space_theme": themed,
        "theme_line": "PLANETS · MOON · ROCKETS · ASTRONAUTS" if themed else "",
        "hero_before_overlay": False,
        "topdown": topdown_layout(
            doc,
            organized=claims_organized,
            space_theme=themed,
            lead=lead,
        ),
        "safety": safety_guidance(lead, doc),
        "placeholder_label": HERO_PLACEHOLDER_LABEL,
        "placeholder_sub": HERO_PLACEHOLDER_SUB,
    }


def _text(draw: ImageDraw.ImageDraw, xy, text, font, fill, max_width=None) -> None:
    draw.text(xy, text, font=font, fill=fill)


def _caption_bar(base: Image.Image, box: Tuple[int, int, int, int], label: str) -> None:
    x0, y0, x1, y1 = box
    bar_h = 30 if (y1 - y0) >= 140 else 22
    overlay = Image.new("RGBA", (max(1, x1 - x0), bar_h), (31, 61, 44, 214))
    base.paste(overlay, (x0, y1 - bar_h), overlay)
    draw = ImageDraw.Draw(base)
    size = 16 if bar_h >= 30 else 12
    font = _font("sans-bold", size)
    while size > 9 and draw.textlength(label, font=font) > max(8, x1 - x0 - 16):
        size -= 1
        font = _font("sans-bold", size)
    draw.text((x0 + 8, y1 - bar_h + max(2, (bar_h - size) // 2)), label, font=font, fill=WHITE)


def _empty_panel(base: Image.Image, box: Tuple[int, int, int, int], title: str, sub: str) -> None:
    draw = ImageDraw.Draw(base)
    _rounded(draw, box, 16, (236, 244, 239))
    x0, y0, x1, y1 = box
    width = x1 - x0 - 36
    title_lines = _fit(draw, title, _font("serif-bold", 28), width, 3)
    sub_lines = _fit(draw, sub, _font("sans", 16), width, 3)
    y = y0 + (y1 - y0) // 2 - 18 * (len(title_lines) + len(sub_lines))
    for line in title_lines:
        draw.text((x0 + 18, y), line, font=_font("serif-bold", 28), fill=GREEN)
        y += 34
    y += 6
    for line in sub_lines:
        draw.text((x0 + 18, y), line, font=_font("sans", 16), fill=MUTED)
        y += 22


def _draw_source_grid(base: Image.Image, box: Tuple[int, int, int, int], pairs: Sequence[Dict[str, Any]]) -> None:
    """Every required after at a useful size. A gap stays empty."""
    x0, y0, x1, y1 = box
    count = max(1, len(pairs))
    cols = 2 if count >= 2 else 1
    rows = (count + cols - 1) // cols
    gap = 12
    cell_w = (x1 - x0 - gap * (cols - 1)) // cols
    cell_h = (y1 - y0 - gap * (rows - 1)) // rows
    for index, pair in enumerate(pairs):
        col = index % cols
        row = index // cols
        cx = x0 + col * (cell_w + gap)
        cy = y0 + row * (cell_h + gap)
        cell = (cx, cy, cx + cell_w, cy + cell_h)
        after = _open_image(pair.get("after"))
        label = customer_view_caption(index, None, missing=after is None)
        if after is None:
            _empty_panel(base, cell, label, "Not filled from another angle.")
        else:
            _photo_or_empty(base, after, cell, label, label, "Not filled from another angle.")


def _photo_or_empty(base: Image.Image, img: Optional[Image.Image], box: Tuple[int, int, int, int], label: str, empty_title: str, empty_sub: str) -> None:
    """Paint ``img`` contained in ``box``. The slot may letterbox; it never crops."""
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    if img is None:
        _empty_panel(base, box, empty_title, empty_sub)
        return
    ox, oy, dw, dh = contain_pixels(img.width, img.height, w, h)
    if dw <= 0 or dh <= 0:
        _empty_panel(base, box, empty_title, empty_sub)
        return
    fitted = img.resize((dw, dh), Image.Resampling.LANCZOS)
    radius = min(16, max(4, dw // 10), max(4, dh // 10))
    _paste_round(base, fitted, (x0 + ox, y0 + oy), radius)
    _caption_bar(base, (x0 + ox, y0 + oy, x0 + ox + dw, y0 + oy + dh), label)


def _draw_space_glyphs(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Moon, ringed planet, and rocket. Marks the plan as a space-themed room."""
    draw.ellipse((x, y + 2, x + 14, y + 16), outline=CLAY, width=2)
    draw.pieslice((x + 4, y + 2, x + 16, y + 16), start=100, end=260, fill=CARD)
    draw.ellipse((x + 22, y + 3, x + 34, y + 15), outline=GREEN, width=2)
    draw.arc((x + 16, y + 6, x + 40, y + 13), start=200, end=340, fill=GREEN, width=2)
    draw.polygon([(x + 50, y), (x + 58, y + 16), (x + 42, y + 16)], fill=CLAY)


def _section_kicker(draw: ImageDraw.ImageDraw, x: int, y: int, number: str, title: str) -> None:
    """Numbered section mark, matching the editorial reference."""
    draw.ellipse((x, y, x + 26, y + 26), outline=CLAY, width=2)
    num_font = _font("sans-bold", 13)
    nw = draw.textlength(number, font=num_font)
    draw.text((x + (26 - nw) / 2, y + 4), number, font=num_font, fill=CLAY)
    draw.text((x + 34, y + 3), title, font=_font("sans-bold", 16), fill=GREEN)


def clear_path_points(geo: Dict[str, Any]) -> List[Tuple[int, int]]:
    """Stroke from the door opening into open floor. The first point meets the door."""
    room = geo["room"]
    door = geo["door"]
    rx0, ry0, rx1, ry1 = room
    rw, rh = max(1, rx1 - rx0), max(1, ry1 - ry0)
    start = (rx0 + 1, (door[1] + door[3]) // 2)

    def _at(fx: float, fy: float) -> Tuple[int, int]:
        return (rx0 + int(fx * rw), ry0 + int(fy * rh))

    return [start, _at(0.18, 0.50), _at(0.40, 0.48)]


def _legend_band_height(legend: Sequence[Dict[str, Any]]) -> int:
    return 52 if legend else 0


def _draw_zone_legend(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    legend: Sequence[Dict[str, Any]],
) -> None:
    x0, y0, x1, y1 = box
    if not legend or y1 <= y0:
        return
    cols = 2
    rows = (len(legend) + cols - 1) // cols
    col_w = max(40, (x1 - x0) // cols)
    row_h = max(16, (y1 - y0) // max(1, rows))
    name_font = _font("sans", 15)
    num_font = _font("sans-bold", 11)
    for index, item in enumerate(legend):
        col, row = index % cols, index // cols
        x = x0 + col * col_w
        y = y0 + row * row_h
        draw.ellipse((x, y + 1, x + 18, y + 19), fill=GREEN)
        number = str(item.get("number") or "")
        nw = draw.textlength(number, font=num_font)
        draw.text((x + (18 - nw) / 2, y + 3), number, font=num_font, fill=WHITE)
        draw.text((x + 24, y + 1), str(item.get("name") or ""), font=name_font, fill=INK)


def _draw_plan(base: Image.Image, box: Tuple[int, int, int, int], topdown: Dict[str, Any]) -> None:
    """Top-down sketch of this room. Zones sit on walls. No dimensions."""
    draw = ImageDraw.Draw(base)
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, y1 = box
    _section_kicker(draw, x0 + 14, y0 + 10, "4", "ROOM PLAN")
    approx = "APPROXIMATE"
    afont = _font("sans", 13)
    aw = draw.textlength(approx, font=afont)
    draw.text((x1 - 16 - aw, y0 + 14), approx, font=afont, fill=MUTED)
    if topdown.get("space_theme"):
        _draw_space_glyphs(draw, x1 - 16 - aw - 78, y0 + 12)
    legend = [item for item in (topdown.get("legend") or []) if isinstance(item, dict)]
    legend_h = _legend_band_height(legend)
    geo = plan_geometry((x0, y0, x1, y1 - legend_h), topdown)
    rx0, ry0, rx1, ry1 = geo["room"]
    floor = (250, 246, 239)
    draw.rounded_rectangle(geo["room"], radius=12, fill=floor, outline=GREEN, width=4)
    wx0, _wy0, wx1, _wy1 = geo["window"]
    draw.rectangle((wx0, ry0 - 1, wx1, ry0 + 7), fill=floor)
    draw.line((wx0, ry0 - 8, wx1, ry0 - 8), fill=CLAY, width=4)
    draw.line((wx0, ry0 - 2, wx1, ry0 - 2), fill=CLAY, width=2)
    rw, rh = max(1, rx1 - rx0), max(1, ry1 - ry0)

    def _at(fx: float, fy: float) -> Tuple[int, int]:
        return (rx0 + int(fx * rw), ry0 + int(fy * rh))

    window_label = str(topdown.get("window") or "WINDOW")
    wfont = _font("sans-bold", 15)
    ww = draw.textlength(window_label, font=wfont)
    label_y = ry0 - 22 if ry0 - 22 > y0 + 34 else ry0 + 8
    draw.text(((wx0 + wx1 - ww) / 2, label_y), window_label, font=wfont, fill=CLAY)
    _dx0, dy0, _dx1, dy1 = geo["door"]
    draw.rectangle((rx0 - 1, dy0, rx0 + 10, dy1), fill=floor)
    swing = max(26, dy1 - dy0)
    draw.arc((rx0 - 2, dy0, rx0 + swing, dy0 + swing), start=280, end=10, fill=GREEN, width=2)
    door_at = _at(0.08, 0.30)
    draw.text(door_at, str(topdown.get("door") or "DOOR"), font=_font("sans-bold", 14), fill=GREEN)
    for place in geo["places"]:
        rect = place["rect"]
        draw.rounded_rectangle(rect, radius=8, fill=GREEN_SOFT, outline=GREEN, width=2)
        number = str(place.get("number") or "")
        label = str(place.get("label") or place.get("role") or "")
        text_left = rect[0] + 6
        if number:
            bx, by = rect[0] + 6, rect[1] + 6
            draw.ellipse((bx, by, bx + 18, by + 18), fill=GREEN)
            nfont = _font("sans-bold", 11)
            nw = draw.textlength(number, font=nfont)
            draw.text((bx + (18 - nw) / 2, by + 2), number, font=nfont, fill=WHITE)
            text_left = bx + 22
        pw = max(12, rect[2] - text_left - 6)
        ph = max(12, rect[3] - rect[1] - 8)
        size = 16 if ph >= 48 else 13
        font = _font("sans-bold", size)
        while size > 11 and draw.textlength(label, font=font) > pw:
            size -= 1
            font = _font("sans-bold", size)
        tw = draw.textlength(label, font=font)
        tx = text_left if number else rect[0] + max(4, (rect[2] - rect[0] - tw) / 2)
        ty = rect[1] + max(4, (rect[3] - rect[1] - size) / 2)
        if number and ty < rect[1] + 6:
            ty = rect[1] + 6
        draw.text((tx, ty), label, font=font, fill=GREEN)
    path = str(topdown.get("circulation") or "CLEAR PATH")
    # The stroke starts on the door opening and stops in open floor, short of the furniture.
    start, mid, end = clear_path_points(geo)
    draw.line([start, mid, end], fill=CLAY, width=4)
    draw.polygon([(end[0] + 10, end[1]), (end[0] - 2, end[1] - 7), (end[0] - 2, end[1] + 7)], fill=CLAY)
    path_at = (start[0] + 8, min(mid[1], start[1]) + 8)
    draw.text(path_at, path, font=_font("sans-bold", 13), fill=CLAY)
    if legend:
        _draw_zone_legend(draw, (x0 + 16, y1 - 26 - legend_h, x1 - 16, y1 - 26), legend)
    caption = str(topdown.get("board_caption") or "Approximate plan of this room. Not measured.")
    fitted = _fit(draw, caption, _font("sans", 15), x1 - x0 - 32, 1)
    if fitted:
        draw.text((x0 + 16, y1 - 24), fitted[0], font=_font("sans", 15), fill=MUTED)


def _draw_moves(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], moves: Sequence[Dict[str, str]]) -> None:
    x0, y0, x1, y1 = box
    draw.text((x0, y0), "DESIGN MOVES", font=_font("sans-bold", 13), fill=GREEN)
    items = list(moves)[:6]
    if not items:
        return
    cols = 2
    rows = 3
    gap_x, gap_y = 8, 6
    cell_w = (x1 - x0 - gap_x) // cols
    cell_h = (y1 - y0 - 22 - gap_y * (rows - 1)) // rows
    top = y0 + 22
    for i, move in enumerate(items):
        col, row = i % cols, i // cols
        cx = x0 + col * (cell_w + gap_x)
        cy = top + row * (cell_h + gap_y)
        _rounded(draw, (cx, cy, cx + cell_w, cy + cell_h), 12, CARD)
        draw.ellipse((cx + 8, cy + 10, cx + 30, cy + 32), outline=CLAY, width=2)
        draw.text((cx + 14, cy + 12), str(i + 1), font=_font("sans-bold", 12), fill=CLAY)
        draw.text((cx + 36, cy + 12), move["title"], font=_font("sans-bold", 12), fill=INK)
        lines = _fit(draw, move["body"], _font("sans", 12), cell_w - 20, 3)
        ty = cy + 36
        for line in lines:
            draw.text((cx + 10, ty), line, font=_font("sans", 12), fill=MUTED)
            ty += 15


def _draw_mark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color=GREEN) -> None:
    """House mark used on the companion PDF, drawn as vectors — not a baked logo image."""
    s = size
    peak = (x + s * 0.5, y)
    eave_r = (x + s, y + s * 0.42)
    bot_r = (x + s, y + s)
    bot_l = (x, y + s)
    eave_l = (x, y + s * 0.42)
    draw.line([peak, eave_r, bot_r, bot_l, eave_l, peak], fill=color, width=max(2, size // 16))
    wave_y = y + s * 0.62
    draw.arc((x + s * 0.18, wave_y - s * 0.12, x + s * 0.55, wave_y + s * 0.12), start=200, end=340, fill=color, width=max(2, size // 18))
    draw.arc((x + s * 0.42, wave_y - s * 0.08, x + s * 0.82, wave_y + s * 0.16), start=200, end=350, fill=color, width=max(2, size // 18))


def _image_aspect(data: Optional[bytes]) -> Optional[float]:
    img = _open_image(data)
    if img is None or img.width <= 0 or img.height <= 0:
        return None
    return img.width / float(img.height)


def _hero_aspect(spec: Dict[str, Any]) -> Optional[float]:
    """Aspect of the photo the hero frame will actually paint."""
    images = spec.get("images") or {}
    mode = spec.get("hero_mode")
    pairs = _source_pairs(images)
    data = None
    if mode == "hero_plus_afters":
        data = (pairs[0].get("after") if pairs else None) or images.get("after")
    elif mode in {"before_after", "after_only"}:
        data = images.get("after") or images.get("front_view")
    elif mode == "before_only":
        data = images.get("before") or images.get("front_view")
    return _image_aspect(data)


def _fitted_frame(aspect: Optional[float], max_w: int, max_h: int, *, missing_h: int) -> Tuple[int, int]:
    """Natural-ratio frame. A missing photo keeps a full-width labeled panel."""
    if aspect is None or aspect <= 0:
        return (max(1, max_w), max(1, min(missing_h, max_h)))
    return frame_size(aspect, max_w, max_h)


def _source_aspects(pairs: Sequence[Dict[str, Any]]) -> List[float]:
    aspects = []
    for pair in pairs:
        aspect = _image_aspect(pair.get("after"))
        aspects.append(aspect if aspect and aspect > 0 else 0.75)
    return aspects


def _row_height_for_width(aspects: Sequence[float], width: int, gap: int, max_h: int) -> int:
    """Tallest row whose natural-ratio frames still fit in ``width``."""
    if not aspects or max_h <= 0 or width <= 0:
        return max(1, min(40, max_h))
    lo, hi = 1, max(1, max_h)
    best = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        total = gap * (len(aspects) - 1)
        for aspect in aspects:
            fw, _fh = frame_size(aspect, width, mid)
            total += fw
        if total <= width:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _place_row(
    pairs: Sequence[Dict[str, Any]],
    x: int,
    y: int,
    width: int,
    max_h: int,
) -> Tuple[List[Tuple[int, int, int, int]], int]:
    """Pack each photo at its own aspect. Frames are not stretched into a wide cell."""
    if not pairs:
        return [], 0
    gap = 12
    aspects = _source_aspects(pairs)
    row_h = _row_height_for_width(aspects, width, gap, max_h)
    frames = [frame_size(aspect, width, row_h) for aspect in aspects]
    used = sum(item[0] for item in frames) + gap * (len(frames) - 1)
    cursor = x + max(0, (width - used) // 2)
    boxes: List[Tuple[int, int, int, int]] = []
    for fw, fh in frames:
        top = y + max(0, (row_h - fh) // 2)
        boxes.append((cursor, top, cursor + fw, top + fh))
        cursor += fw + gap
    return boxes, row_h


def board_layout(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Shared portrait boxes so the PNG and the tests describe the same frames.

    Room-photo frames follow each file's aspect ratio. A landscape hero is
    given enough height to reach across the page. A portrait hero sits beside
    the other views and the short copy, so the side of the photo is not blank.
    Nothing is cover-cropped.
    """
    width, height = PORTRAIT_W, PORTRAIT_H
    margin = 36
    content_w = width - 2 * margin
    images = spec.get("images") or {}
    pairs = _source_pairs(images)
    multi = spec.get("hero_mode") == "hero_plus_afters" and len(pairs) >= 2
    rest = pairs[1:] if multi else []
    aspect = _hero_aspect(spec)
    header = (margin, 16, width - margin, 204)
    footer = (margin, height - 40, width - margin, height - 16)
    y_start = header[3] + 12
    bottom = footer[1] - 8
    editorial = bool(multi and aspect is not None and aspect < 1.0)
    product_count = len(spec.get("products") or [])
    if editorial:
        laid = _layout_editorial(
            width, height, margin, content_w, y_start, bottom, rest, aspect, header, footer, product_count
        )
    else:
        laid = _layout_stacked(
            width, height, margin, content_w, y_start, bottom, rest, aspect, header, footer, product_count
        )
    laid["multi"] = multi
    laid["editorial"] = editorial
    return laid


def _stack_bands(
    x0: int,
    y0: int,
    x1: int,
    height: int,
    weights: Sequence[float],
) -> Tuple[Tuple[int, int, int, int], ...]:
    """Split a column into boxes. A zero weight yields an empty box."""
    gap = 8
    active = [(i, w) for i, w in enumerate(weights) if w > 0]
    if not active or height <= 0 or x1 <= x0:
        return tuple((x0, y0, x1, y0) for _ in weights)
    gaps = gap * (len(active) - 1)
    usable = max(len(active), height - gaps)
    total = sum(w for _i, w in active) or 1.0
    boxes: List[Tuple[int, int, int, int]] = [(x0, y0, x1, y0) for _ in weights]
    y = y0
    for n, (index, weight) in enumerate(active):
        if n == len(active) - 1:
            band_h = max(1, y0 + height - y)
        else:
            band_h = max(1, int(usable * (weight / total)))
        boxes[index] = (x0, y, x1, y + band_h)
        y += band_h + gap
    return tuple(boxes)


def _layout_stacked(
    width: int,
    height: int,
    margin: int,
    content_w: int,
    y_start: int,
    bottom: int,
    rest: Sequence[Dict[str, Any]],
    aspect: Optional[float],
    header: Tuple[int, int, int, int],
    footer: Tuple[int, int, int, int],
    product_count: int = 0,
) -> Dict[str, Any]:
    gap = 12
    # The lower band is a room sketch beside the short copy, so the plan
    # has enough height to read as this room.
    lower_min = 500
    photo_budget = max(280, bottom - y_start - lower_min)
    support_max = 0
    if rest:
        support_max = max(140, min(240, int(photo_budget * 0.28)))
    hero_max_h = max(200, photo_budget - (support_max + gap if rest else 0))
    if aspect and aspect > 0:
        fill_h = int(round(content_w / float(aspect)))
        hero_max_h = min(hero_max_h, fill_h)
    hero_w, hero_h = _fitted_frame(aspect, content_w, hero_max_h, missing_h=min(480, hero_max_h))
    y = y_start
    hx = margin + max(0, (content_w - hero_w) // 2)
    hero = (hx, y, hx + hero_w, y + hero_h)
    y = hero[3] + gap
    sources: List[Tuple[int, int, int, int]] = []
    if rest:
        sources, used = _place_row(rest, margin, y, content_w, max(120, photo_budget - hero_h - gap))
        y += used + gap
    lower_h = max(160, bottom - y)
    plan_w = max(280, int(content_w * 0.62))
    plan = (margin, y, margin + plan_w, y + lower_h)
    right_x = plan[2] + 10
    if product_count:
        bands = _stack_bands(right_x, y, width - margin, lower_h, (0.20, 0.24, 0.16, 0.24, 0.16))
        outcome, changes, palette, shopping, roadmap = bands
    else:
        bands = _stack_bands(right_x, y, width - margin, lower_h, (0.24, 0.32, 0.22, 0.22))
        outcome, changes, palette, roadmap = bands
        shopping = (right_x, y, right_x, y)
    return {
        "size": (width, height),
        "header": header,
        "hero": hero,
        "sources": sources,
        "outcome": outcome,
        "changes": changes,
        "plan": plan,
        "palette": palette,
        "shopping": shopping,
        "roadmap": roadmap,
        "footer": footer,
    }


def _layout_editorial(
    width: int,
    height: int,
    margin: int,
    content_w: int,
    y_start: int,
    bottom: int,
    rest: Sequence[Dict[str, Any]],
    aspect: Optional[float],
    header: Tuple[int, int, int, int],
    footer: Tuple[int, int, int, int],
    product_count: int = 0,
) -> Dict[str, Any]:
    """Portrait hero on the left. A compact 2×2 sits beside it, then shopping and photos.

    What's New is a fixed card, not the empty stretch down to the thumbnails.
    The plan stays under the hero, with palette and roadmap beside it.
    """
    gap = 12
    lower_min = 460
    photo_h = max(480, bottom - y_start - lower_min - gap)
    hero_max_w = max(240, int(content_w * 0.48))
    hero_w, hero_h = _fitted_frame(aspect, hero_max_w, photo_h, missing_h=photo_h)
    hero = (margin, y_start, margin + hero_w, y_start + hero_h)
    right_x = hero[2] + 12
    right_w = max(140, width - margin - right_x)
    photo_bottom = hero[3]

    y = y_start
    outcome_h = 112
    outcome = (right_x, y, right_x + right_w, y + outcome_h)
    y = outcome[3] + 8
    changes_h = 320
    changes = (right_x, y, right_x + right_w, y + changes_h)
    y = changes[3] + 8
    shop_h = _shopping_card_height(product_count)
    if shop_h:
        shopping = (right_x, y, right_x + right_w, y + shop_h)
        y = shopping[3] + 8
    else:
        shopping = (right_x, y, right_x + right_w, y)
    row_max = max(110, photo_bottom - y)
    sources, _used = _place_row(rest, right_x, y, right_w, row_max) if rest else ([], 0)
    column_bottom = photo_bottom
    if sources:
        column_bottom = max(column_bottom, max(box[3] for box in sources))
    plan_top = column_bottom + gap
    lower_h = max(180, bottom - plan_top)
    plan_w = max(300, int(content_w * 0.64))
    plan = (margin, plan_top, margin + plan_w, plan_top + lower_h)
    bands = _stack_bands(plan[2] + 10, plan_top, width - margin, lower_h, (0.0, 0.0, 0.48, 0.52))
    _skip_a, _skip_b, palette, roadmap = bands
    return {
        "size": (width, height),
        "header": header,
        "hero": hero,
        "sources": sources,
        "outcome": outcome,
        "changes": changes,
        "shopping": shopping,
        "plan": plan,
        "palette": palette,
        "roadmap": roadmap,
        "footer": footer,
    }


def _draw_header(base: Image.Image, spec: Dict[str, Any], box: Tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(base)
    x0, y0, x1, _y1 = box
    _draw_mark(draw, x0, y0 + 4, 46, GREEN)
    draw.text((x0 + 58, y0 + 6), "FlowSpace", font=_font("serif-bold", 28), fill=GREEN)
    draw.text((x0 + 58, y0 + 40), "Clear space. Create flow. Live better.", font=_font("sans", 13), fill=MUTED)

    badge = (x1 - 228, y0, x1, y0 + 78)
    _rounded(draw, badge, 16, GREEN)
    draw.text((badge[0] + 22, badge[1] + 12), "FLOWSPACE", font=_font("sans-bold", 12), fill=(207, 226, 215))
    draw.text((badge[0] + 22, badge[1] + 28), "BLUEPRINT", font=_font("serif-bold", 22), fill=WHITE)
    draw.text((badge[0] + 22, badge[1] + 54), "Your space. Your flow. Your life.", font=_font("sans", 11), fill=(207, 226, 215))

    headline = _fit(draw, spec.get("headline") or "Your space", _font("serif-bold", 38), x1 - x0, 1)
    draw.text((x0, y0 + 88), headline[0] if headline else "Your space", font=_font("serif-bold", 38), fill=INK)
    brand = _fit(draw, BRAND_LINE, _font("sans-bold", 14), x1 - x0, 1)
    draw.text((x0, y0 + 134), brand[0] if brand else BRAND_LINE, font=_font("sans-bold", 14), fill=GREEN)
    personal = spec.get("tagline") or ""
    if spec.get("theme_line"):
        personal = f"{personal}   {spec['theme_line']}".strip()
    fitted = _fit(draw, personal, _font("sans", 15), x1 - x0, 1)
    if fitted:
        draw.text((x0, y0 + 156), fitted[0], font=_font("sans", 15), fill=MUTED)
    draw.rectangle((x0, y0 + 184, x1, y0 + 187), fill=GREEN)


def _draw_outcome(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], text: str) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, y1 = box
    _section_kicker(draw, x0 + 12, y0 + 10, "2", "THE OUTCOME")
    size = 24 if (y1 - y0) >= 108 else 20
    lines = _fit(draw, text, _font("serif-italic", size), x1 - x0 - 28, 2)
    y = y0 + 42
    for line in lines:
        if y > y1 - size:
            break
        draw.text((x0 + 14, y), line, font=_font("serif-italic", size), fill=INK)
        y += size + 4


def _draw_changes(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], moves: Sequence[Dict[str, str]]) -> None:
    """Compact 2×2 cards. The section box is sized to the grid, not left as a void."""
    x0, y0, x1, y1 = box
    _rounded(draw, box, 16, CARD)
    _section_kicker(draw, x0 + 12, y0 + 10, "3", "WHAT'S NEW & WHY")
    items = list(moves)[:4]
    if not items:
        draw.text((x0 + 14, y0 + 48), "The companion guide lists each change.", font=_font("sans", 18), fill=MUTED)
        return
    cols = 2 if len(items) > 1 else 1
    rows = (len(items) + cols - 1) // cols
    gap_x, gap_y = 10, 10
    inner_top = y0 + 46
    inner_h = max(rows * 36, y1 - inner_top - 12)
    cell_w = max(40, (x1 - x0 - 24 - gap_x * (cols - 1)) // cols)
    cell_h = max(36, (inner_h - gap_y * (rows - 1)) // rows)
    title_size = 20 if cell_h >= 108 else (17 if cell_h >= 78 else 14)
    body_size = 17 if cell_h >= 108 else (15 if cell_h >= 78 else 13)
    body_lines = 3 if cell_h >= 108 else (2 if cell_h >= 72 else 1)
    words = 20 if body_lines >= 3 else 12
    inner = (247, 244, 239)
    for index, move in enumerate(items):
        col, row = index % cols, index // cols
        cx = x0 + 12 + col * (cell_w + gap_x)
        cy = inner_top + row * (cell_h + gap_y)
        draw.rounded_rectangle((cx, cy, cx + cell_w, cy + cell_h), radius=12, fill=inner, outline=RULE, width=2)
        draw.ellipse((cx + 8, cy + 8, cx + 32, cy + 32), outline=CLAY, width=2)
        draw.text((cx + 15, cy + 11), str(index + 1), font=_font("sans-bold", 13), fill=CLAY)
        title = _fit(draw, move.get("title") or "", _font("sans-bold", title_size), cell_w - 44, 1)
        draw.text((cx + 38, cy + 8), title[0] if title else "", font=_font("sans-bold", title_size), fill=INK)
        phrase = _board_phrase(move.get("title") or "", move.get("body") or "", words=words)
        body = _fit(draw, phrase, _font("sans", body_size), cell_w - 20, body_lines)
        ty = cy + 14 + title_size
        for line in body:
            if ty > cy + cell_h - body_size - 2:
                break
            draw.text((cx + 10, ty), line, font=_font("sans", body_size), fill=INK)
            ty += body_size + 3


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> str:
    text = _clean(text)
    if width <= 0 or not text:
        return ""
    if draw.textlength(text, font=font) <= width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and draw.textlength(trimmed + ellipsis, font=font) > width:
        trimmed = trimmed[:-1].rstrip()
    return (trimmed + ellipsis) if trimmed else ellipsis


def _shopping_card_height(count: int) -> int:
    """Height for a real line-item card. Zero when there is nothing to shop."""
    if count <= 0:
        return 0
    shown = min(count, 5)
    extra = 22 if count > shown else 0
    return 46 + shown * 26 + extra + 12


def _draw_shopping(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    products: Sequence[Dict[str, str]],
    total: str,
) -> None:
    """Real shopping lines and their total. No invented products or a lone price."""
    x0, y0, x1, y1 = box
    rows = [row for row in products if str(row.get("name") or "").strip()]
    if y1 - y0 < 56 or not rows:
        return
    _rounded(draw, box, 16, CARD)
    draw.text((x0 + 14, y0 + 12), "SHOPPING", font=_font("sans-bold", 16), fill=GREEN)
    if total and total not in {"—", "-"}:
        font = _font("serif-bold", 22)
        tw = draw.textlength(total, font=font)
        draw.text((x1 - 14 - tw, y0 + 8), total, font=font, fill=GREEN)
    top = y0 + 44
    row_h = 26
    room = max(1, (y1 - top - 8) // row_h)
    if len(rows) <= room:
        show_n = len(rows)
        more = 0
    else:
        show_n = max(1, room - 1)
        more = len(rows) - show_n
    price_font = _font("sans-bold", 15)
    name_font = _font("sans", 15)
    for index, row in enumerate(rows[:show_n]):
        y = top + index * row_h
        if y > y1 - 18:
            break
        price = str(row.get("price") or "")
        price_w = draw.textlength(price, font=price_font) if price else 0
        name_w = max(40, x1 - x0 - 36 - price_w)
        name = _ellipsize(draw, str(row.get("name") or ""), name_font, name_w)
        draw.text((x0 + 14, y), name, font=name_font, fill=INK)
        if price:
            draw.text((x1 - 14 - price_w, y), price, font=price_font, fill=GREEN)
    if more:
        y = top + show_n * row_h
        if y <= y1 - 16:
            draw.text((x0 + 14, y), f"{more} more in the companion guide", font=_font("sans", 14), fill=MUTED)


def _draw_palette_row(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], swatches: Sequence[Dict[str, str]]) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, y1 = box
    _section_kicker(draw, x0 + 12, y0 + 8, "5", "PALETTE")
    items = list(swatches)[:5] or [{"name": "Cream", "hex": "#F3EEE6", "note": "Textile"}]
    gap = 8
    avail = x1 - x0 - 24
    sw = max(28, min(72, (avail - gap * (len(items) - 1)) // max(1, len(items))))
    y = y0 + 40
    swatch_h = max(22, min(36, y1 - y - 36))
    for index, swatch in enumerate(items):
        x = x0 + 12 + index * (sw + gap)
        draw.rounded_rectangle((x, y, x + sw, y + swatch_h), radius=8, fill=_rgb(swatch.get("hex") or "#C5C8C6"))
        name_font = _font("sans", 12)
        # Wrap the real name. Do not clip it into a different word with a period.
        lines = _wrap(draw, swatch.get("name") or "", name_font, max(sw + 4, 56))[:2]
        ty = y + swatch_h + 4
        for line in lines:
            if ty > y1 - 14:
                break
            draw.text((x, ty), line, font=name_font, fill=INK)
            ty += 14


def _draw_roadmap_row(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], steps: Sequence[Dict[str, str]], budget: str) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, y1 = box
    _section_kicker(draw, x0 + 12, y0 + 8, "6", "ROADMAP")
    # A total belongs with the shopping lines. A lone figure is not drawn here.
    if budget and budget not in {"—", "-"}:
        font = _font("serif-bold", 22)
        tw = draw.textlength(budget, font=font)
        draw.text((x1 - 12 - tw, y0 + 8), budget, font=font, fill=GREEN)
    steps = list(steps)[:3]
    if not steps:
        return
    top = y0 + 42
    step_h = max(18, (y1 - top - 8) // len(steps))
    for index, step in enumerate(steps):
        y = top + index * step_h
        if y > y1 - 16:
            break
        draw.ellipse((x0 + 12, y, x0 + 30, y + 18), fill=GREEN)
        draw.text((x0 + 17, y + 1), str(index + 1), font=_font("sans-bold", 11), fill=WHITE)
        title = _fit(draw, step.get("title") or "", _font("sans-bold", 14), x1 - x0 - 52, 1)
        draw.text((x0 + 36, y), title[0] if title else "", font=_font("sans-bold", 14), fill=INK)
        if step_h >= 34:
            phrase = _board_phrase(step.get("title") or "", step.get("body") or "", words=18)
            lines = 2 if step_h >= 52 else 1
            body = _fit(draw, phrase, _font("sans", 13), x1 - x0 - 52, lines)
            ty = y + 16
            for line in body:
                if ty > y1 - 14:
                    break
                draw.text((x0 + 36, ty), line, font=_font("sans", 13), fill=MUTED)
                ty += 15


def _draw_board_footer(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int]) -> None:
    x0, y0, x1, _y1 = box
    text = "Companion guide: steps, shopping, safety, climate, and the weekly reset."
    fitted = _fit(draw, text, _font("sans", 13), x1 - x0, 1)
    if fitted:
        draw.text((x0, y0), fitted[0], font=_font("sans", 13), fill=MUTED)


def _hero_frame(spec: Dict[str, Any], images: Dict[str, Any]) -> Tuple[Optional[Image.Image], str, str, str]:
    before = _open_image(images.get("before"))
    after = _open_image(images.get("after"))
    pairs = _source_pairs(images)
    if spec["hero_mode"] == "before_only" and before is None:
        before = _open_image(images.get("front_view"))
    if spec["hero_mode"] == "after_only" and after is None:
        after = _open_image(images.get("front_view"))
    if spec["hero_mode"] == "hero_plus_afters":
        pair = pairs[0] if pairs else {}
        hero_after = _open_image(pair.get("after")) if pair else after
        label = spec.get("hero_label") or "Organized view"
        return hero_after, label, "This view is still coming", "We do not invent an after photo."
    if spec["hero_mode"] in {"before_after", "after_only"}:
        return after, spec.get("hero_label") or "Organized view", "Organized view unavailable", "We do not invent an after photo."
    if spec["hero_mode"] == "before_only":
        return before, spec["hero_label"], spec["hero_label"], "We do not invent an organized after."
    return None, spec.get("hero_label") or HERO_PLACEHOLDER_LABEL, HERO_PLACEHOLDER_LABEL, HERO_PLACEHOLDER_SUB


def _empty_thumb(base: Image.Image, box: Tuple[int, int, int, int], title: str, sub: str) -> None:
    draw = ImageDraw.Draw(base)
    _rounded(draw, box, 16, (236, 244, 239))
    x0, y0, x1, y1 = box
    width = x1 - x0 - 20
    title_lines = _fit(draw, title, _font("sans-bold", 14), width, 3)
    sub_lines = _fit(draw, sub, _font("sans", 12), width, 3)
    y = y0 + 16
    for line in title_lines:
        draw.text((x0 + 10, y), line, font=_font("sans-bold", 14), fill=GREEN)
        y += 18
    y += 4
    for line in sub_lines:
        if y > y1 - 16:
            break
        draw.text((x0 + 10, y), line, font=_font("sans", 12), fill=MUTED)
        y += 16


def customer_board_text(spec: Dict[str, Any]) -> str:
    """Every customer-facing string the portrait board is allowed to paint.

    Review codes (SOURCE_, AFTER_, lead ids) are not part of this text.
    """
    parts: List[str] = [
        spec.get("headline") or "",
        spec.get("plan_title") or "",
        spec.get("subtitle") or "",
        spec.get("tagline") or "",
        spec.get("theme_line") or "",
        spec.get("hero_label") or "",
        BRAND_LINE,
        "FlowSpace",
        "Clear space. Create flow. Live better.",
        "Your space. Your flow. Your life.",
        "The outcome",
        "What's new & why",
        "Room plan",
        "Palette",
        "Roadmap",
        "Companion guide: steps, shopping, safety, climate, and the weekly reset.",
    ]
    products = spec.get("products") or []
    if products:
        parts.append("Shopping")
        parts.append(spec.get("budget_display") or "")
        for row in products:
            parts.append(str(row.get("name") or ""))
            parts.append(str(row.get("price") or ""))
    for caption in spec.get("detail_captions") or []:
        parts.append(str(caption))
    for move in spec.get("moves") or []:
        parts.append(str(move.get("title") or ""))
        parts.append(_board_phrase(str(move.get("title") or ""), str(move.get("body") or ""), words=20))
    topdown = spec.get("topdown") or {}
    parts.append(str(topdown.get("board_caption") or ""))
    parts.append(str(topdown.get("window") or ""))
    parts.append(str(topdown.get("door") or ""))
    parts.append(str(topdown.get("circulation") or ""))
    for place in topdown.get("places") or []:
        parts.append(str(place.get("label") or ""))
        parts.append(str(place.get("number") or ""))
        parts.append(str(place.get("zone") or ""))
    for item in topdown.get("legend") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("number") or ""))
            parts.append(str(item.get("name") or ""))
    for swatch in spec.get("palette") or []:
        parts.append(str(swatch.get("name") or ""))
        parts.append(str(swatch.get("note") or ""))
    for step in spec.get("roadmap") or []:
        parts.append(str(step.get("title") or ""))
        parts.append(_board_phrase(str(step.get("title") or ""), str(step.get("body") or ""), words=18))
    return "\n".join(parts)


def build_image_board(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Any],
) -> bytes:
    """Render the portrait Blueprint PNG. Text and the logo are drawn here."""
    spec = board_spec(lead, deliverable, images)
    layout = board_layout(spec)
    width, height = layout["size"]
    base = Image.new("RGBA", (width, height), PAPER + (255,))
    _draw_header(base, spec, layout["header"])

    hero_img, hero_label, empty_title, empty_sub = _hero_frame(spec, spec["images"])
    if hero_img is None and spec["hero_mode"] == "placeholder":
        _empty_panel(base, layout["hero"], empty_title, empty_sub)
    else:
        _photo_or_empty(base, hero_img, layout["hero"], hero_label, empty_title, empty_sub)

    pairs = _source_pairs(spec["images"])
    for index, (box, pair) in enumerate(zip(layout["sources"], pairs[1:]), start=1):
        after = _open_image(pair.get("after"))
        label = customer_view_caption(index, lead, missing=after is None)
        if after is None:
            _empty_thumb(base, box, label, "Not filled from another angle.")
        else:
            _photo_or_empty(base, after, box, label, label, "Not filled from another angle.")

    draw = ImageDraw.Draw(base)
    _draw_outcome(draw, layout["outcome"], spec.get("subtitle") or "")
    _draw_changes(draw, layout["changes"], spec.get("moves") or [])
    shopping_box = layout.get("shopping")
    if shopping_box and spec.get("products"):
        _draw_shopping(draw, shopping_box, spec.get("products") or [], spec.get("budget_display") or "")
    _draw_plan(base, layout["plan"], spec["topdown"])
    draw = ImageDraw.Draw(base)
    _draw_palette_row(draw, layout["palette"], spec.get("palette") or [])
    _draw_roadmap_row(draw, layout["roadmap"], spec.get("roadmap") or [], "")
    _draw_board_footer(draw, layout["footer"])

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


