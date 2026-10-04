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
The room flow is a top-down sketch of this room — window, door, and the
furniture already in it — not a stack of bars and not a measured drawing.
Customer pixels never carry SOURCE_/AFTER_ codes or a lead id. Those stay
on the review contact sheet.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from blueprint_consistency import nightly_instruction, prepare_deliverable, safety_guidance
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


_ANCHOR_MOVE = re.compile(r"\b(anchor|anti-tip|anti tip|tip-over|tip over)\b", re.I)
_CLIMATE_MOVE = re.compile(r"\b(thermal|draft|january|curtain|insulation|warmth|winter|warm the)\b", re.I)
_PATH_MOVE = re.compile(r"\b(floor path|clear path|walking path|circulation)\b", re.I)
_KEEP_MOVE = re.compile(
    r"\b(preserve|existing wall|no new wall|space theme|drawer|one step|routine|simplify)\b",
    re.I,
)
_WARNING_MOVE = re.compile(r"\b(do not|don't|never|no loose|no portable|teddy|heater)\b", re.I)
