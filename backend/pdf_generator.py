"""
FlowSpace Blueprint PDF — dashboard organization plan.

Layout (Letter):
  Page 1 — dense dashboard inspired by the FlowSpace “design plan” sheet
            (hero, needs, optional paint, zones, extra views, strategy).
  Page 2 — consumer DIY instructions + full shopping list / budget.
  Page 3 — Before | After when a real photo exists.

Visual template only: site emerald/slate palette, Fraunces display + Inter body.
Content is always an organization plan for closets, garages, laundry rooms,
pantries, mudrooms, and storage — never a bedroom redesign.

Hard rules:
  - Windows and room proportions stay ~95% true to the customer photo.
  - Never invent footage, window counts, or measured callouts.
  - Floor plans only when the pipeline actually provides one.
  - Wall paint/color is an optional recommendation, not applied in the visual.
  - Change bins, furniture, and layout; preserve the physical shell.

Public API is unchanged: build_pdf(lead=, deliverable=, images=) -> bytes
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from blueprint_layers import BUDGET_LABELS, STORAGE, resolve_layers
from pdf_images import (
    COMPARE_AFTER_BANNER,
    COMPARE_AFTER_EMPTY,
    COMPARE_AFTER_EMPTY_SUB,
    COMPARE_BEFORE_BANNER,
    COMPARE_BEFORE_EMPTY,
    COMPARE_BEFORE_EMPTY_SUB,
    HERO_BANNER_ORGANIZED,
    HERO_BANNER_ORIGINAL,
    HERO_PLACEHOLDER_LABEL,
    HERO_PLACEHOLDER_SUB,
    coerce_image_bytes,
    normalize_pdf_images,
)

# ──────────────────────────── Palette (site design system) ─────────────────────────────
EMERALD = HexColor("#059669")
EMERALD_DEEP = HexColor("#047857")
MINT = HexColor("#34d399")
MINT_BG = HexColor("#ecfdf5")
SLATE = HexColor("#0f172a")
SLATE_MUTED = HexColor("#475569")
SLATE_SOFT = HexColor("#64748b")
SURFACE = HexColor("#ffffff")
SOFT = HexColor("#f8fafc")
BORDER = HexColor("#e2e8f0")
WHITE = colors.white
SAGE = HexColor("#10b981")
INK = SLATE
MUTED = SLATE_MUTED
LINE = BORDER
TAGLINE = "Clear space. Create flow. Live better."
RADIUS = 8
CALLOUT_LINES = (
    "Smart choices. Everything in its place.",
    "Less stress. More time. More you.",
)

SPACE_LABELS = {
    "living_room": "Living room",
    "bedroom": "Bedroom",
    "closet": "Closet",
    "garage": "Garage",
    "pantry": "Pantry",
    "laundry_room": "Laundry",
    "laundry": "Laundry",
    "home_office": "Home office",
    "kids_room": "Kids' room",
    "mudroom": "Mudroom",
    "storage": "Storage",
    "other": "Space",
}

DEFAULT_NOTES = (
    "Windows and room proportions stay ~95% true to your photo. "
    "We do not invent dimensions. Paint is optional — consider it only if it helps your goal."
)
OPTIONAL_PAINT_HEADING = "Optional paint — consider if it helps"
OPTIONAL_PAINT_NOTE = (
    "Optional paint — consider if it helps. Not applied in the visual. "
    "Consider this color only if it helps your organization goal."
)
FOOTER_NOTE = (
    "Note: Measurements are approximate. Adjust to your space as needed. "
    "Windows and proportions stay ~95% true to your photo."
)

DEFAULT_STRATEGY = [
    "Keep the layout balanced and clutter-free",
    "Use matching bins for visual harmony",
    "Layer soft textures for warmth and comfort",
    "Use hidden storage to reduce visual noise",
]
DEFAULT_ACTIONS = [
    "Declutter and keep only what you need",
    "Add matching bins and wall storage",
    "Refresh lighting with a task lamp",
    "Label homes so everything returns",
]
DEFAULT_BENEFITS = [
    "More restful and relaxing environment",
    "Easy to keep tidy and organized",
    "Feels brighter, softer and more open",
    "Better daily routine and less hunting",
]
DEFAULT_NEEDS = [
    ("Storage", "Hidden homes for daily items", "box"),
    ("Clear path", "Floor stays a destination, not a dump", "car"),
    ("Landing zone", "Drop-and-go at the door you already use", "bag"),
    ("Lighting", "See what you own without hunting", "bulb"),
]

NEED_ICON_RULES: Sequence[Tuple[Tuple[str, ...], str]] = (
    (("tool", "hardware", "workbench", "peg"), "wrench"),
    (("sport", "bag", "gear", "bike"), "ball"),
    (("cloth", "closet", "hanger", "apparel", "coat"), "hanger"),
    (("shoe",), "hanger"),
    (("bed", "linen", "sheet", "towel", "laundry"), "layers"),
    (("paper", "file", "document", "pdf"), "file"),
    (("decor", "accent", "art"), "leaf"),
    (("light", "lamp"), "bulb"),
    (("park", "car", "stall", "floor", "path", "circul"), "car"),
    (("stor", "bin", "basket", "hidden", "shelf"), "box"),
    (("personal", "book", "med", "daily"), "person"),
    (("cable", "tech", "office"), "file"),
)

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_FILES = {
    "FSSerif": "Fraunces-Regular.ttf",
    "FSSerif-Bold": "Fraunces-Bold.ttf",
    "FSSerif-Italic": "Fraunces-Regular.ttf",
    "FSSans": "Inter-Regular.ttf",
    "FSSans-Medium": "Inter-Medium.ttf",
    "FSSans-Semi": "Inter-SemiBold.ttf",
    "FSSans-Bold": "Inter-Bold.ttf",
    "FSSans-Italic": "Inter-Italic.ttf",
}
_FALLBACKS = {
    "FSSerif": "Times-Roman",
    "FSSerif-Bold": "Times-Bold",
    "FSSerif-Italic": "Times-Italic",
    "FSSans": "Helvetica",
    "FSSans-Medium": "Helvetica",
    "FSSans-Semi": "Helvetica-Bold",
    "FSSans-Bold": "Helvetica-Bold",
    "FSSans-Italic": "Helvetica-Oblique",
}
_REGISTERED = False


def _register_fonts() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    for name, filename in _FONT_FILES.items():
        path = FONTS_DIR / filename
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        except Exception:
            continue
    _REGISTERED = True


def _font(name: str) -> str:
    _register_fonts()
    registered = set(pdfmetrics.getRegisteredFontNames())
    if name in registered:
        return name
    return _FALLBACKS.get(name, "Helvetica")


def space_label(space_type: Optional[str]) -> str:
    key = (space_type or "space").strip().lower().replace(" ", "_")
    return SPACE_LABELS.get(key, key.replace("_", " ").title() or "Space")


def plan_title(space_type: Optional[str]) -> str:
    """Space-aware PDF title. Closets use Blueprint; others are Organization Plans."""
    key = (space_type or "space").strip().lower().replace(" ", "_")
    label = space_label(space_type)
    if key == "closet":
        return "Closet Blueprint"
    return f"{label} Organization Plan"


PAGE_W, PAGE_H = LETTER
MARGIN = 0.40 * inch
DASH_HEADER_H = 0.90 * inch
INT_HEADER_H = 0.46 * inch
FOOTER_H = 0.36 * inch


# ──────────────────────────── Styles ─────────────────────────────
def _styles():
    _register_fonts()
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Title"], fontName=_font("FSSerif-Bold"),
            fontSize=18, leading=21, textColor=SLATE, alignment=TA_CENTER, spaceAfter=0,
        ),
        "kicker": ParagraphStyle(
            "kicker", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.2, leading=9, textColor=EMERALD_DEEP, alignment=TA_LEFT,
            spaceBefore=0, spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "section", parent=base["BodyText"], fontName=_font("FSSans-Bold"),
            fontSize=7.4, leading=9.5, textColor=SLATE, alignment=TA_LEFT,
            spaceBefore=0, spaceAfter=3,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName=_font("FSSans-Semi"),
            fontSize=8.5, leading=11, textColor=EMERALD_DEEP, spaceBefore=2, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=8, leading=10.4, textColor=INK,
        ),
        "bodySmall": ParagraphStyle(
            "bodySmall", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.1, leading=9.2, textColor=INK,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["BodyText"], fontName=_font("FSSans-Italic"),
            fontSize=6.8, leading=8.8, textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "label", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.6, leading=9.6, textColor=SLATE,
        ),
        "needTitle": ParagraphStyle(
            "needTitle", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.3, leading=9.2, textColor=SLATE,
        ),
        "needSub": ParagraphStyle(
            "needSub", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.5, leading=8.2, textColor=SLATE_MUTED,
        ),
        "cardCat": ParagraphStyle(
            "cardCat", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.2, leading=8, textColor=EMERALD_DEEP, alignment=TA_LEFT,
        ),
        "cardTitle": ParagraphStyle(
            "cardTitle", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.4, leading=9.4, textColor=SLATE,
        ),
        "cardMeta": ParagraphStyle(
            "cardMeta", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.6, leading=8.4, textColor=MUTED,
        ),
        "banner": ParagraphStyle(
            "banner", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.4, leading=8, textColor=WHITE, alignment=TA_CENTER,
        ),
        "whiteTiny": ParagraphStyle(
            "whiteTiny", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.2, leading=7.8, textColor=HexColor("#d1fae5"), alignment=TA_CENTER,
        ),
        "budgetHead": ParagraphStyle(
            "budgetHead", parent=base["BodyText"], fontName=_font("FSSans-Bold"),
            fontSize=8.2, leading=10.4, textColor=WHITE, alignment=TA_CENTER,
        ),
        "th": ParagraphStyle(
            "th", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.3, leading=8, textColor=WHITE,
        ),
        "thRight": ParagraphStyle(
            "thRight", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.3, leading=8, textColor=WHITE, alignment=TA_RIGHT,
        ),
        "td": ParagraphStyle(
            "td", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.0, leading=9.0, textColor=INK,
        ),
        "tdRight": ParagraphStyle(
            "tdRight", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.0, leading=9.0, textColor=INK, alignment=TA_RIGHT,
        ),
        "tdBold": ParagraphStyle(
            "tdBold", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.2, leading=9.2, textColor=SLATE,
        ),
        "tdBoldRight": ParagraphStyle(
            "tdBoldRight", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.2, leading=9.2, textColor=SLATE, alignment=TA_RIGHT,
        ),
        "check": ParagraphStyle(
            "check", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.1, leading=9.6, textColor=INK, leftIndent=0,
        ),
        "price": ParagraphStyle(
            "price", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.2, leading=9, textColor=EMERALD_DEEP,
        ),
        "intro": ParagraphStyle(
            "intro", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.4, leading=9.6, textColor=SLATE_MUTED, alignment=TA_CENTER,
        ),
    }


# ──────────────────────────── Primitives ─────────────────────────────
def _clip(text: str, n: int = 220) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= n:
        return cleaned
    return cleaned[: n - 1].rstrip() + "…"


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _cover_image(
    src: Optional[bytes],
    width: float,
    height: float,
    *,
    missing_label: str = "Image not provided",
    missing_sublabel: str = "",
    fill: bool = True,
) -> Any:
    """Fit a photo into a box. ``fill=True`` covers and clips; missing stays a labeled panel."""
    data = coerce_image_bytes(src)
    if not data:
        return _placeholder(width, height, missing_label, missing_sublabel)
    try:
        return ClippedPhoto(data, width, height, fill=fill)
    except Exception:
        return _placeholder(width, height, "Image unavailable")


class ClippedPhoto(Flowable):
    """Draw an image covering (or contained in) a rounded box without a white letterbox."""

    def __init__(self, data: bytes, width: float, height: float, fill: bool = True):
        super().__init__()
        self.data = data
        self.width = width
        self.height = max(height, 24)
        self.fill = fill
        self._ir = ImageReader(io.BytesIO(data))
        iw, ih = self._ir.getSize()
        if iw <= 0 or ih <= 0:
            raise ValueError("empty")
        self._iw, self._ih = iw, ih

    def wrap(self, availWidth, availHeight):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(SOFT)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        path = c.beginPath()
        path.rect(0, 0, self.width, self.height)
        c.clipPath(path, stroke=0, fill=0)
        if self.fill:
            scale = max(self.width / self._iw, self.height / self._ih)
        else:
            scale = min(self.width / self._iw, self.height / self._ih)
        dw, dh = self._iw * scale, self._ih * scale
        x = (self.width - dw) / 2.0
        y = (self.height - dh) / 2.0
        c.drawImage(self._ir, x, y, width=dw, height=dh, mask="auto")
        c.restoreState()


class BrandedPlaceholder(Flowable):
    """Soft mint panel with a house mark — not a gray void."""

    def __init__(self, width: float, height: float, label: str, sublabel: str = ""):
        super().__init__()
        self.width = width
        self.height = max(height, 36)
        self.label = label
        self.sublabel = sublabel

    def draw(self):
        c = self.canv
        c.setFillColor(MINT_BG)
        c.roundRect(0, 0, self.width, self.height, RADIUS, fill=1, stroke=0)
        c.setStrokeColor(MINT)
        c.setLineWidth(0.9)
        c.roundRect(0.4, 0.4, self.width - 0.8, self.height - 0.8, RADIUS, fill=0, stroke=1)
        cx, cy = self.width / 2.0, self.height / 2.0 + (10 if self.sublabel else 6)
        s = min(18.0, self.height * 0.24)
        c.setStrokeColor(EMERALD)
        c.setLineWidth(1.5)
        p = c.beginPath()
        p.moveTo(cx - s * 0.55, cy)
        p.lineTo(cx, cy + s * 0.5)
        p.lineTo(cx + s * 0.55, cy)
        p.lineTo(cx + s * 0.55, cy - s * 0.5)
        p.lineTo(cx - s * 0.55, cy - s * 0.5)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.setFillColor(EMERALD_DEEP)
        c.setFont(_font("FSSans-Semi"), 7.2)
        ly = max(14 if self.sublabel else 8, cy - s - 12)
        c.drawCentredString(self.width / 2.0, ly, self.label)
        if self.sublabel:
            c.setFillColor(SLATE_SOFT)
            c.setFont(_font("FSSans"), 6.2)
            c.drawCentredString(self.width / 2.0, max(6, ly - 11), self.sublabel)


def _placeholder(w: float, h: float, label: str, sublabel: str = ""):
    return BrandedPlaceholder(w, h, label, sublabel)


def _draw_need_glyph(c, kind: str, cx: float, cy: float, s: float) -> None:
    c.setStrokeColor(EMERALD_DEEP)
    c.setFillColor(EMERALD)
    c.setLineWidth(1.15)
    c.setLineCap(1)
    c.setLineJoin(1)
    k = (kind or "box").lower()
    if k == "hanger":
        c.circle(cx, cy + s * 0.28, s * 0.12, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(cx, cy + s * 0.16)
        p.lineTo(cx, cy + s * 0.02)
        p.lineTo(cx - s * 0.38, cy - s * 0.18)
        p.lineTo(cx + s * 0.38, cy - s * 0.18)
        p.lineTo(cx, cy + s * 0.02)
        c.drawPath(p, stroke=1, fill=0)
    elif k == "layers":
        for i, dy in enumerate((-0.22, 0.0, 0.22)):
            c.roundRect(cx - s * 0.34, cy + dy * s - 2.2, s * 0.68, 4.2, 1.2, fill=0, stroke=1)
    elif k == "person":
        c.circle(cx, cy + s * 0.22, s * 0.16, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(cx - s * 0.32, cy - s * 0.32)
        p.curveTo(cx - s * 0.32, cy + s * 0.02, cx + s * 0.32, cy + s * 0.02, cx + s * 0.32, cy - s * 0.32)
        c.drawPath(p, stroke=1, fill=0)
    elif k == "leaf":
        p = c.beginPath()
        p.moveTo(cx, cy - s * 0.32)
        p.curveTo(cx + s * 0.42, cy - s * 0.05, cx + s * 0.18, cy + s * 0.38, cx, cy + s * 0.34)
        p.curveTo(cx - s * 0.18, cy + s * 0.38, cx - s * 0.42, cy - s * 0.05, cx, cy - s * 0.32)
        c.drawPath(p, stroke=1, fill=0)
        c.line(cx, cy - s * 0.28, cx, cy + s * 0.22)
    elif k == "bulb":
        c.circle(cx, cy + s * 0.08, s * 0.26, fill=0, stroke=1)
        c.roundRect(cx - s * 0.12, cy - s * 0.32, s * 0.24, s * 0.16, 1.2, fill=0, stroke=1)
    elif k == "wrench":
        c.setLineWidth(1.4)
        c.roundRect(cx - s * 0.36, cy + s * 0.04, s * 0.28, s * 0.28, 1.4, fill=0, stroke=1)
        c.line(cx - s * 0.10, cy + s * 0.10, cx + s * 0.34, cy - s * 0.28)
        c.setLineWidth(2.2)
        c.line(cx + s * 0.16, cy - s * 0.12, cx + s * 0.32, cy - s * 0.28)
        c.line(cx + s * 0.22, cy - s * 0.34, cx + s * 0.38, cy - s * 0.18)
    elif k == "ball":
        c.circle(cx, cy, s * 0.32, fill=0, stroke=1)
        c.arc(cx - s * 0.32, cy - s * 0.12, cx + s * 0.32, cy + s * 0.32, 200, 140)
    elif k == "car":
        c.roundRect(cx - s * 0.36, cy - s * 0.08, s * 0.72, s * 0.28, 2, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(cx - s * 0.22, cy + s * 0.20)
        p.lineTo(cx - s * 0.08, cy + s * 0.34)
        p.lineTo(cx + s * 0.14, cy + s * 0.34)
        p.lineTo(cx + s * 0.28, cy + s * 0.20)
        c.drawPath(p, stroke=1, fill=0)
        c.circle(cx - s * 0.20, cy - s * 0.16, s * 0.09, fill=0, stroke=1)
        c.circle(cx + s * 0.20, cy - s * 0.16, s * 0.09, fill=0, stroke=1)
    elif k == "file":
        c.rect(cx - s * 0.26, cy - s * 0.32, s * 0.52, s * 0.64, fill=0, stroke=1)
        c.line(cx - s * 0.14, cy + s * 0.12, cx + s * 0.14, cy + s * 0.12)
        c.line(cx - s * 0.14, cy - s * 0.02, cx + s * 0.14, cy - s * 0.02)
        c.line(cx - s * 0.14, cy - s * 0.16, cx + s * 0.08, cy - s * 0.16)
    elif k == "bag":
        c.roundRect(cx - s * 0.28, cy - s * 0.28, s * 0.56, s * 0.42, 2, fill=0, stroke=1)
        p = c.beginPath()
        p.moveTo(cx - s * 0.14, cy + s * 0.12)
        p.curveTo(cx - s * 0.14, cy + s * 0.36, cx + s * 0.14, cy + s * 0.36, cx + s * 0.14, cy + s * 0.12)
        c.drawPath(p, stroke=1, fill=0)
    else:
        c.roundRect(cx - s * 0.30, cy - s * 0.28, s * 0.60, s * 0.48, 2, fill=0, stroke=1)
        c.rect(cx - s * 0.36, cy + s * 0.12, s * 0.72, s * 0.14, fill=0, stroke=1)


class IconBadge(Flowable):
    """Circular mint badge with a simple storage-need glyph."""

    def __init__(self, kind: str, size: float = 22):
        super().__init__()
        self.kind = kind
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        c = self.canv
        r = self.size / 2.0
        c.setFillColor(MINT_BG)
        c.circle(r, r, r, fill=1, stroke=0)
        c.setStrokeColor(MINT)
        c.setLineWidth(0.8)
        c.circle(r, r, r - 0.4, fill=0, stroke=1)
        _draw_need_glyph(c, self.kind, r, r, r * 0.78)


class NumberBadge(Flowable):
    def __init__(self, n: int, size: float = 12, fill: Color = EMERALD):
        super().__init__()
        self.n = n
        self.size = size
        self.fill = fill
        self.width = size
        self.height = size

    def draw(self):
        c = self.canv
        r = self.size / 2
        c.setFillColor(self.fill)
        c.circle(r, r, r, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(_font("FSSans-Bold"), max(6, self.size * 0.55))
        c.drawCentredString(r, r - self.size * 0.18, str(self.n))


class ZonePlan(Flowable):
    """Schematic top-view zones — conceptual, never measured."""

    def __init__(self, zones: Sequence[Dict[str, str]], width: float, height: float):
        super().__init__()
        self.zones = list(zones or [])[:6]
        self.width = width
        self.height = max(height, 88)

    def draw(self):
        c = self.canv
        c.setFillColor(SOFT)
        c.roundRect(0, 0, self.width, self.height, RADIUS, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.8)
        c.roundRect(0.5, 0.5, self.width - 1, self.height - 1, RADIUS, fill=0, stroke=1)

        pad = 8
        inner_x, inner_y = pad, pad
        inner_w = self.width - pad * 2
        inner_h = self.height - pad * 2
        c.setFillColor(WHITE)
        c.roundRect(inner_x, inner_y, inner_w, inner_h, 5, fill=1, stroke=0)
        c.setStrokeColor(SLATE)
        c.setLineWidth(1.15)
        c.roundRect(inner_x, inner_y, inner_w, inner_h, 5, fill=0, stroke=1)

        n = max(len(self.zones), 1)
        fills = (MINT_BG, WHITE, HexColor("#f0fdf4"), WHITE)
        # Split into a 2-column schematic so it reads as a plan, not a scorecard.
        cols = 2 if n >= 2 else 1
        rows = (n + cols - 1) // cols
        gap = 4
        tw = (inner_w - gap * (cols + 1)) / cols
        th = (inner_h - gap * (rows + 1)) / rows

        for i in range(n):
            z = self.zones[i] if i < len(self.zones) else {}
            r, col = divmod(i, cols)
            x = inner_x + gap + col * (tw + gap)
            y = inner_y + inner_h - gap - (r + 1) * th - r * gap
            c.setFillColor(fills[i % len(fills)])
            c.roundRect(x, y, tw, th, 3, fill=1, stroke=0)
            c.setStrokeColor(MINT)
            c.setLineWidth(0.7)
            c.roundRect(x, y, tw, th, 3, fill=0, stroke=1)
            c.setFillColor(EMERALD if i % 2 == 0 else EMERALD_DEEP)
            c.circle(x + 9, y + th - 10, 6, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont(_font("FSSans-Bold"), 6.5)
            c.drawCentredString(x + 9, y + th - 12.2, str(i + 1))
            title = (z.get("title") or f"Zone {i + 1}")
            c.setFillColor(SLATE)
            c.setFont(_font("FSSans-Semi"), 6.0)
            max_chars = max(8, int((tw - 22) / 3.7))
            c.drawString(x + 18, y + th - 13, title[:max_chars])


def _card(inner, width: float, pad: float = 6, *, fill: Color = WHITE, box: Color = BORDER) -> Table:
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.6, box),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("LEFTPADDING", (0, 0), (-1, -1), pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def _swatch(hex_color: str, size: float = 22) -> Table:
    try:
        fill = HexColor(hex_color) if hex_color and hex_color.startswith("#") else SAGE
    except Exception:
        fill = SAGE
    t = Table([[""]], colWidths=[size], rowHeights=[size])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("ROUNDEDCORNERS", [size / 2, size / 2, size / 2, size / 2]),
            ]
        )
    )
    return t


# ──────────────────────────── Content helpers ─────────────────────────────
def _keyword_line(lead: Dict[str, Any]) -> str:
    bits: List[str] = []
    for raw in (lead.get("style_prefs") or [])[:2]:
        bits.append(str(raw).replace("_", " ").strip())
    for raw in (lead.get("desired_feeling") or lead.get("color_prefs") or [])[:2]:
        label = str(raw).replace("_", " ").strip()
        if label and label.lower() not in {b.lower() for b in bits}:
            bits.append(label)
    if not bits:
        bits = ["Practical", "Calming", "Organized"]
    return "  ·  ".join(b.upper() for b in bits[:4])


def _need_icon(text: str) -> str:
    blob = (text or "").lower()
    for keys, kind in NEED_ICON_RULES:
        if any(k in blob for k in keys):
            return kind
    return "box"


def _need_title(text: str) -> str:
    raw = (text or "").strip()
    if " — " in raw:
        return raw.split(" — ", 1)[0].strip()
    if ":" in raw and len(raw.split(":", 1)[0]) <= 36:
        return raw.split(":", 1)[0].strip()
    if len(raw) <= 52:
        return raw
    return raw[:50].rsplit(" ", 1)[0]


def _space_needs(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(title, detail, icon) — organization needs, not bedroom décor categories."""
    out: List[Tuple[str, str, str]] = []
    seen = set()

    def add(title: str, detail: str, icon: str) -> None:
        key = title.strip().lower()
        if not title or key in seen:
            return
        seen.add(key)
        out.append((title.strip(), (detail or "").strip(), icon))

    for raw in (deliverable.get("needs") or []):
        text = str(raw or "").strip()
        if not text:
            continue
        add(_need_title(text), text, _need_icon(text))
        if len(out) >= 5:
            return out

    blob = " ".join(f"{t} {d}" for t, d, _ in out).lower()
    for key in (lead.get("storage_needs") or []):
        label = STORAGE.get(str(key), str(key).replace("_", " ").title())
        token = str(key).replace("_", " ").split()[0].lower()
        if token and token in blob:
            continue
        add(label, f"{label} get a labeled home on the existing shell.", _need_icon(label))
        if len(out) >= 5:
            return out

    if not out:
        for title, detail, icon in DEFAULT_NEEDS:
            add(title, detail, icon)
    return out[:5]


def _item_category(name: str) -> str:
    n = (name or "").lower()
    rules = (
        (("bin", "tote", "box"), "BINS"),
        (("basket",), "BASKETS"),
        (("shelf", "shelves", "shelving", "rack"), "SHELVING"),
        (("hook", "peg"), "HOOKS"),
        (("label", "sticker"), "LABELS"),
        (("light", "lamp"), "LIGHTING"),
        (("rug", "mat"), "FLOOR"),
        (("hamper", "laundry"), "LAUNDRY"),
        (("hanger", "rod"), "HANGING"),
        (("divider", "insert"), "DIVIDERS"),
        (("vacuum", "broom"), "TOOLS"),
        (("desk", "work"), "ORGANIZER"),
    )
    for keys, cat in rules:
        if any(k in n for k in keys):
            return cat
    return "ORGANIZER"


def _money(value: float) -> str:
    if value <= 0:
        return "—"
    if abs(value - round(value)) < 0.009:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _line_total(item: Dict[str, Any]) -> Tuple[float, float, float]:
    try:
        qty = float(item.get("qty", 1) or 1)
    except (TypeError, ValueError):
        qty = 1.0
    try:
        price = float(item.get("price", 0) or 0)
    except (TypeError, ValueError):
        price = 0.0
    return qty, price, qty * price


def _budget_range(lead: Dict[str, Any], deliverable: Dict[str, Any], layers: Dict[str, Any]) -> str:
    key = str(lead.get("budget") or "").strip()
    if key in BUDGET_LABELS:
        return BUDGET_LABELS[key]
    candidates = [
        ((layers.get("validation") or {}).get("budget_band") or {}).get("band"),
        deliverable.get("budget_note"),
    ]
    for raw in candidates:
        text = str(raw or "").strip()
        if not text:
            continue
        found = re.search(r"\$?\d[\d,]*\s*[–\-to]+\s*\$?\d[\d,]*", text)
        if found:
            return found.group(0).replace("to", "–")
        if text:
            return text
    return "Typical retail range"


# ──────────────────────────── Page chrome ─────────────────────────────
def _draw_logo(canvas, x: float, y: float, size: float = 16, stroke: Color = EMERALD) -> None:
    canvas.saveState()
    canvas.setStrokeColor(stroke)
    canvas.setLineWidth(1.4)
    s = size
    p = canvas.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + s * 0.5, y + s * 0.55)
    p.lineTo(x + s, y)
    p.lineTo(x + s, y - s * 0.55)
    p.lineTo(x, y - s * 0.55)
    p.close()
    canvas.drawPath(p, stroke=1, fill=0)
    p2 = canvas.beginPath()
    p2.moveTo(x + 2, y - s * 0.22)
    p2.curveTo(x + s * 0.28, y - s * 0.42, x + s * 0.5, y - s * 0.08, x + s * 0.72, y - s * 0.28)
    p2.curveTo(x + s * 0.85, y - s * 0.38, x + s * 0.92, y - s * 0.22, x + s - 1, y - s * 0.22)
    canvas.drawPath(p2, stroke=1, fill=0)
    canvas.restoreState()


def _draw_footer(canvas, page: int) -> None:
    canvas.saveState()
    y = FOOTER_H
    canvas.setStrokeColor(MINT)
    canvas.setLineWidth(1.6)
    canvas.line(0, y, PAGE_W, y)
    canvas.setFillColor(SOFT)
    canvas.rect(0, 0, PAGE_W, y, fill=1, stroke=0)
    canvas.setFillColor(SLATE_SOFT)
    canvas.setFont(_font("FSSans"), 6.1)
    if page == 1:
        canvas.drawString(MARGIN, 14, FOOTER_NOTE)
        canvas.drawRightString(PAGE_W - MARGIN, 14, "The FlowSpace Design Team")
    else:
        canvas.drawString(MARGIN, 14, "The FlowSpace Design Team  ·  Functional design  ·  Lasting value")
        canvas.drawRightString(PAGE_W - MARGIN, 14, f"Page {page}")
    canvas.restoreState()


def _draw_dashboard_header(canvas, title: str, vibe: str) -> None:
    canvas.saveState()
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(EMERALD)
    canvas.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)

    top = PAGE_H - 0.38 * inch
    _draw_logo(canvas, MARGIN, top, 15, EMERALD)
    canvas.setFillColor(SLATE)
    canvas.setFont(_font("FSSerif-Bold"), 12.5)
    canvas.drawString(MARGIN + 22, top - 2, "FlowSpace")
    canvas.setFillColor(SLATE_SOFT)
    canvas.setFont(_font("FSSans"), 5.8)
    canvas.drawString(MARGIN + 22, top - 12, TAGLINE)

    badge_w, badge_h = 142, 52
    bx = PAGE_W - MARGIN - badge_w
    by = PAGE_H - DASH_HEADER_H + 10
    canvas.setFillColor(EMERALD_DEEP)
    canvas.roundRect(bx, by, badge_w, badge_h, 7, fill=1, stroke=0)
    canvas.setFillColor(HexColor("#a7f3d0"))
    canvas.setFont(_font("FSSans-Semi"), 5.8)
    canvas.drawCentredString(bx + badge_w / 2, by + 38, "DESIGNED FOR")
    canvas.setFillColor(WHITE)
    canvas.setFont(_font("FSSans-Bold"), 8.0)
    canvas.drawCentredString(bx + badge_w / 2, by + 26, "HOW YOU LIVE")
    canvas.setFillColor(HexColor("#d1fae5"))
    canvas.setFont(_font("FSSans"), 5.3)
    canvas.drawCentredString(bx + badge_w / 2, by + 14, CALLOUT_LINES[0])
    canvas.drawCentredString(bx + badge_w / 2, by + 6, CALLOUT_LINES[1])

    left_bound = MARGIN + 108
    right_bound = bx - 10
    cx = (left_bound + right_bound) / 2.0
    label = title.upper()
    font_name = _font("FSSerif-Bold")
    size = 15.0
    while size > 10.0 and canvas.stringWidth(label, font_name, size) > (right_bound - left_bound):
        size -= 0.4
    canvas.setFillColor(SLATE)
    canvas.setFont(font_name, size)
    canvas.drawCentredString(cx, top - 1, label)
    canvas.setFillColor(EMERALD_DEEP)
    canvas.setFont(_font("FSSans-Semi"), 6.8)
    canvas.drawCentredString(cx, top - 16, vibe or "PRACTICAL  ·  CALMING  ·  ORGANIZED")
    canvas.restoreState()


def _draw_interior_header(canvas, title: str, kind: str = "interior") -> None:
    canvas.saveState()
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(EMERALD)
    canvas.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)
    top = PAGE_H - 0.28 * inch
    _draw_logo(canvas, MARGIN, top, 13, EMERALD)
    canvas.setFillColor(SLATE)
    canvas.setFont(_font("FSSerif-Bold"), 11.5)
    canvas.drawString(MARGIN + 20, top - 2, "FlowSpace")
    canvas.setFillColor(SLATE_SOFT)
    canvas.setFont(_font("FSSans"), 6.2)
    canvas.drawString(MARGIN + 92, top, title)
    canvas.setFillColor(EMERALD_DEEP)
    canvas.setFont(_font("FSSans-Semi"), 6.4)
    right = "BEFORE & AFTER" if kind == "compare" else "SHOPPING LIST  ·  DIY THIS WEEK"
    canvas.drawRightString(PAGE_W - MARGIN, top, right)
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - INT_HEADER_H + 4, PAGE_W - MARGIN, PAGE_H - INT_HEADER_H + 4)
    canvas.restoreState()


def _make_on_page(kind: str, title: str, vibe: str):
    def _on_page(canvas, doc):
        if kind == "dashboard":
            _draw_dashboard_header(canvas, title, vibe)
        else:
            _draw_interior_header(canvas, title, kind)
        _draw_footer(canvas, canvas.getPageNumber())

    return _on_page


# ──────────────────────────── Sections ─────────────────────────────
def _hero_block(
    img_bytes: Optional[bytes],
    width: float,
    height: float,
    kind: str = "organized",
) -> Table:
    s = _styles()
    data = coerce_image_bytes(img_bytes)
    if data:
        photo = _cover_image(data, width, height - 15)
        banner_text = HERO_BANNER_ORIGINAL if kind == "original" else HERO_BANNER_ORGANIZED
    else:
        photo = _cover_image(
            None,
            width,
            height - 15,
            missing_label=HERO_PLACEHOLDER_LABEL,
            missing_sublabel=HERO_PLACEHOLDER_SUB,
        )
        banner_text = HERO_BANNER_ORGANIZED
    banner = Table([[Paragraph(banner_text, s["banner"])]], colWidths=[width], rowHeights=[15])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), EMERALD),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    photo_h = height - 15
    stack = Table([[banner], [photo]], colWidths=[width], rowHeights=[15, photo_h])
    stack.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("BOX", (0, 0), (-1, -1), 0.7, EMERALD),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (0, 1), WHITE),
            ]
        )
    )
    return stack


def _needs_stack(needs: List[Tuple[str, str, str]], width: float) -> Table:
    s = _styles()
    rows: List[List[Any]] = []
    for title, detail, icon in needs:
        copy = detail if detail.lower() != title.lower() else ""
        cell = [Paragraph(_esc(title), s["needTitle"])]
        if copy:
            cell.append(Paragraph(_esc(_clip(copy, 90)), s["needSub"]))
        rows.append([IconBadge(icon, 20), cell])
    t = Table(rows, colWidths=[24, max(width - 24, 40)])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return t


def _paint_block(deliverable: Dict[str, Any], width: float) -> Optional[Table]:
    s = _styles()
    name = (deliverable.get("wall_color_name") or "").strip()
    code = (deliverable.get("wall_color_code") or "").strip()
    hex_color = (deliverable.get("wall_color_hex") or "").strip()
    if not (name or hex_color or code):
        return None
    note = (deliverable.get("wall_color_note") or OPTIONAL_PAINT_NOTE).strip()
    copy = [
        Paragraph("WALL COLOR SUGGESTION", s["kicker"]),
        Paragraph(_esc(name or OPTIONAL_PAINT_HEADING), s["label"]),
        Paragraph(_esc(code or "Optional"), s["needSub"]),
        Paragraph(_esc(_clip(note, 110)), s["muted"]),
    ]
    inner = Table([[copy, _swatch(hex_color or "#cfd7d3", 28)]], colWidths=[width - 40, 34])
    inner.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )
    return inner


def _budget_callout(range_label: str, width: float, *, compact: bool = True) -> Table:
    s = _styles()
    body = [
        Paragraph(f"BUDGET RANGE:  {_esc(range_label)}", s["budgetHead"]),
        Paragraph(
            "Full shopping list and DIY steps on page 2."
            if compact
            else "Items chosen to bring the biggest impact for your budget.",
            s["whiteTiny"],
        ),
    ]
    t = Table([[body]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), EMERALD_DEEP),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return t


def _sidebar(
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    layers: Dict[str, Any],
    width: float,
    space_name: str,
) -> List[Any]:
    s = _styles()
    bits: List[Any] = [Paragraph(f"{space_name.upper()} NEEDS", s["section"])]
    bits.append(_needs_stack(_space_needs(lead, deliverable), width))
    paint = _paint_block(deliverable, width)
    if paint:
        bits += [Spacer(1, 6), paint]
    bits += [Spacer(1, 7), _budget_callout(_budget_range(lead, deliverable, layers), width)]
    return bits


def _zone_copy(z: Dict[str, str]) -> str:
    return (z.get("desc") or z.get("why") or "Keep the existing shell; change only the org system.").strip()


def _zones_row(
    zones: List[Dict[str, str]],
    floor_plan: Optional[bytes],
    width: float,
) -> Table:
    s = _styles()
    left_w = width * 0.38
    right_w = width - left_w - 10
    if floor_plan:
        visual = [
            Paragraph("ZONE PLAN (TOP VIEW)", s["section"]),
            _cover_image(floor_plan, left_w, 1.55 * inch),
            Spacer(1, 3),
            Paragraph("From your photo — no invented dimensions.", s["muted"]),
        ]
    else:
        visual = [
            Paragraph("ZONE PLAN (TOP VIEW)", s["section"]),
            ZonePlan(zones or [], left_w, 1.55 * inch),
            Spacer(1, 3),
            Paragraph("Conceptual zone map — not a measured floor plan.", s["muted"]),
        ]

    items: List[List[Any]] = []
    use = (zones or [])[:5] or [
        {"title": "Landing Zone", "desc": "Drop daily items at the existing door path."},
        {"title": "Storage Zone", "desc": "Matching bins on the walls you already have."},
        {"title": "Circulation Zone", "desc": "Keep the walk path the photo already shows."},
    ]
    for i, z in enumerate(use, 1):
        items.append(
            [
                NumberBadge(i, size=12),
                [
                    Paragraph(_esc(z.get("title") or f"Zone {i}"), s["label"]),
                    Paragraph(_esc(_clip(_zone_copy(z), 140)), s["bodySmall"]),
                ],
            ]
        )
    listed = Table(items, colWidths=[16, max(right_w - 16, 40)])
    listed.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    right = [Paragraph("ROOM LAYOUT & ZONES", s["section"]), listed]
    t = Table([[visual, right]], colWidths=[left_w, right_w + 10])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ]
        )
    )
    return t


def _additional_views(
    views: Sequence[Optional[bytes]],
    zones: List[Dict[str, str]],
    width: float,
) -> Optional[Table]:
    s = _styles()
    provided: List[Tuple[int, bytes]] = []
    for i, raw in enumerate(views[:3]):
        data = coerce_image_bytes(raw)
        if data:
            provided.append((i, data))
    if not provided:
        return None
    n = len(provided)
    gap = 8
    card_w = (width - gap * (n - 1)) / n
    cells = []
    for idx, data in provided:
        z = zones[idx] if idx < len(zones) else {}
        label = (z.get("title") or f"View {idx + 1}").upper()
        body = [
            Paragraph(f"VIEW {idx + 1}  —  {_esc(label)}", s["cardCat"]),
            Spacer(1, 3),
            _cover_image(data, card_w - 8, 0.92 * inch),
        ]
        cells.append(_card(body, card_w, pad=5))
    widths = [card_w] * n
    t = Table([cells], colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -2), gap / 2),
                ("LEFTPADDING", (1, 0), (-1, -1), gap / 2),
                ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
            ]
        )
    )
    s_head = Paragraph("ADDITIONAL VIEWS", _styles()["section"])
    wrap = Table([[s_head], [t]], colWidths=[width])
    wrap.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return wrap


def _check_items(
    items: Sequence[str],
    *,
    numbered: bool = False,
    limit: int = 4,
    mark: str = "✓",
) -> List[Any]:
    s = _styles()
    use = [str(x).strip() for x in items if str(x).strip()][:limit]
    out: List[Any] = []
    for i, item in enumerate(use, 1):
        prefix = f"<b>{i}</b>" if numbered else mark
        out.append(Paragraph(f'<font color="#059669">{prefix}</font>  {_esc(item)}', s["check"]))
    return out


def _bottom_cards(
    strategy: List[str],
    actions: List[str],
    benefits: List[str],
    width: float,
) -> Table:
    s = _styles()
    gap = 8
    col_w = (width - gap * 2) / 3
    left = _card(
        [Paragraph("DESIGN STRATEGY", s["section"]), *_check_items(strategy or DEFAULT_STRATEGY)],
        col_w,
        pad=7,
    )
    mid = _card(
        [Paragraph("SIMPLE ACTION PLAN", s["section"]), *_check_items(actions or DEFAULT_ACTIONS, numbered=True)],
        col_w,
        pad=7,
    )
    right = _card(
        [Paragraph("BENEFITS", s["section"]), *_check_items(benefits or DEFAULT_BENEFITS)],
        col_w,
        pad=7,
        fill=MINT_BG,
        box=MINT,
    )
    t = Table([[left, mid, right]], colWidths=[col_w, col_w, col_w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (1, 0), gap),
                ("LEFTPADDING", (1, 0), (2, 0), 0),
            ]
        )
    )
    return t


def _compare_panel(
    img_bytes: Optional[bytes],
    width: float,
    height: float,
    banner: str,
    empty_label: str,
    empty_sub: str,
) -> Table:
    s = _styles()
    data = coerce_image_bytes(img_bytes)
    if data:
        photo = _cover_image(data, width, height)
    else:
        photo = _cover_image(
            None, width, height, missing_label=empty_label, missing_sublabel=empty_sub
        )
    head = Table([[Paragraph(banner, s["banner"])]], colWidths=[width], rowHeights=[15])
    head.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), EMERALD),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    stack = Table([[head], [photo]], colWidths=[width], rowHeights=[15, height])
    stack.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("BOX", (0, 0), (-1, -1), 0.7, EMERALD),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 1), (0, 1), WHITE),
            ]
        )
    )
    return stack


def _before_after_section(before: Optional[bytes], after: Optional[bytes], width: float, *, compact: bool = True) -> Table:
    gap = 8
    col_w = (width - gap) / 2
    photo_h = 2.05 * inch if compact else 6.55 * inch
    left = _compare_panel(
        before, col_w, photo_h,
        COMPARE_BEFORE_BANNER, COMPARE_BEFORE_EMPTY, COMPARE_BEFORE_EMPTY_SUB,
    )
    right = _compare_panel(
        after, col_w, photo_h,
        COMPARE_AFTER_BANNER, COMPARE_AFTER_EMPTY, COMPARE_AFTER_EMPTY_SUB,
    )
    t = Table([[left, right]], colWidths=[col_w, col_w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), gap),
                ("LEFTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ]
        )
    )
    return t


def _shopping_table(items: List[Dict[str, Any]], width: float) -> Table:
    s = _styles()
    rows = [[
        Paragraph("ITEM", s["th"]),
        Paragraph("QTY", s["thRight"]),
        Paragraph("EST. PRICE", s["thRight"]),
        Paragraph("SUBTOTAL", s["thRight"]),
    ]]
    total = 0.0
    for it in (items or [])[:12]:
        qty, price, sub = _line_total(it)
        total += sub
        name = str(it.get("name") or "Organizer")
        cat = _item_category(name)
        rows.append([
            Paragraph(f"<b>{_esc(name)}</b><br/><font size='6.2' color='#64748b'>{_esc(cat.title())}</font>", s["td"]),
            Paragraph(str(int(qty) if qty.is_integer() else qty), s["tdRight"]),
            Paragraph(_money(price) if price else "Typical", s["tdRight"]),
            Paragraph(_money(sub) if sub else "—", s["tdRight"]),
        ])
    if len(rows) == 1:
        rows.append([
            Paragraph("Shopping list will follow your plan.", s["muted"]),
            Paragraph("", s["td"]),
            Paragraph("", s["td"]),
            Paragraph("", s["td"]),
        ])
    rows.append([
        Paragraph("ESTIMATED TOTAL  ·  typical retail range", s["tdBold"]),
        "",
        "",
        Paragraph(_money(total) if total else "—", s["tdBoldRight"]),
    ])
    col_w = [width * 0.48, width * 0.12, width * 0.20, width * 0.20]
    table = Table(rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SOFT]),
        ("BACKGROUND", (0, -1), (-1, -1), MINT_BG),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (0, -1), (2, -1)),
    ]
    table.setStyle(TableStyle(style_cmds))
    return table


def _diy_columns(layers: Dict[str, Any], action_plan: List[str], width: float) -> Table:
    s = _styles()
    inst = layers.get("customer_instruction") or {}
    steps = [x for x in (inst.get("do_this_week") or action_plan or DEFAULT_ACTIONS) if x][:4]
    dont = [x for x in (inst.get("do_not") or []) if x][:4] or [
        "Do not add walls, windows, or doors.",
        "Do not invent room dimensions.",
        "Paint is optional — skip it unless it helps.",
    ]
    reset = [x.strip() for x in str(inst.get("weekly_reset") or "").split(",") if x.strip()]
    if len(reset) <= 1:
        blob = str(inst.get("weekly_reset") or "")
        reset = [p.strip() for p in re.split(r"[.;]", blob) if p.strip()]
    reset = [(r[:1].upper() + r[1:]) if r else r for r in reset]
    if not reset:
        reset = [
            "Return items to their labeled bin",
            "Clear the landing zone / floor path",
            "Wipe one work surface",
        ]
    start = inst.get("start_here") or (steps[0] if steps else "Start with the floor path, then label homes.")
    gap = 8
    col_w = (width - gap * 2) / 3
    week = _card(
        [
            Paragraph("THIS WEEK — DIY STEPS", s["section"]),
            Paragraph(_esc(_clip(str(start), 140)), s["muted"]),
            Spacer(1, 3),
            *_check_items(steps, numbered=True, limit=5),
            Spacer(1, 3),
            Paragraph("Typical org session — no construction.", s["cardMeta"]),
        ],
        col_w,
        pad=7,
    )
    avoid = _card(
        [
            Paragraph("DO NOT", s["section"]),
            *_check_items(dont, limit=4, mark="–"),
        ],
        col_w,
        pad=7,
    )
    weekly = _card(
        [
            Paragraph("10-MINUTE WEEKLY RESET", s["section"]),
            *_check_items(reset, limit=5),
            Spacer(1, 3),
            Paragraph("A short reset keeps the system — not a remodel.", s["muted"]),
        ],
        col_w,
        pad=7,
        fill=MINT_BG,
        box=MINT,
    )
    t = Table([[week, avoid, weekly]], colWidths=[col_w, col_w, col_w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (1, 0), gap),
            ]
        )
    )
    return t


# ──────────────────────────── Build ─────────────────────────────
def build_pdf(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Optional[bytes]],
) -> bytes:
    """
    Render the FlowSpace Blueprint PDF.

    `lead` — questionnaire/lead document
    `deliverable` — zones, needs, shopping_list, strategy, action_plan, …
    `images` — see ``pdf_images``: front_view (+ front_view_kind), floor_plan,
    view_1/2/3, before, after, customer_photos. Values must be image bytes, not URLs.
    """
    _register_fonts()
    images = normalize_pdf_images(images)
    buf = io.BytesIO()
    s = _styles()
    space_key = lead.get("space_type") or "space"
    space_name = space_label(space_key)
    title_text = plan_title(space_key)
    customer_name = lead.get("name") or "there"
    vibe = _keyword_line(lead)
    content_w = PAGE_W - 2 * MARGIN

    dash_frame = Frame(
        MARGIN,
        FOOTER_H + 0.06 * inch,
        content_w,
        PAGE_H - DASH_HEADER_H - FOOTER_H - 0.12 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=2,
        bottomPadding=2,
        showBoundary=0,
    )
    int_frame = Frame(
        MARGIN,
        FOOTER_H + 0.06 * inch,
        content_w,
        PAGE_H - INT_HEADER_H - FOOTER_H - 0.12 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=4,
        bottomPadding=2,
        showBoundary=0,
    )
    doc = BaseDocTemplate(
        buf,
        pagesize=LETTER,
        pageTemplates=[
            PageTemplate(id="dashboard", frames=[dash_frame], onPage=_make_on_page("dashboard", title_text, vibe)),
            PageTemplate(id="interior", frames=[int_frame], onPage=_make_on_page("interior", title_text, vibe)),
            PageTemplate(id="compare", frames=[int_frame], onPage=_make_on_page("compare", title_text, vibe)),
        ],
        title=f"{title_text} — FlowSpace Blueprint",
        author="FlowSpace",
    )

    layers = resolve_layers(lead, deliverable)
    zones = deliverable.get("zones") or []
    shopping = deliverable.get("shopping_list") or []
    strategy = deliverable.get("strategy") or []
    action_plan = list(deliverable.get("action_plan") or [])
    inst = layers.get("customer_instruction") or {}
    if inst.get("do_this_week"):
        action_plan = list(inst["do_this_week"])
    benefits = deliverable.get("benefits") or []
    intro = (
        deliverable.get("intro")
        or f"A calmer {space_name.lower()} — organized around the room you already have."
    )
    story: List[Any] = []

    # ── Page 1: dashboard ────────────────────────────────────────────
    story.append(Paragraph(_esc(_clip(intro, 160)), s["intro"]))
    story.append(Spacer(1, 6))

    left_w = content_w * 0.62
    right_w = content_w * 0.36
    hero_h = 3.22 * inch
    extra_views = [images.get("view_1"), images.get("view_2"), images.get("view_3")]
    if not any(coerce_image_bytes(v) for v in extra_views):
        hero_h = 3.72 * inch

    hero = _hero_block(
        images.get("front_view"),
        left_w,
        hero_h,
        kind=str(images.get("front_view_kind") or "organized"),
    )
    side = _sidebar(lead, deliverable, layers, right_w, space_name)
    top = Table([[hero, side]], colWidths=[left_w + 8, right_w])
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ]
        )
    )
    story.append(top)
    story.append(Spacer(1, 8))
    story.append(_zones_row(zones, images.get("floor_plan"), content_w))

    views = _additional_views(extra_views, zones, content_w)
    if views:
        story.append(Spacer(1, 7))
        story.append(views)

    story.append(Spacer(1, 8))
    story.append(_bottom_cards(strategy, action_plan, benefits, content_w))

    # ── Page 2: shopping + DIY ───────────────────────────────────────
    story.append(NextPageTemplate("interior"))
    story.append(PageBreak())

    story.append(Paragraph("CURATED SELECTIONS — SHOPPING LIST", s["section"]))
    story.append(
        Paragraph(
            f"Hi { _esc(customer_name) } — shop this kit, then follow this week's DIY. "
            f"{_esc(_clip(str(deliverable.get('budget_note') or ''), 120))}".strip(),
            s["muted"],
        )
    )
    story.append(Spacer(1, 4))
    story.append(_shopping_table(shopping, content_w))
    links = deliverable.get("shopping_links") or []
    if links:
        story.append(Spacer(1, 2))
        link_line = "   ·   ".join(
            f'<link href="{_esc(lnk.get("url") or "")}" color="#047857"><u>{_esc(lnk.get("name") or lnk.get("url") or "")}</u></link>'
            for lnk in links[:6]
            if lnk.get("name") or lnk.get("url")
        )
        if link_line:
            story.append(Paragraph(f"<b>Shopping Links</b>  {link_line}", s["bodySmall"]))
    story.append(Spacer(1, 4))
    story.append(
        _budget_callout(
            _budget_range(lead, deliverable, layers),
            content_w,
            compact=False,
        )
    )

    story.append(Spacer(1, 7))
    story.append(Paragraph("IMPLEMENTATION ROADMAP — SIMPLE ACTION PLAN", s["section"]))
    story.append(_diy_columns(layers, action_plan, content_w))

    notes = str(deliverable.get("notes") or "").strip()
    if notes and notes != DEFAULT_NOTES:
        story.append(Spacer(1, 5))
        story.append(Paragraph("NOTES &amp; TIPS", s["section"]))
        story.append(Paragraph(_esc(notes), s["muted"]))
    attachment_note = deliverable.get("attachment_note") or ""
    if attachment_note:
        story.append(Spacer(1, 3))
        story.append(Paragraph(_esc(attachment_note), s["bodySmall"]))

    before_bytes = coerce_image_bytes(images.get("before"))
    after_bytes = coerce_image_bytes(images.get("after"))
    if before_bytes or after_bytes:
        story.append(NextPageTemplate("compare"))
        story.append(PageBreak())
        story.append(Paragraph("BEFORE &amp; AFTER — YOUR SPACE, RE-ZONED", s["section"]))
        story.append(
            Paragraph(
                "Your original photo on the left. The organized view on the right — "
                "same windows and walls (~95%). Paint is optional — not applied in the visual. "
                "We do not invent an after image.",
                s["muted"],
            )
        )
        story.append(Spacer(1, 10))
        story.append(_before_after_section(before_bytes, after_bytes, content_w, compact=False))

    doc.build(story)
    return buf.getvalue()
