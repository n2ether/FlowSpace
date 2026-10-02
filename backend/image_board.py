"""Primary visual FlowSpace Blueprint.

One portrait PNG (~2:3) per Blueprint, assembled here from real text layers
and the FlowSpace mark. Photos are pasted in as themselves. The image model
never draws this board or its type. Shopping, safety, climate, the weekly
reset, and the full steps live in the companion guide.

Photos are only the customer's before image and renders the pipeline actually
produced. Each room photo is placed with contain: its own aspect ratio and
field of view, never cover-cropped into a wide fixed slot. When several room
photos were required, the hero is the first complete after and each remaining
after is a full frame. A missing after stays empty — it is not a crop of
another angle. Detail crops are extras for a single organized photo only.
The room plan is a zone diagram, not a measured drawing.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from blueprint_consistency import prepare_deliverable, safety_guidance
from pdf_generator import plan_title, space_label
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
    for item in (deliverable.get("shopping_list") or [])[:6]:
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


def topdown_layout(deliverable: Dict[str, Any], *, organized: bool, space_theme: bool = False) -> Dict[str, Any]:
    """Practical approximate plan: furniture, window, door, circulation.

    This is a diagram, not a generated floor-plan photo and not a measured drawing.
    """
    zones = _zone_labels(deliverable)
    furniture: List[str] = []
    circulation = "CLEAR PATH"
    for zone in zones:
        label = _role_label(zone)
        if label == "CLEAR PATH":
            circulation = "CLEAR PATH"
            continue
        if label not in furniture:
            furniture.append(label)
    if not furniture:
        furniture = ["DAILY", "STORAGE", "COMFORT"]
    furniture = furniture[:3]
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
    return {
        "window": "WINDOW",
        "door": "DOOR",
        "furniture": furniture,
        "circulation": circulation,
        "approximate": True,
        "matches_after": organized,
        "space_theme": space_theme,
        "caption": caption,
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


def _pair_slots(pairs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One slot per required source. A missing after stays empty — never a crop."""
    slots = []
    for index, pair in enumerate(pairs):
        label = str(pair.get("label") or f"SOURCE_{index + 1:02d}")
        after_label = str(pair.get("after_label") or f"AFTER_{index + 1:02d}")
        img = _open_image(pair.get("after"))
        if img is None:
            slots.append(
                {
                    "image": None,
                    "caption": f"{label} — after missing",
                    "source": label,
                    "missing": True,
                }
            )
        else:
            slots.append(
                {
                    "image": img,
                    "caption": f"{label} → {after_label}",
                    "source": label,
                    "missing": False,
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
        return _pair_slots(pairs)

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
        hero_label = "AFTER — ORGANIZED VIEW"
    elif before or kind == "original":
        hero_mode = "before_only"
        hero_label = "YOUR PHOTO — ORGANIZED VIEW UNAVAILABLE"
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
        # One strong hero (AFTER_01) + remaining full-room afters as supporting views.
        hero_mode = "hero_plus_afters"
        hero_label = "AFTER — ORGANIZED VIEW" if complete else "INCOMPLETE — MISSING SOURCE AFTER"
        claims_organized = complete
    else:
        claims_organized = hero_mode in {"before_after", "after_only"}
    return {
        "deliverable": doc,
        "images": images,
        "headline": f"{_possessive(_first_name(lead))} {space_label(lead.get('space_type'))}",
        "plan_title": plan_title(lead.get("space_type")),
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
        ),
        "safety": safety_guidance(lead, doc),
        "placeholder_label": HERO_PLACEHOLDER_LABEL,
        "placeholder_sub": HERO_PLACEHOLDER_SUB,
    }


def _text(draw: ImageDraw.ImageDraw, xy, text, font, fill, max_width=None) -> None:
    draw.text(xy, text, font=font, fill=fill)


def _caption_bar(base: Image.Image, box: Tuple[int, int, int, int], label: str) -> None:
    x0, y0, x1, y1 = box
    bar_h = 34 if (y1 - y0) >= 80 else 22
    overlay = Image.new("RGBA", (max(1, x1 - x0), bar_h), (31, 61, 44, 214))
    base.paste(overlay, (x0, y1 - bar_h), overlay)
    draw = ImageDraw.Draw(base)
    size = 14 if bar_h >= 30 else 11
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
        label = str(pair.get("label") or f"SOURCE_{index + 1:02d}")
        after_label = str(pair.get("after_label") or f"AFTER_{index + 1:02d}")
        after = _open_image(pair.get("after"))
        if after is None:
            _empty_panel(base, cell, f"{label} — after missing", "Not filled from another angle.")
        else:
            _photo_or_empty(base, after, cell, f"{label} → {after_label}", f"{label} — after missing", "Not filled from another angle.")


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


def _draw_plan(base: Image.Image, box: Tuple[int, int, int, int], topdown: Dict[str, Any]) -> None:
    """Furniture, window, door, and a clear path. Approximate — no dimensions."""
    draw = ImageDraw.Draw(base)
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, y1 = box
    draw.text((x0 + 16, y0 + 12), "ROOM PLAN", font=_font("sans-bold", 14), fill=GREEN)
    draw.text((x0 + 118, y0 + 14), "APPROXIMATE", font=_font("sans", 12), fill=MUTED)
    if topdown.get("space_theme"):
        draw.text((x0 + 220, y0 + 14), "PLANETS · MOON · ROCKETS", font=_font("sans-bold", 11), fill=CLAY)
        _draw_space_glyphs(draw, x1 - 78, y0 + 10)
    room = (x0 + 18, y0 + 46, x1 - 18, y1 - 52)
    draw.rounded_rectangle(room, radius=10, outline=GREEN, width=3)
    rx0, ry0, rx1, ry1 = room
    win_w = max(80, (rx1 - rx0) // 3)
    win_x = rx0 + (rx1 - rx0 - win_w) // 2
    draw.line((win_x, ry0 + 10, win_x + win_w, ry0 + 10), fill=CLAY, width=4)
    draw.line((win_x, ry0 + 16, win_x + win_w, ry0 + 16), fill=CLAY, width=2)
    window_label = str(topdown.get("window") or "WINDOW")
    draw.text((win_x + 8, ry0 + 22), window_label, font=_font("sans-bold", 12), fill=CLAY)
    door_top = ry0 + 36
    draw.rectangle((rx0 - 1, door_top, rx0 + 10, door_top + 54), fill=PAPER)
    draw.text((rx0 + 16, door_top + 16), str(topdown.get("door") or "DOOR"), font=_font("sans-bold", 12), fill=GREEN)
    furniture = list(topdown.get("furniture") or [])[:3]
    slots = (
        (0.40, 0.18, 0.92, 0.48),
        (0.08, 0.46, 0.48, 0.78),
        (0.52, 0.50, 0.92, 0.80),
    )
    rw, rh = rx1 - rx0, ry1 - ry0
    for label, (l, t, r, b) in zip(furniture, slots):
        pill = (rx0 + int(l * rw), ry0 + int(t * rh), rx0 + int(r * rw), ry0 + int(b * rh))
        draw.rounded_rectangle(pill, radius=10, fill=GREEN_SOFT, outline=GREEN, width=2)
        lines = _fit(draw, str(label), _font("sans-bold", 14), pill[2] - pill[0] - 16, 2)
        ty = pill[1] + max(8, (pill[3] - pill[1] - 16 * len(lines)) // 2)
        for line in lines:
            draw.text((pill[0] + 10, ty), line, font=_font("sans-bold", 14), fill=GREEN)
            ty += 16
    path = str(topdown.get("circulation") or "CLEAR PATH")
    arrow_y = ry1 - 22
    draw.line((rx0 + 24, arrow_y, rx1 - 28, arrow_y), fill=CLAY, width=3)
    draw.polygon([(rx1 - 22, arrow_y), (rx1 - 34, arrow_y - 6), (rx1 - 34, arrow_y + 6)], fill=CLAY)
    draw.text((rx0 + 28, arrow_y - 18), path, font=_font("sans-bold", 11), fill=CLAY)
    caption = str(topdown.get("caption") or "Not a measured floor plan.")
    fitted = _fit(draw, caption, _font("sans", 11), x1 - x0 - 32, 2)
    ty = y1 - 36
    for line in fitted:
        draw.text((x0 + 16, ty), line, font=_font("sans", 11), fill=MUTED)
        ty += 13


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


def board_layout(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Shared portrait boxes so the PNG and the tests describe the same frames.

    Room-photo frames follow each file's aspect ratio inside a max box. They
    are not stretched into one wide hero or a row of short 16:9 cells.
    """
    width, height = PORTRAIT_W, PORTRAIT_H
    margin = 40
    content_w = width - 2 * margin
    images = spec.get("images") or {}
    pairs = _source_pairs(images)
    multi = spec.get("hero_mode") == "hero_plus_afters" and len(pairs) >= 2
    rest = pairs[1:] if multi else []

    header = (margin, 24, width - margin, 214)
    footer = (margin, height - 54, width - margin, height - 22)
    y_start = header[3] + 16
    bottom = footer[1] - 12
    outcome_h = 86
    palette_h = 128
    roadmap_h = 168
    changes_min = 156
    plan_min = 176
    gap_after_hero = 14
    gap_after_row = 14 if rest else 0
    gap_after_outcome = 12
    section_gap = 10
    text_fixed = outcome_h + changes_min + plan_min + palette_h + roadmap_h
    gaps = gap_after_hero + gap_after_row + gap_after_outcome + section_gap * 3
    photo_max = max(240, bottom - y_start - text_fixed - gaps)

    if rest:
        hero_max_h = min(int(photo_max * 0.58), photo_max - gap_after_row - 150)
        hero_max_h = max(200, hero_max_h)
    else:
        hero_max_h = photo_max
    hero_w, hero_h = _fitted_frame(_hero_aspect(spec), content_w, hero_max_h, missing_h=420)
    y = y_start
    hx = margin + max(0, (content_w - hero_w) // 2)
    hero = (hx, y, hx + hero_w, y + hero_h)
    y = hero[3] + gap_after_hero

    sources: List[Tuple[int, int, int, int]] = []
    if rest:
        row_max_h = max(140, photo_max - hero_h - gap_after_row)
        count = len(rest)
        gap = 12
        col_w = max(1, (content_w - gap * (count - 1)) // count)
        fitted: List[Tuple[int, int]] = []
        for pair in rest:
            aspect = _image_aspect(pair.get("after"))
            if aspect is None:
                fitted.append((col_w, min(row_max_h, 200)))
            else:
                fitted.append(frame_size(aspect, col_w, row_max_h))
        row_h = max(item[1] for item in fitted)
        for index, (fw, fh) in enumerate(fitted):
            col_x = margin + index * (col_w + gap)
            x = col_x + max(0, (col_w - fw) // 2)
            y_img = y + max(0, (row_h - fh) // 2)
            sources.append((x, y_img, x + fw, y_img + fh))
        y += row_h + gap_after_row

    outcome = (margin, y, width - margin, y + outcome_h)
    y = outcome[3] + gap_after_outcome
    palette_top = bottom - roadmap_h - section_gap - palette_h
    roadmap_top = bottom - roadmap_h
    middle_bottom = palette_top - section_gap
    middle = max(0, middle_bottom - y)
    if middle <= section_gap + 2:
        changes_h = 1
        plan_h = 1
    else:
        usable = middle - section_gap
        changes_h = max(1, int(usable * 0.48))
        plan_h = max(1, usable - changes_h)
    changes = (margin, y, width - margin, y + changes_h)
    y = changes[3] + section_gap
    plan = (margin, y, width - margin, y + plan_h)
    palette = (margin, palette_top, width - margin, palette_top + palette_h)
    roadmap = (margin, roadmap_top, width - margin, roadmap_top + roadmap_h)
    return {
        "size": (width, height),
        "header": header,
        "hero": hero,
        "sources": sources,
        "outcome": outcome,
        "changes": changes,
        "plan": plan,
        "palette": palette,
        "roadmap": roadmap,
        "footer": footer,
        "multi": multi,
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

    headline = _fit(draw, spec.get("headline") or "Your space", _font("serif-bold", 34), x1 - x0, 1)
    draw.text((x0, y0 + 92), headline[0] if headline else "Your space", font=_font("serif-bold", 34), fill=INK)
    brand = _fit(draw, BRAND_LINE, _font("sans-bold", 12), x1 - x0, 1)
    draw.text((x0, y0 + 138), brand[0] if brand else BRAND_LINE, font=_font("sans-bold", 12), fill=GREEN)
    personal = spec.get("tagline") or ""
    if spec.get("theme_line"):
        personal = f"{personal}   {spec['theme_line']}".strip()
    fitted = _fit(draw, personal, _font("sans", 13), x1 - x0, 1)
    if fitted:
        draw.text((x0, y0 + 160), fitted[0], font=_font("sans", 13), fill=MUTED)
    draw.rectangle((x0, y0 + 184, x1, y0 + 187), fill=GREEN)


def _draw_outcome(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], text: str) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, _y1 = box
    draw.text((x0 + 16, y0 + 12), "THE OUTCOME", font=_font("sans-bold", 12), fill=GREEN)
    lines = _fit(draw, text, _font("serif-italic", 18), x1 - x0 - 32, 2)
    y = y0 + 36
    for line in lines:
        draw.text((x0 + 16, y), line, font=_font("serif-italic", 18), fill=INK)
        y += 24


def _draw_changes(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], moves: Sequence[Dict[str, str]]) -> None:
    x0, y0, x1, y1 = box
    _rounded(draw, box, 16, CARD)
    draw.text((x0 + 16, y0 + 12), "WHAT'S NEW & WHY", font=_font("sans-bold", 13), fill=GREEN)
    items = list(moves)[:4]
    if not items:
        draw.text((x0 + 16, y0 + 40), "The companion guide lists each change.", font=_font("sans", 14), fill=MUTED)
        return
    cols = 2 if len(items) > 1 else 1
    rows = (len(items) + cols - 1) // cols
    gap_x, gap_y = 10, 8
    inner_top = y0 + 40
    cell_w = (x1 - x0 - 32 - gap_x * (cols - 1)) // cols
    cell_h = max(36, (y1 - inner_top - 12 - gap_y * (rows - 1)) // rows)
    for index, move in enumerate(items):
        col, row = index % cols, index // cols
        cx = x0 + 16 + col * (cell_w + gap_x)
        cy = inner_top + row * (cell_h + gap_y)
        draw.ellipse((cx, cy + 2, cx + 22, cy + 24), outline=CLAY, width=2)
        num = str(index + 1)
        draw.text((cx + 7, cy + 4), num, font=_font("sans-bold", 12), fill=CLAY)
        title = _fit(draw, move.get("title") or "", _font("sans-bold", 12), cell_w - 32, 1)
        draw.text((cx + 28, cy + 4), title[0] if title else "", font=_font("sans-bold", 12), fill=INK)
        body = _fit(draw, move.get("body") or "", _font("sans", 13), cell_w - 8, 3)
        ty = cy + 30
        for line in body:
            if ty > cy + cell_h - 4:
                break
            draw.text((cx, ty), line, font=_font("sans", 13), fill=MUTED)
            ty += 16


def _draw_palette_row(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], swatches: Sequence[Dict[str, str]]) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, _y1 = box
    draw.text((x0 + 16, y0 + 12), "PALETTE & MATERIALS", font=_font("sans-bold", 13), fill=GREEN)
    items = list(swatches)[:5] or [{"name": "Cream", "hex": "#F3EEE6", "note": "Textile"}]
    gap = 10
    avail = x1 - x0 - 32
    sw = min(96, (avail - gap * (len(items) - 1)) // max(1, len(items)))
    for index, swatch in enumerate(items):
        x = x0 + 16 + index * (sw + gap)
        y = y0 + 40
        draw.rounded_rectangle((x, y, x + sw, y + 36), radius=8, fill=_rgb(swatch.get("hex") or "#C5C8C6"))
        name = _fit(draw, swatch.get("name") or "", _font("sans", 12), sw + 4, 1)
        draw.text((x, y + 42), name[0] if name else "", font=_font("sans", 12), fill=INK)
        note = _fit(draw, swatch.get("note") or "", _font("sans", 11), sw + 4, 1)
        if note:
            draw.text((x, y + 58), note[0], font=_font("sans", 11), fill=MUTED)


def _draw_roadmap_row(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], steps: Sequence[Dict[str, str]], budget: str) -> None:
    _rounded(draw, box, 16, CARD)
    x0, y0, x1, _y1 = box
    draw.text((x0 + 16, y0 + 12), "ROADMAP", font=_font("sans-bold", 13), fill=GREEN)
    label = budget or "—"
    font = _font("serif-bold", 22)
    tw = draw.textlength(label, font=font)
    draw.text((x1 - 16 - tw, y0 + 8), label, font=font, fill=GREEN)
    hint = _font("sans", 11)
    hw = draw.textlength("LIST TOTAL", font=hint)
    draw.text((x1 - 16 - hw, y0 + 32), "LIST TOTAL", font=hint, fill=MUTED)
    for index, step in enumerate(list(steps)[:3]):
        y = y0 + 52 + index * 34
        draw.ellipse((x0 + 16, y, x0 + 36, y + 20), fill=GREEN)
        draw.text((x0 + 22, y + 2), str(index + 1), font=_font("sans-bold", 12), fill=WHITE)
        title = step.get("title") or ""
        draw.text((x0 + 44, y), title, font=_font("sans-bold", 13), fill=INK)
        body = _fit(draw, step.get("body") or "", _font("sans", 12), x1 - x0 - 70, 1)
        if body:
            draw.text((x0 + 44, y + 16), body[0], font=_font("sans", 12), fill=MUTED)


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
        label = f"{pair.get('label') or 'SOURCE_01'} → {pair.get('after_label') or 'AFTER_01'}"
        return hero_after, label, "Organized view unavailable", "We do not invent an after photo."
    if spec["hero_mode"] in {"before_after", "after_only"}:
        return after, "AFTER — ORGANIZED VIEW", "Organized view unavailable", "We do not invent an after photo."
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
    for box, pair in zip(layout["sources"], pairs[1:]):
        label = str(pair.get("label") or "SOURCE")
        after_label = str(pair.get("after_label") or "AFTER")
        after = _open_image(pair.get("after"))
        if after is None:
            _empty_thumb(base, box, f"{label} — after missing", "Not filled from another angle.")
        else:
            _photo_or_empty(base, after, box, f"{label} → {after_label}", f"{label} — after missing", "Not filled from another angle.")

    draw = ImageDraw.Draw(base)
    _draw_outcome(draw, layout["outcome"], spec.get("subtitle") or "")
    _draw_changes(draw, layout["changes"], spec.get("moves") or [])
    _draw_plan(base, layout["plan"], spec["topdown"])
    draw = ImageDraw.Draw(base)
    _draw_palette_row(draw, layout["palette"], spec.get("palette") or [])
    _draw_roadmap_row(draw, layout["roadmap"], spec.get("roadmap") or [], spec.get("budget_display") or "—")
    _draw_board_footer(draw, layout["footer"])

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


