"""FlowSpace Design Plan board — the primary visual of every package.

One portrait PNG in the approved light editorial layout (``design_plan_standards``):
the FlowSpace lockup and a DRAFT / REVIEW pill until release, a small
"FlowSpace Design Plan" label over the project name, an inviting hero with up to
three more views, Project Story, What Changed & Why, The Zones, a materials +
shopping snapshot, a small warm-neutral palette, a three-step roadmap, and a
short Why It Works close over the tagline band.

Text, icons, and the mark are drawn here in Montserrat. The image model never
draws the board or its type. The Room Flow map is its own attachment
(``room_flow``) and is not drawn on this board. Safety, climate, maintenance,
styling rules, and the full designer assessment live in the Companion Guide.

Photos are only the customer's before image and renders the pipeline actually
produced. Each frame is filled from the photo it names, so a view is never a
crop of another angle, and a missing after stays an empty, labelled panel.
Every full, uncropped before and after is in the Companion Guide. Customer
pixels never carry SOURCE_/AFTER_ codes or a lead id.
"""
from __future__ import annotations

import io
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from blueprint_consistency import (
    SHOPPING_DISCLAIMER,
    nightly_instruction,
    prepare_deliverable,
    reference_total_line,
    safety_guidance,
)
from copy_shape import complete_clip, heading
from design_plan_standards import (
    BOARD_WORDS,
    BRAND_NAME,
    BRAND_TINTS,
    COLOR_PREF_SWATCHES,
    DEFAULT_ROADMAP,
    DEFAULT_STORY,
    DEFAULT_SUBTITLE,
    DESIGN_PLAN_FOOTER,
    DESIGN_PLAN_FOOTER_REVIEW,
    DESIGN_PLAN_LABEL,
    KEPT_LABEL,
    NURSERY_CHANGE_ORDER,
    NURSERY_CHANGES,
    NURSERY_ROADMAP,
    NURSERY_ROADMAP_NO_CLIMATE,
    NURSERY_ZONES,
    PALETTE_BLURB,
    PALETTE_BLURB_THEMED,
    PALETTE_SIZE,
    REVIEW_NOTE,
    REVIEW_PILL,
    ROADMAP_NOTE,
    SECTION_TITLES,
    SNAPSHOT_MAX_ITEMS,
    SNAPSHOT_TOTAL_LABEL,
    STORY_HEADLINE,
    TAGLINE,
    WARM_NEUTRAL_PALETTE,
    WHY_IT_WORKS_BODY,
    WHY_IT_WORKS_HEADLINE,
    ZONES_NOTE,
    BRAND_CHAR,
    BRAND_GREEN,
    BRAND_GREIGE,
    BRAND_OFF,
    BRAND_SAGE,
    hex_rgb,
    is_released,
    montserrat_path,
)
from pdf_generator import customer_project_title, plan_title, space_label
from room_flow import outline_phrases, record_view_chips, record_view_names, resolve_room_flow
from pdf_images import (
    HERO_PLACEHOLDER_LABEL,
    HERO_PLACEHOLDER_SUB,
    coerce_image_bytes,
    normalize_pdf_images,
)

# The approved board is 1600 × 2540. A long plan may grow the canvas; it never shrinks.
PORTRAIT_W, PORTRAIT_H = 1600, 2540
W, H = PORTRAIT_W, PORTRAIT_H
PAD_X = 72
PAD_TOP = 36
CONTENT_W = W - 2 * PAD_X
# Drawn at 2× and downsampled, so lines, circles, and type are smooth.
SUPERSAMPLE = 2

GREEN = hex_rgb(BRAND_GREEN)
SAGE = hex_rgb(BRAND_SAGE)
OFF = hex_rgb(BRAND_OFF)
GREIGE = hex_rgb(BRAND_GREIGE)
CHAR = hex_rgb(BRAND_CHAR)
SAGE_L = hex_rgb(BRAND_TINTS["sage_light"])
SAGE_LINE = hex_rgb(BRAND_TINTS["sage_line"])
GREIGE_L = hex_rgb(BRAND_TINTS["greige_light"])
LINE = hex_rgb(BRAND_TINTS["line"])
MUTED = hex_rgb(BRAND_TINTS["muted"])
BODY = hex_rgb(BRAND_TINTS["body"])
WHITE = (255, 255, 255)
SOFT_INK = (63, 66, 63)
CHANGE_INK = (79, 84, 80)
WHY_RING = (207, 220, 210)
CHIP_RING = (232, 232, 229)
FOOT_SOFT = tuple(int(255 * 0.85 + c * 0.15) for c in GREEN)
CHIP_FILL = (246, 247, 244)

# Kept for callers that still read the old names.
PAPER = OFF
INK = CHAR

_LIBERATION = "/usr/share/fonts/truetype/liberation"
_FONT_PATHS = {
    "light": (montserrat_path("light"), f"{_LIBERATION}/LiberationSans-Regular.ttf"),
    "regular": (montserrat_path("regular"), f"{_LIBERATION}/LiberationSans-Regular.ttf"),
    "medium": (montserrat_path("medium"), f"{_LIBERATION}/LiberationSans-Regular.ttf"),
    "semibold": (montserrat_path("semibold"), f"{_LIBERATION}/LiberationSans-Bold.ttf"),
    "bold": (montserrat_path("bold"), f"{_LIBERATION}/LiberationSans-Bold.ttf"),
}
_fonts: Dict[Tuple[str, int], ImageFont.ImageFont] = {}


def _font(kind: str, size: int) -> ImageFont.ImageFont:
    key = (kind, int(size))
    if key in _fonts:
        return _fonts[key]
    for path in _FONT_PATHS.get(kind, _FONT_PATHS["regular"]):
        try:
            face = ImageFont.truetype(path, size=int(size))
            _fonts[key] = face
            return face
        except OSError:
            continue
    face = ImageFont.load_default()
    _fonts[key] = face
    return face


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _hex(value: str, fallback: str) -> str:
    v = (value or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
        return v.upper()
    return fallback


def _sentence_case(text: str) -> str:
    text = _clean(text)
    if not text:
        return ""
    if text.isupper():
        text = text.lower()
    return text[:1].upper() + text[1:]


# ──────────────────────────── Pen (2× drawing in 1× coordinates) ─────────────────────────────


class _Pen:
    """Draws on a supersampled canvas. Every coordinate and size is a 1× board pixel."""

    def __init__(self, base: Image.Image, scale: int = SUPERSAMPLE):
        self.base = base
        self.s = scale
        self.draw = ImageDraw.Draw(base)

    def _p(self, value: float) -> int:
        return int(round(value * self.s))

    def face(self, kind: str, size: float) -> ImageFont.ImageFont:
        return _font(kind, max(1, int(round(size * self.s))))

    def width(self, text: str, kind: str, size: float, tracking: float = 0.0) -> float:
        face = self.face(kind, size)
        text = str(text or "")
        if not text:
            return 0.0
        if not tracking:
            return self.draw.textlength(text, font=face) / self.s
        total = sum(self.draw.textlength(ch, font=face) for ch in text)
        return (total / self.s) + tracking * size * (len(text) - 1)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        kind: str,
        size: float,
        fill,
        *,
        tracking: float = 0.0,
        align: str = "left",
    ) -> float:
        """Draw one line with its top at ``y``. ``tracking`` is letter spacing in em."""
        text = str(text or "")
        if not text:
            return 0.0
        width = self.width(text, kind, size, tracking)
        if align == "right":
            x = x - width
        elif align == "center":
            x = x - width / 2
        face = self.face(kind, size)
        if not tracking:
            self.draw.text((self._p(x), self._p(y)), text, font=face, fill=fill)
            return width
        cursor = x
        gap = tracking * size
        for ch in text:
            self.draw.text((self._p(cursor), self._p(y)), ch, font=face, fill=fill)
            cursor += self.draw.textlength(ch, font=face) / self.s + gap
        return width

    def wrap(self, text: str, kind: str, size: float, width: float) -> List[str]:
        words = _clean(text).split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if self.width(trial, kind, size) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def fit(self, text: str, kind: str, size: float, width: float, max_lines: int) -> List[str]:
        """Wrap on word boundaries. If it still overflows, end on a whole sentence or phrase."""
        text = _clean(text)
        if not text:
            return []
        lines = self.wrap(text, kind, size, width)
        if len(lines) <= max_lines:
            return lines
        count = len(text.split())
        while count > 1:
            count -= 1
            clipped = complete_clip(text, count)
            lines = self.wrap(clipped, kind, size, width)
            if len(lines) <= max_lines:
                return lines
        return self.wrap(complete_clip(text, 1), kind, size, width)[:max_lines]

    def rrect(self, box, radius: float, fill=None, outline=None, width: float = 0) -> None:
        x0, y0, x1, y1 = box
        self.draw.rounded_rectangle(
            (self._p(x0), self._p(y0), self._p(x1), self._p(y1)),
            radius=self._p(radius),
            fill=fill,
            outline=outline,
            width=self._p(width) if outline is not None and width else 0,
        )

    def rect(self, box, fill) -> None:
        x0, y0, x1, y1 = box
        self.draw.rectangle((self._p(x0), self._p(y0), self._p(x1), self._p(y1)), fill=fill)

    def ellipse(self, box, fill=None, outline=None, width: float = 0) -> None:
        x0, y0, x1, y1 = box
        self.draw.ellipse(
            (self._p(x0), self._p(y0), self._p(x1), self._p(y1)),
            fill=fill,
            outline=outline,
            width=self._p(width) if outline is not None and width else 0,
        )

    def line(self, points: Sequence[Tuple[float, float]], fill, width: float) -> None:
        pts = [(self._p(x), self._p(y)) for x, y in points]
        if len(pts) < 2:
            return
        w = max(1, self._p(width))
        self.draw.line(pts, fill=fill, width=w, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):
            self.draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def arc(self, box, start: float, end: float, fill, width: float) -> None:
        x0, y0, x1, y1 = box
        self.draw.arc(
            (self._p(x0), self._p(y0), self._p(x1), self._p(y1)),
            start=start,
            end=end,
            fill=fill,
            width=max(1, self._p(width)),
        )

    def polygon(self, points, fill=None, outline=None) -> None:
        self.draw.polygon([(self._p(x), self._p(y)) for x, y in points], fill=fill, outline=outline)

    def paste_cover(self, img: Image.Image, box, radius: float, focus: Tuple[float, float] = (0.5, 0.55)) -> None:
        """Fill ``box`` from ``img`` (its own photo only), centred on ``focus``, with rounded corners."""
        x0, y0, x1, y1 = box
        tw, th = max(1, self._p(x1 - x0)), max(1, self._p(y1 - y0))
        fitted = ImageOps.fit(img, (tw, th), method=Image.Resampling.LANCZOS, centering=focus)
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw - 1, th - 1), radius=self._p(radius), fill=255)
        self.base.paste(fitted, (self._p(x0), self._p(y0)), mask)


def _probe() -> _Pen:
    return _Pen(Image.new("RGB", (8, 8)), SUPERSAMPLE)


def _bezier(p0, p1, p2, p3, n: int = 18) -> List[Tuple[float, float]]:
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


# ──────────────────────────── Line icons ─────────────────────────────


def _crescent(cx, cy, r, ox, oy, r2, n: int = 72) -> List[Tuple[float, float]]:
    outer = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        if math.hypot(x - ox, y - oy) >= r2:
            outer.append((a, x, y))
    if not outer:
        return []
    # Rotate so the run of outside points is contiguous.
    gaps = [(outer[(i + 1) % len(outer)][0] - outer[i][0]) % (2 * math.pi) for i in range(len(outer))]
    start = (gaps.index(max(gaps)) + 1) % len(outer)
    ordered = outer[start:] + outer[:start]
    pts = [(x, y) for _a, x, y in ordered]
    a0 = math.atan2(pts[-1][1] - oy, pts[-1][0] - ox)
    a1 = math.atan2(pts[0][1] - oy, pts[0][0] - ox)
    span = (a1 - a0) % (2 * math.pi)
    if span > math.pi:
        span -= 2 * math.pi
    for i in range(1, 24):
        a = a0 + span * i / 24
        pts.append((ox + r2 * math.cos(a), oy + r2 * math.sin(a)))
    pts.append(pts[0])
    return pts


def _zone_icon(pen: _Pen, kind: str, x: float, y: float, size: float = 40, color=GREEN) -> None:
    """Simple line icon in a 48-unit box, drawn at ``size`` px."""
    k = size / 48.0
    w = 2.0 * k * 1.1

    def P(px, py):
        return (x + px * k, y + py * k)

    def L(*pts):
        pen.line([P(*p) for p in pts], color, w)

    if kind == "sleep":
        pen.line([P(px, py) for px, py in _crescent(22, 26, 16, 30, 19, 13)], color, w)
        star = [(36, 9), (37.2, 11.6), (39.8, 12.8), (37.2, 14), (36, 16.6), (34.8, 14), (32.2, 12.8), (34.8, 11.6), (36, 9)]
        L(*star)
    elif kind == "change":
        pen.rrect((x + 8 * k, y + 10 * k, x + 40 * k, y + 40 * k), 2 * k, outline=color, width=w)
        L((8, 20), (40, 20))
        L((8, 30), (40, 30))
        for hy in (15, 25, 35):
            L((21, hy), (27, hy))
        L((12, 40), (12, 43))
        L((36, 40), (36, 43))
    elif kind == "comfort":
        L((14, 28), (14, 14))
        pen.arc((x + 14 * k, y + 9 * k, x + 24 * k, y + 19 * k), 180, 270, color, w)
        L((19, 9), (29, 9))
        pen.arc((x + 24 * k, y + 9 * k, x + 34 * k, y + 19 * k), 270, 360, color, w)
        L((34, 14), (34, 28))
        L((9, 23), (14, 23), (14, 30), (34, 30), (34, 23), (39, 23), (39, 32), (36, 35), (12, 35), (9, 32), (9, 23))
        pen.line([P(*p) for p in _bezier((8, 42), (17, 38), (31, 38), (40, 42))], color, w)
    elif kind == "play":
        L((9, 19), (39, 19), (36, 38), (33, 40.5), (15, 40.5), (12, 38), (9, 19))
        pen.arc((x + 17 * k, y + 10 * k, x + 31 * k, y + 28 * k), 180, 360, color, w)
        L((13, 27), (35, 27))
        L((14, 33), (34, 33))
    elif kind == "storage":
        pen.rrect((x + 8 * k, y + 16 * k, x + 40 * k, y + 40 * k), 2 * k, outline=color, width=w)
        L((6, 10), (42, 10), (42, 16), (6, 16), (6, 10))
        L((20, 24), (28, 24))
    elif kind == "work":
        L((6, 20), (42, 20))
        L((10, 20), (10, 40))
        L((38, 20), (38, 40))
        pen.rrect((x + 24 * k, y + 22 * k, x + 36 * k, y + 32 * k), 1.5 * k, outline=color, width=w)
        L((16, 8), (16, 20))
        L((12, 8), (22, 8))
    else:
        L((24, 8), (40, 20), (40, 40), (8, 40), (8, 20), (24, 8))
        pen.line([P(*p) for p in _bezier((14, 30), (18, 25), (22, 25), (26, 30))], color, w)
        pen.line([P(*p) for p in _bezier((22, 32), (26, 27), (30, 27), (34, 32))], color, w)


def _item_kind(name: str) -> str:
    low = (name or "").lower()
    for kind, words in (
        ("anchor", ("anchor", "anti-tip", "tip kit", "strap")),
        ("curtain", ("curtain", "drape", "panel", "shade", "blind")),
        ("film", ("film", "insulat", "window")),
        ("draft", ("draft", "stopper", "sweep", "door")),
        ("light", ("light", "lamp", "bulb")),
        ("thermo", ("thermometer", "humidity", "hygrometer")),
        ("basket", ("basket", "bin", "tote")),
        ("caddy", ("caddy", "organizer", "hook", "rack", "shelf")),
    ):
        if any(word in low for word in words):
            return kind
    return "box"


def _item_icon(pen: _Pen, kind: str, x: float, y: float, size: float = 20, color=GREEN) -> None:
    """Small line icon in a 24-unit box."""
    k = size / 24.0
    w = 1.6 * k * 1.1

    def P(px, py):
        return (x + px * k, y + py * k)

    def L(*pts):
        pen.line([P(*p) for p in pts], color, w)

    def R(x0, y0, x1, y1, r=2):
        pen.rrect((x + x0 * k, y + y0 * k, x + x1 * k, y + y1 * k), r * k, outline=color, width=w)

    if kind == "anchor":
        L((12, 3), (12, 9))
        L((8, 7), (12, 3), (16, 7))
        R(4, 9, 20, 21)
        L((8, 15), (16, 15))
    elif kind == "curtain":
        L((3, 4), (21, 4))
        L((6, 4), (6, 20))
        L((18, 4), (18, 20))
        pen.line([P(*p) for p in _bezier((6, 20), (7.5, 15), (7.5, 9), (6, 4))], color, w)
        pen.line([P(*p) for p in _bezier((18, 20), (16.5, 15), (16.5, 9), (18, 4))], color, w)
    elif kind == "film":
        R(4, 4, 20, 20)
        L((4, 11), (20, 11))
    elif kind == "draft":
        R(4, 16, 20, 19, 1)
        pen.line([P(*p) for p in _bezier((6, 16), (8, 12), (10, 10), (12, 10))], color, w)
        pen.line([P(*p) for p in _bezier((12, 10), (14, 10), (16, 12), (18, 16))], color, w)
    elif kind == "light":
        pen.ellipse((x + 7 * k, y + 3 * k, x + 17 * k, y + 13 * k), outline=color, width=w)
        L((10, 14), (10, 17), (14, 17), (14, 14))
        L((10, 20), (14, 20))
    elif kind == "thermo":
        R(10, 3, 14, 15, 2)
        pen.ellipse((x + 8 * k, y + 14 * k, x + 16 * k, y + 22 * k), outline=color, width=w)
        L((16, 7), (19, 7))
        L((16, 10), (19, 10))
    elif kind == "basket":
        L((4, 9), (20, 9), (18, 20), (6, 20), (4, 9))
        pen.arc((x + 8 * k, y + 3 * k, x + 16 * k, y + 13 * k), 180, 360, color, w)
        L((6, 14), (18, 14))
    elif kind == "caddy":
        R(4, 4, 20, 20)
        L((4, 11), (20, 11))
        L((9, 15.5), (15, 15.5))
    else:
        R(4, 7, 20, 20)
        L((3, 7), (21, 7))
        L((10, 12), (14, 12))


def _check_icon(pen: _Pen, x: float, y: float, size: float = 26) -> None:
    pen.ellipse((x, y, x + size, y + size), fill=GREEN)
    k = size / 26.0
    ox, oy = x + 6.5 * k, y + 6.5 * k
    s = 13 / 14.0 * k
    pen.line([(ox + 3 * s, oy + 7.5 * s), (ox + 5.6 * s, oy + 10 * s), (ox + 11 * s, oy + 4.5 * s)], WHITE, 2.4 * s)


def _waves_icon(pen: _Pen, x: float, y: float, size: float = 52) -> None:
    k = size / 48.0
    for base in (22, 34):
        pts = _bezier((8, base), (14, base - 6), (20, base - 6), (24, base)) + _bezier(
            (24, base), (28, base + 6), (34, base + 6), (40, base)
        )
        pen.line([(x + px * k, y + py * k) for px, py in pts], GREEN, 2.2 * k)


def _lockup(pen: _Pen, x: float, y: float, height: float = 72) -> float:
    """House mark plus the FlowSpace wordmark. Returns the drawn width."""
    mark = height * 0.78
    top = y + (height - mark) / 2
    k = mark / 48.0
    w = max(1.6, 1.7 * k)

    def P(px, py):
        return (x + px * k, top + py * k)

    pen.line([P(4, 22), P(24, 4), P(44, 22)], MUTED, w)
    pen.line([P(9, 18), P(9, 44), P(39, 44), P(39, 18)], MUTED, w)
    pen.line([P(*p) for p in _bezier((15, 32), (19, 27), (23, 27), (27, 32))], GREEN, w)
    pen.line([P(*p) for p in _bezier((22, 36), (26, 31), (30, 31), (34, 36))], GREEN, w)
    size = height * 0.56
    tx = x + mark + height * 0.18
    pen.text(tx, y + (height - size * 1.2) / 2, BRAND_NAME, "regular", size, CHAR)
    return (tx - x) + pen.width(BRAND_NAME, "regular", size)


# ──────────────────────────── Customer names ─────────────────────────────


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


def customer_view_caption(index: int, lead: Optional[Dict[str, Any]], *, missing: bool = False) -> str:
    """Short customer label for one room photo. Never a SOURCE_/AFTER_ code.

    A lead whose Room Flow record names its views (photo order is per room) uses
    those names. Otherwise the first view is the organized view and the rest are numbered.
    """
    names = record_view_names(lead)
    if 0 <= index < len(names):
        name = names[index]
    elif index <= 0:
        name = "Organized view"
    else:
        name = f"Room view {index + 1}"
    if missing:
        return f"{name} — still coming"
    return name


def board_view_chip(index: int, lead: Optional[Dict[str, Any]], *, missing: bool = False) -> str:
    """The short chip a board frame wears. Falls back to the customer caption."""
    chips = record_view_chips(lead)
    name = chips[index] if 0 <= index < len(chips) else customer_view_caption(index, lead)
    name = name.upper()
    return f"{name} — STILL COMING" if missing else name


def _board_phrase(title: str, body: str, words: int = 8) -> str:
    """One complete sentence or clause for the board. The full sentence stays in the guide."""
    return complete_clip(body, words)


# ──────────────────────────── Plan copy for the board ─────────────────────────────


def _six_drawer(lead: Dict[str, Any], doc: Dict[str, Any], flow: Dict[str, Any]) -> bool:
    from space_rails import mentions_six_drawer

    if any(int(item.get("drawers") or 0) == 6 for item in flow.get("furniture") or [] if isinstance(item, dict)):
        return True
    blob = " ".join([str(lead.get("must_stay") or ""), str(lead.get("goals") or "")])
    for key in ("strategy", "needs"):
        blob += " " + " ".join(str(x) for x in (doc.get(key) or []))
    for zone in doc.get("zones") or []:
        if isinstance(zone, dict):
            blob += " " + str(zone.get("desc") or "")
    return mentions_six_drawer(blob)


def _plan_lines(deliverable: Dict[str, Any]) -> List[str]:
    return [
        _clean(str(x))
        for key in ("strategy", "action_plan", "needs")
        for x in (deliverable.get(key) or [])
        if _clean(str(x))
    ]


_CLIMATE_CUES = re.compile(r"\b(film|insulat|draft|thermal|cold|curtain)", re.I)


def _nursery_moves(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    """Four distinct changes, each a whole heading and a whole sentence."""
    blob = " ".join([str(lead.get("goals") or ""), str(lead.get("biggest_challenge") or ""), *_plan_lines(deliverable)])
    climate = bool(re.search(r"\b(film|insulat)", blob, re.I))
    moves = []
    for key in NURSERY_CHANGE_ORDER:
        title, full, short = NURSERY_CHANGES[key]
        if key == "climate" and not _CLIMATE_CUES.search(blob):
            continue
        body = full if (key != "climate" or climate) else short
        moves.append({"title": title.upper(), "body": body})
    return moves


def _move_title(text: str, index: int) -> str:
    """Short label taken from the sentence itself, so the title matches the body."""
    title = heading(text, max_words=3).upper()
    return title or f"CHANGE {index + 1}"


def _moves(deliverable: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    from space_rails import is_nursery_space

    if is_nursery_space(lead):
        return _nursery_moves(lead or {}, deliverable)
    strategy = [_clean(str(x)) for x in (deliverable.get("strategy") or []) if _clean(str(x))]
    return [
        {"title": _move_title(text, i), "body": complete_clip(text, BOARD_WORDS["change"])}
        for i, text in enumerate(strategy[:4])
    ]


def _roadmap(deliverable: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    from space_rails import is_nursery_space

    if is_nursery_space(lead):
        blob = " ".join([str((lead or {}).get("goals") or ""), *_plan_lines(deliverable)])
        steps = list(NURSERY_ROADMAP)
        if not _CLIMATE_CUES.search(blob):
            steps[1] = NURSERY_ROADMAP_NO_CLIMATE
        return [{"title": title, "body": body} for title, body in steps]
    layers = deliverable.get("blueprint_layers") if isinstance(deliverable.get("blueprint_layers"), dict) else {}
    instruction = layers.get("customer_instruction") if isinstance(layers.get("customer_instruction"), dict) else {}
    steps = [_clean(str(x)) for x in (instruction.get("do_this_week") or deliverable.get("action_plan") or []) if _clean(str(x))]
    while len(steps) < 3:
        steps.append(DEFAULT_ROADMAP[len(steps)])
    return [
        {"title": _sentence_case(heading(steps[i], max_words=3)) or f"Step {i + 1}", "body": complete_clip(steps[i], BOARD_WORDS["roadmap"])}
        for i in range(3)
    ]


_GREETING = re.compile(r"^(?:welcome|hi|hello|hey|dear)\b", re.I)


def _story(lead: Dict[str, Any], doc: Dict[str, Any]) -> str:
    story = _clean(doc.get("project_story"))
    if story:
        return story
    customer = _first_name(lead).lower()
    for key in ("summary", "intro"):
        for sentence in re.split(r"(?<=[.!?])\s+", _clean(doc.get(key))):
            if len(sentence.split()) < 6 or _GREETING.search(sentence) or sentence.endswith("!"):
                continue
            if sentence.lower().startswith(customer + ","):
                sentence = sentence[len(customer) + 1 :].strip()
                sentence = sentence[:1].upper() + sentence[1:]
            return complete_clip(sentence, BOARD_WORDS["story"])
    return DEFAULT_STORY


def _subtitle(deliverable: Dict[str, Any], draw: Any = None) -> str:
    """The Project Story line. Kept under its old name for the phone page."""
    story = _clean(deliverable.get("project_story"))
    if story:
        return story
    summary = _clean(deliverable.get("summary") or deliverable.get("intro"))
    sentence = re.split(r"(?<=[.!?])\s+", summary)[0] if summary else ""
    return sentence or "A calmer refresh of the room you already have."


def _zone_cards(lead: Dict[str, Any], doc: Dict[str, Any], flow: Dict[str, Any]) -> List[Dict[str, str]]:
    """One card per zone: number, title, the piece that anchors it, and its one job."""
    from space_rails import is_nursery_space

    zones = [zone for zone in flow.get("zones") or [] if isinstance(zone, dict)][:4]
    furniture = [item for item in flow.get("furniture") or [] if isinstance(item, dict)]
    if is_nursery_space(lead):
        standard = {zone["id"]: zone for zone in NURSERY_ZONES}
        six = _six_drawer(lead, doc, flow)
        cards = []
        for index, base in enumerate(NURSERY_ZONES):
            obj = base["object"]
            if base["id"] == "change" and six:
                obj = "Six-drawer dresser"
            cards.append({"number": f"{index + 1:02d}", "id": base["id"], "icon": base["id"], "title": base["title"], "object": obj, "job": standard[base["id"]]["job"]})
        return cards
    from room_flow import _zone_style_key

    cards = []
    for index, zone in enumerate(zones):
        zid = str(zone.get("id") or "")
        labels = [_clean(item.get("label")) for item in furniture if str(item.get("zone") or "") == zid and _clean(item.get("label"))]
        obj = " + ".join(labels[:2]).capitalize() if labels else ""
        title = _clean(zone.get("title")) or f"Zone {index + 1}"
        job = complete_clip(_clean(zone.get("job")) or f"One clear home for {title.lower()}.", BOARD_WORDS["zone_job"])
        cards.append(
            {
                "number": str(zone.get("number") or f"{index + 1:02d}"),
                "id": zid,
                "icon": str(zone.get("style") or _zone_style_key(title, index)),
                "title": title,
                "object": obj,
                "job": job,
            }
        )
    return cards


def _palette(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    """A small warm-neutral palette. Customer color preferences swap in for the accents."""
    swatches: List[Dict[str, str]] = []
    hex_color = str(deliverable.get("wall_color_hex") or "")
    name = str(deliverable.get("wall_color_name") or "")
    if hex_color and "keep existing" not in name.lower() and "no paint" not in name.lower():
        swatches.append({"name": name or "Optional paint", "hex": _hex(hex_color, "#CFD7D3"), "note": "Optional paint"})
    base = [{"name": n, "hex": h, "note": "Palette"} for n, h in WARM_NEUTRAL_PALETTE]
    prefs = []
    for pref in lead.get("color_prefs") or []:
        swatch = COLOR_PREF_SWATCHES.get(str(pref))
        if swatch and swatch[1] not in {s["hex"] for s in base}:
            prefs.append({"name": swatch[0], "hex": swatch[1], "note": "Textiles"})
    # Beige and cream stay; a preference replaces an accent from the end.
    for index, swatch in enumerate(prefs[:2]):
        base[len(base) - 1 - index] = swatch
    out: List[Dict[str, str]] = []
    seen = set()
    for swatch in swatches + base:
        if swatch["hex"] not in seen:
            seen.add(swatch["hex"])
            out.append(swatch)
    return out[:PALETTE_SIZE]


def _kept_items(lead: Dict[str, Any], doc: Dict[str, Any], flow: Dict[str, Any], themed: bool) -> List[str]:
    """What stays exactly as it is. Chips, not sentences."""
    from ai_drafter import is_keep_existing_wall
    from space_rails import is_nursery_space

    kept: List[str] = []
    if is_keep_existing_wall(doc):
        kept.append("Original wall color")
    if is_nursery_space(lead):
        blob = " ".join(
            [str(lead.get(k) or "") for k in ("must_stay", "goals", "biggest_challenge")]
            + [str(item.get("kind") or "") for item in flow.get("furniture") or [] if isinstance(item, dict)]
        ).lower()
        if "dresser" in blob or "changing" in blob:
            kept.append("Six-drawer dresser" if _six_drawer(lead, doc, flow) else "Dresser")
        crib, rocker = "crib" in blob, bool(re.search(r"rocker|glider|rocking", blob))
        if crib and rocker:
            kept.append("Crib + rocker")
        elif crib:
            kept.append("Crib")
        elif rocker:
            kept.append("Rocker")
        if themed:
            kept.append("Space-themed art")
        return kept[:4]
    for part in re.split(r",|;|\band\b|\n", str(lead.get("must_stay") or "")):
        item = _clean(part).strip(".")
        if item and len(item.split()) <= 4:
            kept.append(item[:1].upper() + item[1:])
        if len(kept) >= 4:
            break
    return kept[:4]


def _short_item_name(item: Dict[str, Any]) -> str:
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


def _money(value: float) -> str:
    if value and abs(value - round(value)) < 0.01:
        return f"${value:,.0f}"
    return f"${value:,.2f}" if value else "Confirm price"


def _products(deliverable: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        if not name:
            continue
        try:
            qty = float(item.get("qty", 1) or 1)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            qty, price = 1.0, 0.0
        sub = qty * price
        rows.append(
            {
                "name": name,
                "short": _short_item_name(item),
                "price": _money(sub),
                "subtotal": sub,
                "icon": _item_kind(name),
            }
        )
    return rows


def _snapshot(products: Sequence[Dict[str, Any]], total: str) -> Dict[str, Any]:
    shown = list(products[:SNAPSHOT_MAX_ITEMS])
    rest = list(products[SNAPSHOT_MAX_ITEMS:])
    more_total = sum(float(row.get("subtotal") or 0) for row in rest)
    if rest:
        noun = "item" if len(rest) == 1 else "items"
        more = f"Includes {len(rest)} more {noun} ({_money(more_total)}) in the Companion Guide"
    else:
        more = "Full list with links in the Companion Guide"
    return {"items": shown, "more_count": len(rest), "more_line": more, "total": total}


def _zone_labels(deliverable: Dict[str, Any]) -> List[str]:
    labels = []
    for zone in deliverable.get("zones") or []:
        title = _clean(zone.get("title") if isinstance(zone, dict) else zone)
        if title:
            labels.append(title)
    return labels[:4]


def topdown_layout(
    deliverable: Dict[str, Any],
    *,
    organized: bool,
    space_theme: bool = False,
    lead: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Room Flow summary for the phone page. The board itself does not draw the map."""
    flow = resolve_room_flow(lead, deliverable)
    phrases = outline_phrases(flow)
    zones = [zone for zone in flow.get("zones") or [] if isinstance(zone, dict)][:4]
    titles = {str(zone.get("id")): zone for zone in zones}
    places = []
    for item in flow.get("furniture") or []:
        label = _clean(str(item.get("label") or ""))
        if not label:
            continue
        zone = titles.get(str(item.get("zone") or ""), {})
        places.append(
            {
                "id": str(item.get("id") or label.lower()),
                "label": label,
                "zone": str(zone.get("title") or ""),
                "number": str(zone.get("number") or ""),
            }
        )
    if not places:
        places = [
            {"id": str(zone.get("id")), "label": str(zone.get("map_label") or zone.get("title") or ""), "zone": str(zone.get("title") or ""), "number": str(zone.get("number") or "")}
            for zone in zones
        ]
    caption = phrases["board_caption"]
    if space_theme:
        caption = f"{caption} The space theme remains: planets, moon, rockets, and astronauts."
    return {
        "window": "WINDOW",
        "door": "DOOR",
        "circulation": "CLEAR PATH",
        "furniture": [place["label"] for place in places],
        "places": places,
        "legend": [{"number": str(zone.get("number") or ""), "name": str(zone.get("title") or "")} for zone in zones],
        "approximate": True,
        "measured_outline": flow.get("outline_source") == "measured",
        "matches_after": organized,
        "space_theme": space_theme,
        "drawing": "zone_map",
        "caption": caption,
        "board_caption": phrases["board_caption"],
        "room_flow": flow,
    }


# ──────────────────────────── Photos ─────────────────────────────


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


def _source_pairs(images: Dict[str, Any]) -> List[Dict[str, Any]]:
    pairs = images.get("source_pairs") or []
    if not isinstance(pairs, list):
        return []
    return [pair for pair in pairs if isinstance(pair, dict)]


def _view_slots(images: Dict[str, Any], lead: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every room view the board may show, hero first. A missing after stays empty."""
    from space_rails import supporting_view_caption

    pairs = _source_pairs(images)
    if len(pairs) >= 2:
        slots = []
        for index, pair in enumerate(pairs):
            img = _open_image(pair.get("after"))
            slots.append(
                {
                    "image": img,
                    "caption": customer_view_caption(index, lead, missing=img is None),
                    "chip": board_view_chip(index, lead, missing=img is None),
                    "source": str(pair.get("label") or f"SOURCE_{index + 1:02d}"),
                    "missing": img is None,
                }
            )
        return slots
    slots = []
    after = _open_image(images.get("after"))
    before = _open_image(images.get("before"))
    front = _open_image(images.get("front_view"))
    kind = str(images.get("front_view_kind") or "placeholder")
    if after is not None or (front is not None and kind == "organized"):
        slots.append({"image": after or front, "caption": "Organized view", "chip": "ORGANIZED VIEW", "source": "after", "missing": False})
    elif before is not None or (front is not None and kind == "original"):
        slots.append({"image": before or front, "caption": "Your photo", "chip": "YOUR PHOTO", "source": "before", "missing": False})
    if slots and slots[0]["source"] == "after":
        for key in ("view_1", "view_2", "view_3"):
            img = _open_image(images.get(key))
            if img is not None:
                caption = supporting_view_caption(lead, key)
                slots.append({"image": img, "caption": caption, "chip": caption.upper(), "source": key, "missing": False})
    return slots


# ──────────────────────────── Spec ─────────────────────────────


def board_spec(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None, images: Dict[str, Any] | None) -> Dict[str, Any]:
    """All copy and honesty flags for the board. Rendering reads only this."""
    from space_rails import is_space_theme

    lead = lead or {}
    images = normalize_pdf_images(images)
    doc = prepare_deliverable(lead, deliverable)
    flow = resolve_room_flow(lead, {**doc, "room_flow": (deliverable or {}).get("room_flow")})
    slots = _view_slots(images, lead)
    pairs = _source_pairs(images)
    multi = len(pairs) >= 2
    themed = is_space_theme(lead, doc)
    if multi:
        hero_mode = "hero_plus_afters"
        claims_organized = bool(slots) and all(not slot["missing"] for slot in slots)
    elif slots and slots[0]["source"] == "after":
        hero_mode = "before_after" if coerce_image_bytes(images.get("before")) else "after_only"
        claims_organized = True
    elif slots:
        hero_mode = "before_only"
        claims_organized = False
    else:
        hero_mode = "placeholder"
        claims_organized = False
    hero = slots[0] if slots else None
    thumbs = slots[1:4]
    title = customer_project_title(lead, doc) or f"{_possessive(_first_name(lead))} {space_label(lead.get('space_type'))}"
    products = _products(doc)
    total = doc.get("budget_display") or "—"
    released = is_released(deliverable)
    return {
        "deliverable": doc,
        "images": images,
        "released": released,
        "label": DESIGN_PLAN_LABEL,
        "headline": title,
        "plan_title": customer_project_title(lead, doc) or plan_title(lead.get("space_type")),
        "title_sub": _clean(flow.get("subtitle")) or DEFAULT_SUBTITLE,
        "story_headline": _clean(doc.get("story_headline")) or STORY_HEADLINE,
        "story": _story(lead, doc),
        "subtitle": _subtitle(doc),
        "tagline": _tagline(lead),
        "moves": _moves(doc, lead),
        "zone_cards": _zone_cards(lead, doc, flow),
        "reset_title": nightly_instruction(lead, doc)[0],
        "palette": _palette(lead, doc),
        "palette_blurb": PALETTE_BLURB_THEMED if themed else PALETTE_BLURB,
        "kept": _kept_items(lead, doc, flow, themed),
        "products": products,
        "snapshot": _snapshot(products, total),
        "roadmap": _roadmap(doc, lead),
        "why": {"headline": WHY_IT_WORKS_HEADLINE, "body": WHY_IT_WORKS_BODY},
        "zones": _zone_labels(doc),
        "priorities": [_clean(str(x)) for x in (doc.get("needs") or []) if _clean(str(x))][:4],
        "budget_display": total,
        "stated_budget": doc.get("stated_budget") or "",
        "hero_mode": hero_mode,
        "hero_label": hero["caption"] if hero else HERO_PLACEHOLDER_LABEL,
        "hero_chip": hero["chip"] if hero else "",
        "hero_missing": bool(hero and hero["missing"]),
        "claims_organized_photo": claims_organized,
        # Every room view the package carries (with several sources, the hero is the first).
        "detail_captions": [slot["caption"] for slot in (slots if multi else slots[1:])],
        "detail_sources": [slot["source"] for slot in (slots if multi else slots[1:])],
        # The up-to-three frames under the hero.
        "detail_chips": [slot["chip"] for slot in thumbs],
        "space_theme": themed,
        "theme_line": "PLANETS · MOON · ROCKETS · ASTRONAUTS" if themed else "",
        "hero_before_overlay": False,
        "review_pill": "" if released else REVIEW_PILL,
        "review_note": () if released else REVIEW_NOTE,
        "footer_left": TAGLINE.upper(),
        "footer_right": (DESIGN_PLAN_FOOTER if released else DESIGN_PLAN_FOOTER_REVIEW).upper(),
        "draws_room_flow": False,
        "topdown": topdown_layout(doc, organized=claims_organized, space_theme=themed, lead=lead),
        "safety": safety_guidance(lead, doc),
        "placeholder_label": HERO_PLACEHOLDER_LABEL,
        "placeholder_sub": HERO_PLACEHOLDER_SUB,
    }


# ──────────────────────────── Layout ─────────────────────────────

_LH = 1.25


def _label_h() -> float:
    return 16 * _LH


def _story_card_h(pen: _Pen, spec: Dict[str, Any], width: float) -> float:
    inner = width - 48
    head = pen.fit(spec["story_headline"], "semibold", 28, inner, 2)
    body = pen.fit(spec["story"], "regular", 20, inner, 4)
    return 20 + _label_h() + 12 + len(head) * 35 + 10 + len(body) * 31 + 20


def _change_rows(pen: _Pen, moves: Sequence[Dict[str, str]], width: float) -> List[Tuple[List[str], List[str]]]:
    inner = width - 48 - 38
    rows = []
    for move in list(moves)[:4]:
        title = pen.fit(move["title"], "semibold", 18, inner, 2)
        body = pen.fit(move["body"], "regular", 17, inner, 3)
        rows.append((title, body))
    return rows


def _changes_card_h(pen: _Pen, spec: Dict[str, Any], width: float) -> float:
    rows = _change_rows(pen, spec["moves"], width)
    h = sum(max(26, len(t) * 23.4 + 2 + len(b) * 23.8) for t, b in rows) + 9 * max(0, len(rows) - 1)
    return 20 + _label_h() + 12 + h + 20


def _zone_card_parts(pen: _Pen, card: Dict[str, str], width: float):
    inner = width - 44
    title = pen.fit(card["title"], "semibold", 22, inner, 2)
    obj = pen.fit(card["object"].upper(), "medium", 14, inner, 1) if card.get("object") else []
    job = pen.fit(card["job"], "regular", 18, inner, 3)
    return title, obj, job


def _zone_card_h(pen: _Pen, card: Dict[str, str], width: float) -> float:
    title, obj, job = _zone_card_parts(pen, card, width)
    return 20 + 40 + 10 + len(title) * 27 + (4 + 17.5 if obj else 0) + 10 + len(job) * 26 + 22


def _shop_card_h(pen: _Pen, spec: Dict[str, Any], width: float) -> float:
    note = pen.fit(SHOPPING_DISCLAIMER, "regular", 16, width - 48, 2)
    items = spec["snapshot"]["items"]
    more = pen.fit(spec["snapshot"]["more_line"], "regular", 15, width - 48 - 36 - 140, 2)
    total_h = 14 + 16 + 3 + len(more) * 19 + 14
    return 20 + _label_h() + 8 + len(note) * 23 + 10 + len(items) * 51 + 12 + max(total_h, 66) + 20


def _kept_rows(pen: _Pen, kept: Sequence[str], width: float) -> List[List[Tuple[str, float]]]:
    rows: List[List[Tuple[str, float]]] = [[]]
    used = 0.0
    for item in kept:
        chip_w = 14 + 7 + 8 + pen.width(item, "regular", 15) + 14
        if rows[-1] and used + 8 + chip_w > width:
            rows.append([])
            used = 0.0
        rows[-1].append((item, chip_w))
        used += chip_w + (8 if used else 0)
    return [row for row in rows if row]


def _palette_card_h(pen: _Pen, spec: Dict[str, Any], width: float) -> float:
    inner = width - 48
    blurb = pen.fit(spec["palette_blurb"], "regular", 17, inner, 3)
    chip_names = max([len(_swatch_name_lines(pen, s["name"], inner / 5)) for s in spec["palette"]] or [1])
    h = 20 + _label_h() + 18 + 68 + 10 + chip_names * 19 + 3 + 16 + 14 + len(blurb) * 25.5
    kept = _kept_rows(pen, spec["kept"], inner)
    if kept:
        h += 16 + 14 + 16 + 10 + len(kept) * 33 + 8 * (len(kept) - 1)
    return h + 20


def _swatch_name_lines(pen: _Pen, name: str, width: float) -> List[str]:
    words = _clean(name).split()
    if len(words) == 2 and pen.width(name, "semibold", 15) > 52:
        return words
    return pen.fit(name, "semibold", 15, max(48, width - 8), 2)


def _step_parts(pen: _Pen, step: Dict[str, str], width: float):
    inner = width - 48
    title = pen.fit(step["title"], "semibold", 20, inner, 2)
    body = pen.fit(step["body"], "regular", 18, inner, 3)
    return title, body


def _step_h(pen: _Pen, step: Dict[str, str], width: float) -> float:
    title, body = _step_parts(pen, step, width)
    return 20 + 40 + 10 + len(title) * 26 + 6 + len(body) * 26 + 20


def _why_parts(pen: _Pen, spec: Dict[str, Any]):
    inner = CONTENT_W - 72 - 36 - 100
    head = pen.fit(spec["why"]["headline"], "semibold", 28, inner, 2)
    body = pen.fit(spec["why"]["body"], "regular", 19, inner, 4)
    return head, body


def _why_h(pen: _Pen, spec: Dict[str, Any]) -> float:
    head, body = _why_parts(pen, spec)
    return max(18 + _label_h() + 10 + len(head) * 34 + 8 + len(body) * 28.5 + 18, 136)


def _title_size(pen: _Pen, title: str) -> int:
    size = 70
    while size > 44 and pen.width(title, "semibold", size) > CONTENT_W:
        size -= 2
    return size


def board_layout(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Boxes for every block, so the PNG and the tests describe the same frames."""
    pen = _probe()
    width = PORTRAIT_W
    cw = CONTENT_W
    x0 = PAD_X
    y = PAD_TOP
    header = (x0, y, x0 + cw, y + 72)
    y = header[3] + 16
    title_size = _title_size(pen, spec["headline"])
    title = (x0, y, x0 + cw, y + 21 + 8 + title_size * 1.1 + 6 + 29)
    y = title[3] + 14
    rule = (x0, y, x0 + cw, y + 1.5)
    y = rule[3] + 16
    hero_top = y

    duo_w1 = int((cw - 18) / 2.15)
    duo_w2 = cw - 18 - duo_w1
    duo_h = max(_story_card_h(pen, spec, duo_w1), _changes_card_h(pen, spec, duo_w2))
    zone_w = (cw - 3 * 18) / 4
    cards = spec["zone_cards"]
    cols = max(1, len(cards))
    zone_w = (cw - (cols - 1) * 18) / cols
    zone_h = max([_zone_card_h(pen, card, zone_w) for card in cards] or [0])
    has_shop = bool(spec["snapshot"]["items"])
    shop_w = int((cw - 18) * 1.15 / 2.15) if has_shop else 0
    pal_w = cw - 18 - shop_w if has_shop else cw
    mp_h = max(_shop_card_h(pen, spec, shop_w) if has_shop else 0, _palette_card_h(pen, spec, pal_w))
    step_w = (cw - 2 * 18) / 3
    step_h = max(_step_h(pen, step, step_w) for step in spec["roadmap"])
    why_h = _why_h(pen, spec)
    sechead = 23 + 12
    foot_h = 58

    below = 18 + duo_h + 20 + sechead + zone_h + 20 + mp_h + 20 + sechead + step_h + 18 + why_h + 28 + foot_h
    thumbs_n = len(spec.get("detail_chips") or [])
    thumbs_h = 100 if thumbs_n else 0
    gap = 12 if thumbs_n else 0
    height = PORTRAIT_H
    hero_h = height - hero_top - below - thumbs_h - gap
    hero_max = 640
    if hero_h > hero_max:
        extra = hero_h - hero_max
        hero_h = hero_max
        if thumbs_n:
            grow = min(extra, 80)
            thumbs_h += grow
    hero_min = 380
    if hero_h < hero_min:
        height += int(math.ceil(hero_min - hero_h))
        hero_h = hero_min
    hero = (x0, hero_top, x0 + cw, int(hero_top + hero_h))
    y = hero[3]
    thumbs = []
    if thumbs_n:
        y += gap
        tw = (cw - 12 * (thumbs_n - 1)) / thumbs_n
        for i in range(thumbs_n):
            tx = x0 + i * (tw + 12)
            thumbs.append((int(tx), int(y), int(tx + tw), int(y + thumbs_h)))
        y += thumbs_h
    y += 18
    story = (x0, y, x0 + duo_w1, y + duo_h)
    changes = (x0 + duo_w1 + 18, y, x0 + cw, y + duo_h)
    y += duo_h + 20
    zones_head = (x0, y, x0 + cw, y + 23)
    y += sechead
    zones = [(x0 + i * (zone_w + 18), y, x0 + i * (zone_w + 18) + zone_w, y + zone_h) for i in range(len(cards))]
    y += zone_h + 20
    shop = (x0, y, x0 + shop_w, y + mp_h) if has_shop else (x0, y, x0, y)
    palette = (x0 + (shop_w + 18 if has_shop else 0), y, x0 + cw, y + mp_h)
    y += mp_h + 20
    road_head = (x0, y, x0 + cw, y + 23)
    y += sechead
    roadmap = [(x0 + i * (step_w + 18), y, x0 + i * (step_w + 18) + step_w, y + step_h) for i in range(3)]
    y += step_h + 18
    why = (x0, y, x0 + cw, y + why_h)
    footer = (0, height - foot_h, width, height)
    return {
        "size": (width, int(height)),
        "header": header,
        "title": title,
        "title_size": title_size,
        "rule": rule,
        "hero": hero,
        "sources": thumbs,
        "story": story,
        "changes": changes,
        "zones_head": zones_head,
        "zones": zones,
        "shopping": shop,
        "palette": palette,
        "roadmap_head": road_head,
        "roadmap": roadmap,
        "why": why,
        "footer": footer,
        "plan": None,
    }


# ──────────────────────────── Drawing ─────────────────────────────


def _section_label(pen: _Pen, x: float, y: float, number: str) -> None:
    w = pen.text(x, y, number, "semibold", 16, SAGE, tracking=0.2)
    pen.text(x + w + 10, y, SECTION_TITLES[number].upper(), "semibold", 16, GREEN, tracking=0.2)


def _card(pen: _Pen, box, fill=WHITE, edge=LINE, radius: float = 22) -> None:
    pen.rrect(box, radius, fill=fill, outline=edge, width=1.5)


def _chip(pen: _Pen, x: float, y: float, text: str, size: float = 15, pad=(16, 8)) -> None:
    w = pen.width(text, "semibold", size, 0.14)
    h = size * 1.2 + pad[1] * 2
    pen.rrect((x, y - h, x + w + pad[0] * 2, y), h / 2, fill=CHIP_FILL)
    pen.text(x + pad[0], y - h + pad[1], text, "semibold", size, GREEN, tracking=0.14)


def _empty_frame(pen: _Pen, box, title: str, sub: str, radius: float) -> None:
    pen.rrect(box, radius, fill=GREIGE)
    x0, y0, x1, y1 = box
    inner = x1 - x0 - 60
    t = pen.fit(title, "semibold", 26 if (y1 - y0) > 200 else 16, inner, 2)
    s = pen.fit(sub, "regular", 18 if (y1 - y0) > 200 else 13, inner, 2) if (y1 - y0) > 120 else []
    tsize = 26 if (y1 - y0) > 200 else 16
    ssize = 18 if (y1 - y0) > 200 else 13
    total = len(t) * tsize * 1.3 + (8 + len(s) * ssize * 1.4 if s else 0)
    y = y0 + (y1 - y0 - total) / 2
    for line in t:
        pen.text((x0 + x1) / 2, y, line, "semibold", tsize, GREEN, align="center")
        y += tsize * 1.3
    y += 8
    for line in s:
        pen.text((x0 + x1) / 2, y, line, "regular", ssize, MUTED, align="center")
        y += ssize * 1.4


def _draw_header(pen: _Pen, spec: Dict[str, Any], layout: Dict[str, Any]) -> None:
    x0, y0, x1, y1 = layout["header"]
    _lockup(pen, x0, y0, y1 - y0)
    if spec.get("review_pill"):
        pill = spec["review_pill"]
        size = 18
        pw = pen.width(pill, "semibold", size, 0.16) + 52
        ph = size * 1.2 + 24
        py = y0 + (y1 - y0 - ph) / 2
        pen.rrect((x1 - pw, py, x1, py + ph), ph / 2, fill=GREEN)
        pen.text(x1 - pw + 26, py + 12, pill, "semibold", size, WHITE, tracking=0.16)
        note = list(spec.get("review_note") or ())
        ny = y0 + (y1 - y0 - len(note) * 21) / 2
        for line in note:
            pen.text(x1 - pw - 16, ny, line, "regular", 15, MUTED, align="right")
            ny += 21
    tx0, ty, tx1, _ = layout["title"]
    pen.text(tx0, ty, spec["label"].upper(), "medium", 17, MUTED, tracking=0.24)
    size = layout["title_size"]
    pen.text(tx0, ty + 21 + 8, spec["headline"], "semibold", size, GREEN)
    sub = pen.fit(spec["title_sub"], "light", 23, tx1 - tx0, 1)
    if sub:
        pen.text(tx0, ty + 21 + 8 + size * 1.1 + 6, sub[0], "light", 23, CHAR)
    pen.rect(layout["rule"], fill=LINE)


def _draw_photos(pen: _Pen, spec: Dict[str, Any], layout: Dict[str, Any], lead: Dict[str, Any]) -> None:
    slots = _view_slots(spec["images"], lead)
    hero_box = layout["hero"]
    hero = slots[0] if slots else None
    if hero is None:
        _empty_frame(pen, hero_box, spec["placeholder_label"], spec["placeholder_sub"], 28)
    elif hero["image"] is None:
        _empty_frame(pen, hero_box, hero["caption"], "This view is not filled from another angle.", 28)
    else:
        pen.paste_cover(hero["image"], hero_box, 28, (0.48, 0.62))
        _chip(pen, hero_box[0] + 22, hero_box[3] - 22, hero["chip"], 15)
    for box, slot in zip(layout["sources"], slots[1:4]):
        if slot["image"] is None:
            _empty_frame(pen, box, slot["chip"].title(), "", 16)
            continue
        pen.paste_cover(slot["image"], box, 16, (0.5, 0.6))
        _chip(pen, box[0] + 12, box[3] - 12, slot["chip"], 13, pad=(12, 5))


def _draw_story(pen: _Pen, spec: Dict[str, Any], box) -> None:
    _card(pen, box)
    x0, y0, x1, _ = box
    _section_label(pen, x0 + 24, y0 + 20, "01")
    y = y0 + 20 + _label_h() + 12
    for line in pen.fit(spec["story_headline"], "semibold", 28, x1 - x0 - 48, 2):
        pen.text(x0 + 24, y, line, "semibold", 28, CHAR)
        y += 35
    y += 10
    for line in pen.fit(spec["story"], "regular", 20, x1 - x0 - 48, 4):
        pen.text(x0 + 24, y, line, "regular", 20, BODY)
        y += 31


def _draw_changes(pen: _Pen, spec: Dict[str, Any], box) -> None:
    _card(pen, box, fill=SAGE_L, edge=SAGE_LINE)
    x0, y0, x1, _ = box
    _section_label(pen, x0 + 24, y0 + 20, "02")
    y = y0 + 20 + _label_h() + 12
    for title, body in _change_rows(pen, spec["moves"], x1 - x0):
        _check_icon(pen, x0 + 24, y + 1)
        ty = y
        for line in title:
            pen.text(x0 + 24 + 38, ty, line, "semibold", 18, CHAR)
            ty += 23.4
        ty += 2
        for line in body:
            pen.text(x0 + 24 + 38, ty, line, "regular", 17, CHANGE_INK)
            ty += 23.8
        y = max(y + 26, ty) + 9


def _sechead(pen: _Pen, box, number: str, note: str) -> None:
    x0, y0, x1, _ = box
    _section_label(pen, x0, y0, number)
    pen.text(x1, y0 - 1, note, "regular", 18, MUTED, align="right")


def _draw_zones(pen: _Pen, spec: Dict[str, Any], layout: Dict[str, Any]) -> None:
    _sechead(pen, layout["zones_head"], "03", ZONES_NOTE)
    for card, box in zip(spec["zone_cards"], layout["zones"]):
        _card(pen, box)
        x0, y0, x1, _ = box
        num = card["number"]
        nw = pen.width(num, "semibold", 15, 0.1)
        pen.rrect((x0 + 22, y0 + 28, x0 + 22 + nw + 24, y0 + 28 + 28), 14, fill=SAGE_L)
        pen.text(x0 + 34, y0 + 33, num, "semibold", 15, GREEN, tracking=0.1)
        _zone_icon(pen, card["icon"], x1 - 22 - 40, y0 + 20, 40)
        title, obj, job = _zone_card_parts(pen, card, x1 - x0)
        y = y0 + 20 + 40 + 10
        for line in title:
            pen.text(x0 + 22, y, line, "semibold", 22, CHAR)
            y += 27
        if obj:
            y += 4
            pen.text(x0 + 22, y, obj[0], "medium", 14, MUTED, tracking=0.14)
            y += 17.5
        y += 10
        for line in job:
            pen.text(x0 + 22, y, line, "regular", 18, SOFT_INK)
            y += 26


def _draw_shop(pen: _Pen, spec: Dict[str, Any], box) -> None:
    if box[2] <= box[0]:
        return
    _card(pen, box)
    x0, y0, x1, y1 = box
    _section_label(pen, x0 + 24, y0 + 20, "04")
    y = y0 + 20 + _label_h() + 8
    for line in pen.fit(SHOPPING_DISCLAIMER, "regular", 16, x1 - x0 - 48, 2):
        pen.text(x0 + 24, y, line, "regular", 16, MUTED)
        y += 23
    y += 10
    for row in spec["snapshot"]["items"]:
        pen.ellipse((x0 + 24, y + 7, x0 + 60, y + 43), fill=SAGE_L)
        _item_icon(pen, row["icon"], x0 + 32, y + 15, 20)
        price = row["price"]
        pw = pen.width(price, "semibold", 18)
        name = pen.fit(row["short"], "regular", 18, x1 - x0 - 48 - 50 - pw - 12, 1)
        pen.text(x0 + 24 + 50, y + 14, name[0] if name else "", "regular", 18, CHAR)
        pen.text(x1 - 24, y + 14, price, "semibold", 18, CHAR, align="right")
        pen.rect((x0 + 24, y + 50, x1 - 24, y + 51), fill=LINE)
        y += 51
    y += 12
    tbox = (x0 + 24, y, x1 - 24, y1 - 20)
    pen.rrect(tbox, 14, fill=GREIGE_L)
    pen.text(tbox[0] + 18, tbox[1] + 14, SNAPSHOT_TOTAL_LABEL.upper(), "semibold", 13, MUTED, tracking=0.16)
    ty = tbox[1] + 14 + 16 + 3
    for line in pen.fit(spec["snapshot"]["more_line"], "regular", 15, tbox[2] - tbox[0] - 36 - 140, 2):
        pen.text(tbox[0] + 18, ty, line, "regular", 15, MUTED)
        ty += 19
    total = spec["snapshot"]["total"]
    if total and total not in {"—", "-"}:
        pen.text(tbox[2] - 18, (tbox[1] + tbox[3]) / 2 - 20, total, "semibold", 30, GREEN, align="right")


def _draw_palette(pen: _Pen, spec: Dict[str, Any], box) -> None:
    _card(pen, box)
    x0, y0, x1, _ = box
    inner = x1 - x0 - 48
    _section_label(pen, x0 + 24, y0 + 20, "05")
    y = y0 + 20 + _label_h() + 18
    swatches = list(spec["palette"])[:5]
    col = inner / 5
    lines_max = 1
    for index, swatch in enumerate(swatches):
        cx = x0 + 24 + col * index + col / 2
        pen.ellipse((cx - 34, y, cx + 34, y + 68), fill=hex_rgb(_hex(swatch["hex"], "#E6E1DB")), outline=CHIP_RING, width=1.5)
        ny = y + 68 + 10
        lines = _swatch_name_lines(pen, swatch["name"], col)
        lines_max = max(lines_max, len(lines))
        for line in lines:
            pen.text(cx, ny, line, "semibold", 15, CHAR, align="center")
            ny += 19
    hy = y + 68 + 10 + lines_max * 19 + 3
    for index, swatch in enumerate(swatches):
        cx = x0 + 24 + col * index + col / 2
        pen.text(cx, hy, _hex(swatch["hex"], "#E6E1DB"), "regular", 13, MUTED, align="center")
    y = hy + 16 + 14
    for line in pen.fit(spec["palette_blurb"], "regular", 17, inner, 3):
        pen.text(x0 + 24, y, line, "regular", 17, BODY)
        y += 25.5
    rows = _kept_rows(pen, spec["kept"], inner)
    if not rows:
        return
    y += 16
    pen.rect((x0 + 24, y, x1 - 24, y + 1), fill=LINE)
    y += 14
    pen.text(x0 + 24, y, KEPT_LABEL.upper(), "semibold", 13, MUTED, tracking=0.16)
    y += 16 + 10
    for row in rows:
        cx = x0 + 24
        for item, chip_w in row:
            pen.rrect((cx, y, cx + chip_w, y + 33), 16.5, fill=GREIGE_L)
            pen.ellipse((cx + 14, y + 13, cx + 21, y + 20), fill=SAGE)
            pen.text(cx + 14 + 7 + 8, y + 7, item, "regular", 15, SOFT_INK)
            cx += chip_w + 8
        y += 33 + 8


def _draw_roadmap(pen: _Pen, spec: Dict[str, Any], layout: Dict[str, Any]) -> None:
    _sechead(pen, layout["roadmap_head"], "06", ROADMAP_NOTE)
    for index, (step, box) in enumerate(zip(spec["roadmap"], layout["roadmap"])):
        _card(pen, box)
        x0, y0, x1, _ = box
        pen.ellipse((x0 + 24, y0 + 20, x0 + 64, y0 + 60), outline=GREEN, width=1.8)
        pen.text(x0 + 44, y0 + 30, str(index + 1), "semibold", 17, GREEN, align="center")
        pen.text(x0 + 76, y0 + 32, f"STEP {index + 1}", "semibold", 14, MUTED, tracking=0.16)
        title, body = _step_parts(pen, step, x1 - x0)
        y = y0 + 20 + 40 + 10
        for line in title:
            pen.text(x0 + 24, y, line, "semibold", 20, CHAR)
            y += 26
        y += 6
        for line in body:
            pen.text(x0 + 24, y, line, "regular", 18, BODY)
            y += 26


def _draw_why(pen: _Pen, spec: Dict[str, Any], box) -> None:
    x0, y0, x1, y1 = box
    pen.rrect(box, 26, fill=SAGE_L)
    _section_label(pen, x0 + 36, y0 + 18, "07")
    head, body = _why_parts(pen, spec)
    y = y0 + 18 + _label_h() + 10
    for line in head:
        pen.text(x0 + 36, y, line, "semibold", 28, GREEN)
        y += 34
    y += 8
    for line in body:
        pen.text(x0 + 36, y, line, "regular", 19, SOFT_INK)
        y += 28.5
    cy = (y0 + y1) / 2
    pen.ellipse((x1 - 36 - 100, cy - 50, x1 - 36, cy + 50), fill=WHITE, outline=WHY_RING, width=1.5)
    _waves_icon(pen, x1 - 36 - 76, cy - 26, 52)


def _draw_footer(pen: _Pen, spec: Dict[str, Any], box) -> None:
    x0, y0, x1, y1 = box
    pen.rect(box, fill=GREEN)
    mid = (y0 + y1) / 2
    pen.text(PAD_X, mid - 11, spec["footer_left"], "regular", 17, WHITE, tracking=0.3)
    pen.text(x1 - PAD_X, mid - 9, spec["footer_right"], "medium", 14, FOOT_SOFT, tracking=0.14, align="right")


def customer_board_text(spec: Dict[str, Any]) -> str:
    """Every customer-facing string the Design Plan board paints.

    Review codes (SOURCE_, AFTER_, lead ids) are not part of this text.
    """
    snapshot = spec.get("snapshot") or {}
    parts: List[str] = [
        BRAND_NAME,
        spec.get("review_pill") or "",
        *(spec.get("review_note") or ()),
        str(spec.get("label") or "").upper(),
        spec.get("headline") or "",
        spec.get("title_sub") or "",
        spec.get("hero_chip") or "",
        *[str(c) for c in spec.get("detail_chips") or []],
        *[f"{n} {SECTION_TITLES[n].upper()}" for n in SECTION_TITLES],
        spec.get("story_headline") or "",
        spec.get("story") or "",
        ZONES_NOTE,
        ROADMAP_NOTE,
        spec.get("palette_blurb") or "",
        KEPT_LABEL.upper(),
        *[str(item) for item in spec.get("kept") or []],
        (spec.get("why") or {}).get("headline") or "",
        (spec.get("why") or {}).get("body") or "",
        spec.get("footer_left") or "",
        spec.get("footer_right") or "",
    ]
    for move in spec.get("moves") or []:
        parts += [str(move.get("title") or ""), str(move.get("body") or "")]
    for card in spec.get("zone_cards") or []:
        parts += [card["number"], card["title"], card.get("object", "").upper(), card["job"]]
    if snapshot.get("items"):
        parts += [SHOPPING_DISCLAIMER, SNAPSHOT_TOTAL_LABEL.upper(), snapshot.get("more_line") or "", str(snapshot.get("total") or "")]
        for row in snapshot["items"]:
            parts += [str(row.get("short") or ""), str(row.get("price") or "")]
    for swatch in spec.get("palette") or []:
        parts += [str(swatch.get("name") or ""), str(swatch.get("hex") or "")]
    for index, step in enumerate(spec.get("roadmap") or []):
        parts += [f"STEP {index + 1}", str(step.get("title") or ""), str(step.get("body") or "")]
    return "\n".join(p for p in parts if p)


def build_image_board(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Any],
    final: Optional[bool] = None,
) -> bytes:
    """Render the Design Plan PNG. ``final`` overrides the review controls; default reads package_status."""
    lead = lead or {}
    spec = board_spec(lead, deliverable, images)
    if final is not None and final != spec["released"]:
        spec = {
            **spec,
            "released": final,
            "review_pill": "" if final else REVIEW_PILL,
            "review_note": () if final else REVIEW_NOTE,
            "footer_right": (DESIGN_PLAN_FOOTER if final else DESIGN_PLAN_FOOTER_REVIEW).upper(),
        }
    layout = board_layout(spec)
    width, height = layout["size"]
    s = SUPERSAMPLE
    base = Image.new("RGB", (width * s, height * s), OFF)
    pen = _Pen(base, s)
    _draw_header(pen, spec, layout)
    _draw_photos(pen, spec, layout, lead)
    _draw_story(pen, spec, layout["story"])
    _draw_changes(pen, spec, layout["changes"])
    _draw_zones(pen, spec, layout)
    _draw_shop(pen, spec, layout["shopping"])
    _draw_palette(pen, spec, layout["palette"])
    _draw_roadmap(pen, spec, layout)
    _draw_why(pen, spec, layout["why"])
    _draw_footer(pen, spec, layout["footer"])
    out_img = base.resize((width, height), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    out_img.save(out, format="PNG", compress_level=6)
    return out.getvalue()
