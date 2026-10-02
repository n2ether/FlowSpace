"""Primary visual FlowSpace image board.

One landscape PNG per Blueprint. The companion PDF carries the long form.
Photos are only the customer's before image and renders the pipeline actually
produced. Detail panels are crops of that organized view, or extra view slots
when those bytes exist. The room plan is a zone diagram, not a measured drawing.

Layout follows Camila's board hierarchy (hero, supporting views, approximate
plan, what's-new callouts, palette, product references, roadmap, budget)
without copying a specific nursery design.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from blueprint_consistency import prepare_deliverable, safety_guidance
from pdf_generator import plan_title, space_label
from pdf_images import (
    HERO_PLACEHOLDER_LABEL,
    HERO_PLACEHOLDER_SUB,
    coerce_image_bytes,
    normalize_pdf_images,
)

W, H = 2600, 1240

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


def _cover(img: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / img.width, height / img.height)
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


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


def _detail_slots(images: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Real extra views when the pipeline made them, else crops of the organized after.

    Captions name the focal point the prompt asked for. Crops stay labeled as
    details of the organized view — never a fake new angle, and never an extra
    view when the after was discarded.
    """
    from space_rails import supporting_view_caption

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
    details = _detail_slots(images, lead)
    themed = is_space_theme(lead, doc)
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
        "claims_organized_photo": hero_mode in {"before_after", "after_only"},
        "detail_captions": [slot["caption"] for slot in details],
        "detail_sources": [slot["source"] for slot in details],
        "space_theme": themed,
        "theme_line": "PLANETS · MOON · ROCKETS · ASTRONAUTS" if themed else "",
        "hero_before_overlay": False,
        "topdown": topdown_layout(
            doc,
            organized=hero_mode in {"before_after", "after_only"},
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
    bar_h = 34
    overlay = Image.new("RGBA", (x1 - x0, bar_h), (31, 61, 44, 214))
    base.paste(overlay, (x0, y1 - bar_h), overlay)
    draw = ImageDraw.Draw(base)
    draw.text((x0 + 12, y1 - bar_h + 8), label, font=_font("sans-bold", 14), fill=WHITE)


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


def _photo_or_empty(base: Image.Image, img: Optional[Image.Image], box: Tuple[int, int, int, int], label: str, empty_title: str, empty_sub: str) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if img is None:
        _empty_panel(base, box, empty_title, empty_sub)
        return
    covered = _cover(img, w, h)
    _paste_round(base, covered, (x0, y0), 16)
    _caption_bar(base, box, label)


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


def build_image_board(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Any],
) -> bytes:
    """Render the primary visual board as a PNG."""
    spec = board_spec(lead, deliverable, images)
    imgs = spec["images"]
    before = _open_image(imgs.get("before"))
    after = _open_image(imgs.get("after"))
    if spec["hero_mode"] == "before_only" and before is None:
        before = _open_image(imgs.get("front_view"))
    if spec["hero_mode"] == "after_only" and after is None:
        after = _open_image(imgs.get("front_view"))

    base = Image.new("RGBA", (W, H), PAPER + (255,))
    draw = ImageDraw.Draw(base)

    # Header
    draw.text((36, 22), "FLOWSPACE", font=_font("sans-bold", 14), fill=GREEN)
    draw.text((150, 24), "IMAGE BOARD", font=_font("sans", 13), fill=MUTED)
    headline = spec["headline"]
    draw.text((36, 46), headline, font=_font("serif-bold", 40), fill=INK)
    draw.text((36, 96), spec["subtitle"], font=_font("serif-italic", 20), fill=MUTED)
    tag = spec["tagline"]
    tag_font = _font("sans-bold", 13)
    tag_w = draw.textlength(tag, font=tag_font)
    draw.text((W - 36 - tag_w, 58), tag, font=tag_font, fill=GREEN)
    if spec.get("theme_line"):
        theme_font = _font("sans-bold", 12)
        theme = spec["theme_line"]
        theme_w = draw.textlength(theme, font=theme_font)
        draw.text((W - 36 - theme_w, 80), theme, font=theme_font, fill=CLAY)
    draw.rectangle((36, 128, W - 36, 131), fill=GREEN)

    main_top = 148
    main_h = 800
    hero = (36, main_top, 36 + 1240, main_top + main_h)
    mid = (1292, main_top, 1292 + 560, main_top + main_h)
    right = (1868, main_top, W - 36, main_top + main_h)

    gap = 12
    if spec["hero_mode"] == "before_after":
        # The hero is the organized after only. A small before chip used to sit
        # in the lower-left and put the cluttered original (teddy, loose cushions)
        # back on top of the render. The companion PDF keeps the labeled before.
        _photo_or_empty(
            base,
            after,
            hero,
            "AFTER — ORGANIZED VIEW",
            "Organized view unavailable",
            "We do not invent an after photo.",
        )
    elif spec["hero_mode"] == "after_only":
        _photo_or_empty(base, after, hero, "AFTER — ORGANIZED VIEW", "Organized view unavailable", "We do not invent an after photo.")
    elif spec["hero_mode"] == "before_only":
        _photo_or_empty(base, before, hero, spec["hero_label"], spec["hero_label"], "We do not invent an organized after.")
    else:
        _empty_panel(base, hero, HERO_PLACEHOLDER_LABEL, HERO_PLACEHOLDER_SUB)

    details = _detail_slots(imgs, lead)
    mx0, my0, mx1, my1 = mid
    if details:
        slot_h = (my1 - my0 - gap * (len(details) - 1)) // len(details)
        for i, slot in enumerate(details):
            top = my0 + i * (slot_h + gap)
            _photo_or_empty(base, slot["image"], (mx0, top, mx1, top + slot_h), slot["caption"], slot["caption"], "")
    else:
        _empty_panel(base, mid, "Additional views", "They appear when an organized photo exists. We do not invent them.")

    rx0, ry0, rx1, ry1 = right
    plan_h = 430
    _draw_plan(base, (rx0, ry0, rx1, ry0 + plan_h), spec["topdown"])
    draw = ImageDraw.Draw(base)
    _draw_moves(draw, (rx0, ry0 + plan_h + 16, rx1, ry1), spec["moves"])

    # Bottom strip
    by = main_top + main_h + 18
    draw = ImageDraw.Draw(base)
    prod_box = (36, by, 980, H - 36)
    pal_box = (1000, by, 1580, H - 36)
    road_box = (1600, by, W - 36, H - 36)
    _rounded(draw, prod_box, 16, CARD)
    _rounded(draw, pal_box, 16, CARD)
    _rounded(draw, road_box, 16, CARD)

    draw.text((prod_box[0] + 16, prod_box[1] + 12), "PRODUCT REFERENCES", font=_font("sans-bold", 13), fill=GREEN)
    draw.text((prod_box[0] + 16, prod_box[1] + 32), "From your shopping list. These are not catalog photos.", font=_font("sans", 12), fill=MUTED)
    products = spec["products"] or [{"name": "Shopping list is in the companion guide.", "price": ""}]
    for i, product in enumerate(products[:4]):
        y = prod_box[1] + 58 + i * 36
        swatch = spec["palette"][i % len(spec["palette"])]["hex"]
        draw.rounded_rectangle((prod_box[0] + 16, y, prod_box[0] + 40, y + 24), radius=4, fill=_rgb(swatch))
        name_lines = _fit(draw, product["name"], _font("sans", 15), 760, 1)
        draw.text((prod_box[0] + 50, y + 2), name_lines[0] if name_lines else product["name"], font=_font("sans", 15), fill=INK)
        if product.get("price"):
            pw = draw.textlength(product["price"], font=_font("sans-bold", 15))
            draw.text((prod_box[2] - 16 - pw, y + 2), product["price"], font=_font("sans-bold", 15), fill=GREEN)

    draw.text((pal_box[0] + 16, pal_box[1] + 12), "PALETTE & MATERIALS", font=_font("sans-bold", 13), fill=GREEN)
    swatch_w = 80
    for i, swatch in enumerate(spec["palette"][:5]):
        x = pal_box[0] + 16 + (i % 5) * (swatch_w + 12)
        y = pal_box[1] + 48
        draw.rounded_rectangle((x, y, x + swatch_w, y + 64), radius=10, fill=_rgb(swatch["hex"]))
        for li, line in enumerate(_fit(draw, swatch["name"], _font("sans", 12), swatch_w + 8, 2)):
            draw.text((x, y + 72 + li * 14), line, font=_font("sans", 12), fill=INK)
        draw.text((x, y + 102), swatch.get("note") or "", font=_font("sans", 11), fill=MUTED)

    draw.text((road_box[0] + 16, road_box[1] + 12), "ROADMAP", font=_font("sans-bold", 13), fill=GREEN)
    budget = spec["budget_display"]
    budget_font = _font("serif-bold", 28)
    bw = draw.textlength(budget, font=budget_font)
    draw.text((road_box[2] - 16 - bw, road_box[1] + 8), budget, font=budget_font, fill=GREEN)
    label = "LIST TOTAL"
    lw = draw.textlength(label, font=_font("sans-bold", 11))
    draw.text((road_box[2] - 16 - lw, road_box[1] + 40), label, font=_font("sans-bold", 11), fill=MUTED)
    for i, step in enumerate(spec["roadmap"]):
        y = road_box[1] + 62 + i * 48
        draw.ellipse((road_box[0] + 16, y, road_box[0] + 38, y + 22), fill=GREEN)
        draw.text((road_box[0] + 23, y + 3), str(i + 1), font=_font("sans-bold", 12), fill=WHITE)
        draw.text((road_box[0] + 46, y), step["title"], font=_font("sans-bold", 13), fill=INK)
        body = _fit(draw, step["body"], _font("sans", 12), road_box[2] - road_box[0] - 70, 2)
        draw.text((road_box[0] + 46, y + 18), " ".join(body), font=_font("sans", 12), fill=MUTED)

    # Priorities sit in the palette card's lower area if there is room; keep them on the footer line.
    priority = ""
    if spec["priorities"]:
        bits = []
        for item in spec["priorities"][:3]:
            fitted = _fit(draw, item, _font("sans", 12), 280, 1)
            if fitted:
                bits.append(fitted[0].rstrip("."))
        priority = "PRIORITIES  " + "   ·   ".join(bits)
    draw.text((36, H - 28), priority or "PRIORITIES  are listed in full in the companion guide.", font=_font("sans", 12), fill=MUTED)
    foot = "Windows and proportions stay ~95% true to your photo. Paint is not applied unless you asked."
    fw = draw.textlength(foot, font=_font("sans", 12))
    draw.text((W - 36 - fw, H - 28), foot, font=_font("sans", 12), fill=MUTED)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
