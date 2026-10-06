"""
FlowSpace Companion Guide PDF — the long-form file beside the Design Plan.

The primary visual is the Design Plan board (``image_board.build_image_board``);
``room_flow`` carries the zone map. This phone-friendly guide is modular
(``design_plan_standards.COMPANION_GUIDE_MODULES``), in this order:

  - Safety essentials and climate comfort (short lists)
  - Maintenance (the reset or the nursery bedtime ritual)
  - Styling rules (palette, what stays, how the room stays calm)
  - Designer assessment (needs, zone by zone, what stays, and the
    "why the FlowSpace zone approach helps" paragraph the Room Flow map prints)
  - The consolidated shopping list with links and one list total
  - One before | after page per source photo, only when a real photo exists

The Do Not list, extended notes, and full safety copy stay in the internal
record (``blueprint_consistency.internal_record``), not in this PDF.

Hard rules:
  - Windows and room proportions follow the customer photos.
  - Never invent footage, window counts, or measured callouts.
  - Floor plans only when the pipeline actually provides one.
  - Wall paint/color is an optional recommendation, not applied in the visual.
  - The list total matches the shopping lines. A lower kit range is rewritten.

Public API: build_pdf(lead=, deliverable=, images=) -> bytes
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image as PILImage
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
    CondPageBreak,
    FrameBreak,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from blueprint_consistency import SHOPPING_DISCLAIMER, companion_sections, reference_total_line
from blueprint_layers import BUDGET_LABELS, STORAGE
from design_plan_standards import (
    BRAND_CHAR,
    BRAND_GREEN,
    BRAND_OFF,
    BRAND_SAGE,
    BRAND_TINTS,
    COMPANION_MODULE_TITLES,
    COMPANION_NAME,
    DESIGN_PLAN_NAME,
    MONTSERRAT,
    TAGLINE,
)
from photo_contain import contain_rect
from room_flow import ZONE_APPROACH_HEADING, guide_outline_caption
from shopping_links import fallback_search_links
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

# ──────────────────────────── Palette (FlowSpace brand) ─────────────────────────────
EMERALD = HexColor(BRAND_GREEN)
EMERALD_DEEP = HexColor(BRAND_GREEN)
MINT = HexColor(BRAND_SAGE)
MINT_BG = HexColor(BRAND_TINTS["sage_light"])
SLATE = HexColor(BRAND_CHAR)
SLATE_MUTED = HexColor(BRAND_TINTS["muted"])
SLATE_SOFT = HexColor(BRAND_TINTS["muted"])
SURFACE = HexColor("#ffffff")
SOFT = HexColor(BRAND_OFF)
BORDER = HexColor(BRAND_TINTS["line"])
WHITE = colors.white
SAGE = HexColor(BRAND_SAGE)
INK = SLATE
MUTED = SLATE_MUTED
LINE = BORDER
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
    "Windows and room proportions follow your photos. "
    "We do not invent dimensions. Paint is optional — consider it only if it helps your goal."
)
OPTIONAL_PAINT_HEADING = "Optional paint — consider if it helps"
OPTIONAL_PAINT_NOTE = (
    "Optional paint — consider if it helps. Not applied in the visual. "
    "Consider this color only if it helps your organization goal."
)
FOOTER_NOTE = (
    "Note: Measurements are approximate. Adjust to your space as needed. "
    "Windows and room proportions follow your photos."
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
# Montserrat hierarchy. The FSSerif names are the display weights (light story, semibold titles).
_FONT_FILES = {
    "FSSerif": MONTSERRAT["light"],
    "FSSerif-Bold": MONTSERRAT["semibold"],
    "FSSerif-Italic": "Montserrat-Italic.ttf",
    "FSSans": MONTSERRAT["regular"],
    "FSSans-Medium": MONTSERRAT["medium"],
    "FSSans-Semi": MONTSERRAT["semibold"],
    "FSSans-Bold": MONTSERRAT["bold"],
    "FSSans-Italic": "Montserrat-Italic.ttf",
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


_CHILD_TURNING = re.compile(
    r"\b([A-Z][a-z]{2,})\s+(?:is\s+turning|just\s+turned|turned|turns)\b"
    r"|\bAs\s+([A-Z][a-z]{2,})\s+grows\b"
    r"|\bfor\s+([A-Z][a-z]{2,}),?\s+who\s+is\b"
)
# "Nicholas's nursery" or "Nicholas' nursery", after curly apostrophes are flattened.
_CHILD_POSSESSIVE = re.compile(r"\b([A-Z][a-z]{2,})(?:'s|')\s+nursery\b")
_CURLY_APOSTROPHE = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u2032": "'"})


def _flatten_apostrophes(text: str) -> str:
    return str(text or "").translate(_CURLY_APOSTROPHE)


def _plan_copy(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> str:
    """Customer plan and outcome text. Not image prompts or review notes."""
    chunks = [str(lead.get(key) or "") for key in ("goals", "must_stay", "notes", "daily_improvement")]
    for key in ("intro", "summary", "notes"):
        chunks.append(str(deliverable.get(key) or ""))
    for key in ("strategy", "benefits", "needs"):
        for item in deliverable.get(key) or []:
            chunks.append(str(item))
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            chunks.append(str(zone.get("title") or ""))
            chunks.append(str(zone.get("desc") or ""))
        else:
            chunks.append(str(zone))
    return _flatten_apostrophes("\n".join(chunks))


def _customer_first_name(lead: Dict[str, Any]) -> str:
    """Greet every customer by first name only."""
    parts = str(lead.get("name") or "").strip().split()
    return parts[0] if parts else ""


def _child_first_name(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]] = None,
) -> str:
    """Child named by the plan.

    Matches "Nicholas is turning one" and a possessive already in the
    outcome, such as "Nicholas's nursery". A curly apostrophe counts.
    The customer's own name is not treated as the child.
    """
    lead = lead or {}
    explicit = str(lead.get("child_name") or "").strip()
    if explicit:
        first = explicit.split()[0]
        if first[:1].isalpha():
            return first[:1].upper() + first[1:]
    blob = _plan_copy(lead, deliverable or {})
    turning = _CHILD_TURNING.search(blob)
    if turning:
        return next(group for group in turning.groups() if group)
    customer = _customer_first_name(lead).lower()
    for match in _CHILD_POSSESSIVE.finditer(blob):
        name = match.group(1)
        if name.lower() != customer:
            return name
    return ""


def customer_project_title(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]] = None,
) -> str:
    """Nursery title the customer sees. Empty for every other room.

    A nursery plan that names the child — "Nicholas is turning one" or
    "Nicholas's nursery" in the outcome — becomes "Nicholas's Nursery".
    A nursery with no child name becomes "Nursery". Other rooms keep
    their own plan title at the call site.
    """
    from space_rails import is_nursery_space

    if not is_nursery_space(lead):
        return ""
    child = _child_first_name(lead, deliverable)
    if child:
        return f"{child}'s Nursery"
    return "Nursery"


PAGE_W, PAGE_H = LETTER
# Narrow page so body type stays readable when a phone fits the page to the screen.
PHONE_W, PHONE_H = 390, 744
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
        "guideKicker": ParagraphStyle(
            "guideKicker", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=11, leading=14, textColor=EMERALD_DEEP, spaceAfter=4,
        ),
        "guideTitle": ParagraphStyle(
            "guideTitle", parent=base["BodyText"], fontName=_font("FSSerif-Bold"),
            fontSize=20, leading=24, textColor=SLATE, spaceAfter=6,
        ),
        "guideStory": ParagraphStyle(
            "guideStory", parent=base["BodyText"], fontName=_font("FSSerif"),
            fontSize=14, leading=18, textColor=EMERALD_DEEP, spaceBefore=2, spaceAfter=8,
        ),
        "guideH": ParagraphStyle(
            "guideH", parent=base["BodyText"], fontName=_font("FSSans-Bold"),
            fontSize=14, leading=17, textColor=SLATE, spaceBefore=7, spaceAfter=2,
            keepWithNext=True,
        ),
        "guideH3": ParagraphStyle(
            "guideH3", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=12, leading=15, textColor=EMERALD_DEEP, spaceBefore=4, spaceAfter=1,
            keepWithNext=True,
        ),
        "guideBody": ParagraphStyle(
            "guideBody", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=12, leading=15.5, textColor=INK, spaceAfter=2,
        ),
        "guideLink": ParagraphStyle(
            "guideLink", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=11, leading=14, textColor=INK, spaceAfter=1,
        ),
        # Ten curated rows, the total, and the link note share one phone page.
        "shopItem": ParagraphStyle(
            "shopItem", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=10.6, leading=12.8, textColor=INK, spaceBefore=0, spaceAfter=6,
        ),
        "shopTotal": ParagraphStyle(
            "shopTotal", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=12, leading=14, textColor=EMERALD_DEEP, spaceBefore=2, spaceAfter=1,
            keepWithNext=True,
        ),
        "shopNote": ParagraphStyle(
            "shopNote", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=10.6, leading=12.8, textColor=INK, spaceAfter=1,
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


def _fit_image(
    src: Optional[bytes],
    width: float,
    height: float,
    *,
    missing_label: str = "Image not provided",
    missing_sublabel: str = "",
    fill: bool = False,
) -> Any:
    """Fit a photo into a box. Room photos contain (no crop). Missing stays a labeled panel."""
    data = coerce_image_bytes(src)
    if not data:
        return _placeholder(width, height, missing_label, missing_sublabel)
    try:
        return ClippedPhoto(data, width, height, fill=fill)
    except Exception:
        return _placeholder(width, height, "Image unavailable")


PDF_PHOTO_DPI = 200
PDF_PHOTO_JPEG_QUALITY = 85
# Phone pages print on letter paper scaled up by this much; photos hold PDF_PHOTO_DPI there.
LETTER_PRINT_SCALE = max(1.0, min(PAGE_W / PHONE_W, PAGE_H / PHONE_H))


def _is_graphic(img: PILImage.Image) -> bool:
    """Flat-color art (zone map, board) keeps lossless PNG; photos go to JPEG."""
    probe = img.convert("RGB")
    probe.thumbnail((256, 256), PILImage.NEAREST)
    return probe.getcolors(maxcolors=2048) is not None


def pdf_photo_bytes(data: bytes, draw_w_pt: float, draw_h_pt: float, *, dpi: int = PDF_PHOTO_DPI) -> bytes:
    """Bytes to embed for a photo drawn at ``draw_w_pt`` × ``draw_h_pt`` points.

    Resampled to ``dpi`` at its letter-print size (never upscaled). Photos become
    JPEG; flat graphics and images with real transparency stay PNG. Returns the
    original bytes when re-encoding would not make them smaller.
    """
    try:
        img = PILImage.open(io.BytesIO(data))
        img.load()
    except Exception:
        return data
    iw, ih = img.size
    target = max(draw_w_pt / iw, draw_h_pt / ih) * LETTER_PRINT_SCALE * dpi / 72.0
    scale = min(1.0, target)
    size = (max(1, round(iw * scale)), max(1, round(ih * scale)))
    alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if alpha:
        rgba = img.convert("RGBA")
        alpha = rgba.getchannel("A").getextrema()[0] < 255
    buf = io.BytesIO()
    if alpha or _is_graphic(img):
        out = img.convert("RGBA" if alpha else "RGB")
        if scale < 1.0:
            out = out.resize(size, PILImage.LANCZOS)
        out.save(buf, format="PNG", optimize=True)
    else:
        out = img.convert("RGB")
        if scale < 1.0:
            out = out.resize(size, PILImage.LANCZOS)
        out.save(buf, format="JPEG", quality=PDF_PHOTO_JPEG_QUALITY, optimize=True)
    encoded = buf.getvalue()
    return encoded if len(encoded) < len(data) else data


class ClippedPhoto(Flowable):
    """Draw a photo inside a box. The default contains the full frame."""

    def __init__(self, data: bytes, width: float, height: float, fill: bool = False):
        super().__init__()
        self.data = data
        self.width = width
        self.height = max(height, 24)
        self.fill = fill
        iw, ih = ImageReader(io.BytesIO(data)).getSize()
        if iw <= 0 or ih <= 0:
            raise ValueError("empty")
        # Geometry uses the source pixel size; only the embedded bytes are resampled.
        self._iw, self._ih = iw, ih
        dw, dh = self.placed_size()
        self._ir = ImageReader(io.BytesIO(pdf_photo_bytes(data, dw, dh)))

    def placed_size(self) -> Tuple[float, float]:
        """Pixel size of the drawn image. Contain stays inside the box."""
        if self.fill:
            scale = max(self.width / self._iw, self.height / self._ih)
        else:
            scale = min(self.width / self._iw, self.height / self._ih)
        return (self._iw * scale, self._ih * scale)

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
        dw, dh = self.placed_size()
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


def _page_box(canvas):
    page_w, page_h = canvas._pagesize
    inset = 18 if page_w < 500 else MARGIN
    return page_w, page_h, inset


def _draw_footer(canvas, page: int) -> None:
    canvas.saveState()
    page_w, _page_h, inset = _page_box(canvas)
    y = FOOTER_H
    canvas.setStrokeColor(MINT)
    canvas.setLineWidth(1.6)
    canvas.line(0, y, page_w, y)
    canvas.setFillColor(SOFT)
    canvas.rect(0, 0, page_w, y, fill=1, stroke=0)
    canvas.setFillColor(SLATE_SOFT)
    canvas.setFont(_font("FSSans"), 8 if page_w < 500 else 6.1)
    note = "The FlowSpace Design Team · Windows and room proportions follow your photos."
    if page_w < 500:
        canvas.drawString(inset, 12, note)
        canvas.drawRightString(page_w - inset, 12, str(page))
    elif page == 1:
        canvas.drawString(inset, 14, FOOTER_NOTE)
        canvas.drawRightString(page_w - inset, 14, "The FlowSpace Design Team")
    else:
        canvas.drawString(inset, 14, "The FlowSpace Design Team  ·  Functional design  ·  Lasting value")
        canvas.drawRightString(page_w - inset, 14, f"Page {page}")
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
    page_w, page_h, inset = _page_box(canvas)
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    canvas.setFillColor(EMERALD)
    canvas.rect(0, page_h - 4, page_w, 4, fill=1, stroke=0)
    top = page_h - 0.28 * inch
    _draw_logo(canvas, inset, top, 13, EMERALD)
    canvas.setFillColor(SLATE)
    canvas.setFont(_font("FSSerif-Bold"), 11.5)
    canvas.drawString(inset + 20, top - 2, "FlowSpace")
    canvas.setFillColor(EMERALD_DEEP)
    canvas.setFont(_font("FSSans-Semi"), 8 if page_w < 500 else 6.4)
    if kind == "compare":
        right = "BEFORE & AFTER"
    elif kind == "guide":
        right = "COMPANION GUIDE"
    else:
        right = "SHOPPING LIST"
    canvas.drawRightString(page_w - inset, top, right)
    if page_w >= 500:
        canvas.setFillColor(SLATE_SOFT)
        canvas.setFont(_font("FSSans"), 6.2)
        canvas.drawString(inset + 92, top, title)
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(inset, page_h - INT_HEADER_H + 4, page_w - inset, page_h - INT_HEADER_H + 4)
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
        photo = _fit_image(data, width, height - 15)
        banner_text = HERO_BANNER_ORIGINAL if kind == "original" else HERO_BANNER_ORGANIZED
    else:
        photo = _fit_image(
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


def _is_keep_existing_paint(deliverable: Dict[str, Any]) -> bool:
    name = (deliverable.get("wall_color_name") or "").strip().lower()
    if "keep existing" in name or "no paint" in name:
        return True
    hex_color = (deliverable.get("wall_color_hex") or "").strip()
    code = (deliverable.get("wall_color_code") or "").strip()
    return not (name or hex_color or code)


def _paint_block(deliverable: Dict[str, Any], width: float) -> Optional[Table]:
    s = _styles()
    name = (deliverable.get("wall_color_name") or "").strip()
    code = (deliverable.get("wall_color_code") or "").strip()
    hex_color = (deliverable.get("wall_color_hex") or "").strip()
    if _is_keep_existing_paint(deliverable):
        return None
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
            _fit_image(floor_plan, left_w, 1.55 * inch),
            Spacer(1, 3),
            Paragraph("From your photo — no invented dimensions.", s["muted"]),
        ]
    else:
        visual = [
            Paragraph("ZONE PLAN (TOP VIEW)", s["section"]),
            ZonePlan(zones or [], left_w, 1.55 * inch),
            Spacer(1, 3),
            Paragraph("Approximate room outline. Furniture footprints and zones are approximate.", s["muted"]),
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
            _fit_image(data, card_w - 8, 0.92 * inch),
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


def _room_photo_flowable(
    data: bytes,
    max_width: float,
    max_height: float,
) -> Any:
    """Contain a room photo in ``max_width`` × ``max_height`` and size the frame to that fit.

    The flowable is as tall as the contained image, so a portrait phone photo
    is not locked into a short wide crop window.
    """
    reader = ImageReader(io.BytesIO(data))
    iw, ih = reader.getSize()
    if iw <= 0 or ih <= 0:
        raise ValueError("empty")
    _ox, _oy, _dw, dh = contain_rect(iw, ih, max_width, max_height)
    return ClippedPhoto(data, max_width, max(dh, 24), fill=False)


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
        try:
            photo = _room_photo_flowable(data, width, height)
        except Exception:
            photo = _fit_image(None, width, height, missing_label="Image unavailable")
    else:
        photo = _fit_image(
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


def _guide_frame_height() -> float:
    """Usable height of one companion-guide frame, after header, footer, and padding."""
    return PHONE_H - INT_HEADER_H - FOOTER_H - 0.12 * inch - 6


# Two banners, the gap between the panels, and a little slack so the pair never spills.
_COMPARE_CHROME = 2 * 15 + 16 + 10


def _flowables_height(flowables: Sequence[Any], width: float) -> float:
    total = 0.0
    for flowable in flowables:
        _w, h = flowable.wrap(width, 10_000)
        total += h + flowable.getSpaceBefore() + flowable.getSpaceAfter()
    return total


def _compare_photo_height(frame_h: float, text_h: float = 0.0) -> float:
    """Photo height that lets the heading, copy, and both photos fill one page."""
    fitted = (frame_h - text_h - _COMPARE_CHROME) / 2.0
    return max(120.0, fitted)


# A page is "complete" at or above this share of its frame; layout avoids leaving less.
MIN_PAGE_FILL = 0.40
# Smallest photo height (pt) a before/after pair may shrink to so it can share a page.
MIN_SHARED_PHOTO_H = 150.0


class _ListBlock(KeepTogether):
    """Keeps a list whole on the next page, unless that would leave this page mostly empty.

    The rows flow from here instead when at least ``min_room`` of the frame is
    free and either the spilled tail alone fills ``MIN_PAGE_FILL`` of a page, or
    moving the list would leave this page under ``MIN_PAGE_FILL``. A full-page
    before/after can need more room than a short tail leaves, so a following
    block is not counted on to fill it. Inner ``KeepTogether`` groups (heading +
    first rows, last rows + total) still travel together.
    """

    def __init__(self, flowables: List[Any], frame_h: float, *, followed: bool, min_room: float = 0.35) -> None:
        super().__init__(flowables)
        self._frame_h = frame_h
        self._followed = followed
        self._min_room_pt = frame_h * min_room

    def wrap(self, aW: float, aH: float) -> Tuple[float, float]:
        width, forced = super().wrap(aW, aH)
        # Nested KeepTogether groups report a forced-split height; measure their rows instead.
        groups = [
            list(flowable._content) if isinstance(flowable, KeepTogether) else [flowable]
            for flowable in self._content
        ]
        self._heights = [_flowables_height(group, aW) for group in groups]
        self._H = sum(self._heights)
        self._H0 = self._heights[0] if self._heights else 0
        return width, forced

    def _balanced_cut(self, aH: float) -> Optional[int]:
        """Pieces to keep here so this page and the next both reach ``MIN_PAGE_FILL``."""
        need = MIN_PAGE_FILL * self._frame_h
        low = max(0.0, need - (self._frame_h - aH))
        high = min(aH, self._H - need)
        if low > high:
            return None
        used = 0.0
        for index, height in enumerate(self._heights):
            used += height
            if used > high:
                return None
            if used >= low:
                return index + 1
        return None

    def split(self, aW: float, aH: float) -> List[Any]:
        if getattr(self, "_wrapInfo", None) != (aW, aH):
            self.wrap(aW, aH)
        spill_fills = (self._H - aH) >= MIN_PAGE_FILL * self._frame_h
        page_stays_full = (self._frame_h - aH) >= MIN_PAGE_FILL * self._frame_h
        fits_next_page = self._H <= self._frame_h
        if self._H > aH and aH >= self._min_room_pt and (spill_fills or not page_stays_full or not fits_next_page):
            pieces = list(self._content)
            cut = None if spill_fills else self._balanced_cut(aH)
            if cut is not None and 0 < cut < len(pieces):
                pieces = [*pieces[:cut], FrameBreak(), *pieces[cut:]]
        else:
            pieces = super().split(aW, aH)
        # The frame adds the first piece without splitting it, and a KeepTogether
        # always asks to split, so a leading group is unpacked.
        if pieces and isinstance(pieces[0], KeepTogether):
            pieces = [*pieces[0]._content, *pieces[1:]]
        return pieces


class _ComparePage(Flowable):
    """Heading, copy, and a before/after pair sized to the room left in the frame.

    Photos grow to fill a fresh page. After a short page tail they shrink to
    share that page, down to ``MIN_SHARED_PHOTO_H``; below that the block
    moves to the next page.
    """

    def __init__(
        self,
        text: List[Any],
        before: Optional[bytes],
        after: Optional[bytes],
        width: float,
        frame_h: float,
        **panel: Any,
    ) -> None:
        super().__init__()
        self._text = text
        self._before = before
        self._after = after
        self._width = width
        self._frame_h = frame_h
        self._panel = panel
        self._table: Optional[Table] = None

    def _build(self, avail: float) -> Optional[Table]:
        shared = avail < self._frame_h - 12
        text = [*([Spacer(1, 14)] if shared else []), *self._text, Spacer(1, 8)]
        text_h = _flowables_height(text, self._width)
        full = _compare_photo_height(self._frame_h, text_h)
        photo_h = min(full, (avail - text_h - _COMPARE_CHROME) / 2.0)
        if photo_h < min(full, MIN_SHARED_PHOTO_H):
            return None
        pair = _before_after_section(
            self._before, self._after, self._width, compact=False, photo_h=photo_h, **self._panel
        )
        table = Table([[text], [pair]], colWidths=[self._width])
        table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    def wrap(self, aW: float, aH: float) -> Tuple[float, float]:
        self._table = self._build(aH)
        if self._table is None:
            return aW, aH + 1
        return self._table.wrap(aW, aH)

    def split(self, aW: float, aH: float) -> List[Any]:
        return []

    def draw(self) -> None:
        if self._table is not None:
            self._table.drawOn(self.canv, 0, 0)


class _GuideDoc(BaseDocTemplate):
    """Records how far down each page the content reaches, for the page-fill check."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.page_fill: Dict[int, float] = {}

    def afterFlowable(self, flowable: Any) -> None:
        frame = getattr(self, "frame", None)
        if frame is None:
            return
        top = frame._y1 + frame._height - frame._topPadding
        usable = frame._height - frame._topPadding - frame._bottomPadding
        if usable <= 0:
            return
        used = max(0.0, min(1.0, (top - frame._y) / usable))
        self.page_fill[self.page] = max(self.page_fill.get(self.page, 0.0), used)

    def fills(self) -> List[float]:
        return [self.page_fill.get(i, 0.0) for i in range(1, self.page + 1)]


def _before_after_section(
    before: Optional[bytes],
    after: Optional[bytes],
    width: float,
    *,
    compact: bool = True,
    before_banner: str = COMPARE_BEFORE_BANNER,
    after_banner: str = COMPARE_AFTER_BANNER,
    photo_h: Optional[float] = None,
) -> Table:
    # Stacked, full width, so a phone does not have to pinch a side-by-side pair.
    # ``photo_h`` is a maximum. Each photo then contains at its own ratio.
    if photo_h is None:
        photo_h = 2.15 * inch if compact else 3.15 * inch
    left = _compare_panel(
        before, width, photo_h,
        before_banner, COMPARE_BEFORE_EMPTY, COMPARE_BEFORE_EMPTY_SUB,
    )
    right = _compare_panel(
        after, width, photo_h,
        after_banner, COMPARE_AFTER_EMPTY, COMPARE_AFTER_EMPTY_SUB,
    )
    panel_h = 15 + photo_h
    t = Table([[left], [right]], colWidths=[width], rowHeights=[panel_h, panel_h])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 0),
            ]
        )
    )
    t.splitByRow = 0
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
        Paragraph("Illustrative reference total", s["tdBold"]),
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


def _shopping_blocks(
    items: List[Dict[str, Any]],
    links: Optional[Sequence[Dict[str, str]]] = None,
) -> List[Any]:
    """One item per block, with its link, so the list stays readable on a phone."""
    s = _styles()
    flows: List[Any] = []
    rows = [it for it in (items or []) if isinstance(it, dict)][:12]
    if not rows:
        flows.append(Paragraph("Shopping list will follow your plan.", s["guideBody"]))
        return flows
    by_name = {
        str(link.get("name") or "").strip().lower(): link
        for link in (links or [])
        if isinstance(link, dict)
    }
    for it in rows:
        qty, price, sub = _line_total(it)
        name = str(it.get("name") or "Organizer")
        qty_label = str(int(qty) if float(qty).is_integer() else qty)
        price_label = _money(price) if price else "Typical"
        sub_label = _money(sub) if sub else "—"
        link = by_name.get(name.strip().lower(), {}) or {}
        if not link and by_name and it.get("name"):
            # A curated list that names this item differently still gets a labeled search, not a bare row.
            link = (fallback_search_links({"shopping_list": [it]}) or [{}])[0]
        url = str(link.get("url") or "").strip()
        link_type = str(link.get("link_type") or "").strip().lower()
        link_label = str(link.get("label") or "").strip()
        retailer = str(link.get("retailer") or "Target").strip() or "Target"
        if not link_label and url:
            link_label = f"Search at {retailer}" if link_type == "search" else f"View at {retailer}"
        title = f"<b>{_esc(name)}</b>"
        if url and link_label:
            title = (
                f"<b>{_esc(name)}</b><br/>"
                f'<link href="{_esc(url)}" color="#047857"><u>{_esc(link_label)}</u></link>'
            )
        elif url:
            title = f'<link href="{_esc(url)}" color="#047857"><u><b>{_esc(name)}</b></u></link>'
        flows.append(
            Paragraph(
                f"{title}<br/>Qty {qty_label} · {price_label} each · {sub_label}",
                s["shopItem"],
            )
        )
    return flows


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
            Paragraph("DIY STEPS", s["section"]),
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
            Paragraph("QUICK RESET", s["section"]),
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


# ──────────────────────────── Companion Guide modules ─────────────────────────────
_MODULE_PHRASES = {
    "safety": "safety",
    "climate": "climate comfort",
    "maintenance": "maintenance",
    "styling": "styling rules",
    "assessment": "the designer assessment",
    "shopping": "the shopping list",
    "views": "each before-and-after view",
}


def _module_phrase(modules: Sequence[str]) -> str:
    phrases = [_MODULE_PHRASES[m] for m in modules if m in _MODULE_PHRASES]
    if not phrases:
        return "the plan's practical notes"
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + ", and " + phrases[-1]


def _bullets(lines: Sequence[str], style) -> List[Any]:
    return [Paragraph(f"• {_esc(line)}", style) for line in lines if str(line).strip()]


def _module_flowables(module: str, sections: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    """Text modules of the guide. Shopping and before/after pages are laid out by the caller."""
    title = COMPANION_MODULE_TITLES.get(module, module.upper())
    if module == "safety":
        return [Paragraph(title, s["guideH"]), *_bullets(sections["safety_essentials"], s["guideBody"])]
    if module == "climate":
        return [Paragraph(title, s["guideH"]), *_bullets(sections["climate_essentials"], s["guideBody"])]
    if module == "maintenance":
        body = [p.strip() for p in str(sections.get("maintenance") or "").split("\n\n") if p.strip()]
        if not body:
            return []
        out: List[Any] = [Paragraph(title, s["guideH"])]
        reset_title = str(sections.get("reset_title") or "").strip()
        if reset_title:
            out.append(Paragraph(_esc(reset_title), s["guideH3"]))
        out.extend(Paragraph(_esc(p), s["guideBody"]) for p in body)
        return out
    if module == "styling":
        rules = sections.get("styling") or []
        return [Paragraph(title, s["guideH"]), *_bullets(rules, s["guideBody"])] if rules else []
    if module == "assessment":
        assessment = sections.get("assessment") or {}
        out = [Paragraph(title, s["guideH"])]
        needs = assessment.get("needs") or []
        if needs:
            out.append(Paragraph("What the room needed", s["guideH3"]))
            out.extend(_bullets(needs, s["guideBody"]))
        zones = assessment.get("zones") or []
        if zones:
            out.append(Paragraph("Zone by zone", s["guideH3"]))
            for zone in zones:
                anchor = f" · {_esc(zone['object'])}" if zone.get("object") else ""
                out.append(
                    Paragraph(
                        f'<font name="{_font("FSSans-Semi")}">{_esc(zone["number"])} {_esc(zone["title"])}</font>{anchor}. {_esc(zone["job"])}',
                        s["guideBody"],
                    )
                )
        kept = assessment.get("kept") or []
        if kept:
            out.append(Paragraph("What stays", s["guideH3"]))
            out.append(Paragraph(_esc(", ".join(kept)) + ".", s["guideBody"]))
        out.append(Paragraph(ZONE_APPROACH_HEADING, s["guideH3"]))
        out.append(Paragraph(_esc(assessment.get("why") or sections.get("why") or ""), s["guideBody"]))
        return out
    return []


# ──────────────────────────── Build ─────────────────────────────
def build_pdf(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Optional[bytes]],
) -> bytes:
    """
    Render the companion guide PDF.

    `lead` — questionnaire/lead document
    `deliverable` — zones, needs, shopping_list, strategy, action_plan, …
    `images` — see ``pdf_images``. The before | after page uses real bytes only.
    The visual board is a separate portrait PNG from ``build_image_board``.
    """
    return _render_companion(lead=lead, deliverable=deliverable, images=images)[0]


def _render_companion(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Optional[bytes]],
) -> Tuple[bytes, List[float]]:
    _register_fonts()
    images = normalize_pdf_images(images)
    sections, deliverable = companion_sections(lead, deliverable)
    buf = io.BytesIO()
    s = _styles()
    space_key = lead.get("space_type") or "space"
    title_text = customer_project_title(lead, deliverable) or plan_title(space_key)
    customer_name = lead.get("name") or "there"
    vibe = _keyword_line(lead)
    page_w, page_h = PHONE_W, PHONE_H
    inset = 18
    content_w = page_w - 2 * inset

    int_frame = Frame(
        inset,
        FOOTER_H + 0.06 * inch,
        content_w,
        page_h - INT_HEADER_H - FOOTER_H - 0.12 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=4,
        bottomPadding=2,
        showBoundary=0,
    )
    doc = _GuideDoc(
        buf,
        pagesize=(page_w, page_h),
        pageTemplates=[
            PageTemplate(id="guide", frames=[int_frame], onPage=_make_on_page("guide", title_text, vibe)),
            PageTemplate(id="compare", frames=[int_frame], onPage=_make_on_page("compare", title_text, vibe)),
        ],
        title=f"{title_text} — FlowSpace {COMPANION_NAME}",
        author="FlowSpace",
    )

    modules = sections.get("modules") or []
    story: List[Any] = []
    story.append(Paragraph(_esc(title_text), s["guideTitle"]))
    story.append(Paragraph(COMPANION_NAME.upper(), s["guideKicker"]))
    if sections.get("story"):
        story.append(Paragraph(_esc(sections["story"]), s["guideStory"]))
    story.append(
        Paragraph(
            f"Hi {_esc(_customer_first_name(lead) or 'there')}. Start with the {DESIGN_PLAN_NAME} and the Room Flow map "
            "to see the room's overall plan and organization. "
            f"{_esc(guide_outline_caption(lead, deliverable))} "
            f"This {COMPANION_NAME} holds the practical detail: {_module_phrase(modules)}.",
            s["guideBody"],
        )
    )
    for module in modules:
        story.extend(_module_flowables(module, sections, s))

    items = _shopping_blocks(deliverable.get("shopping_list") or [], sections["links"])
    total_line = reference_total_line(str(sections["list_total"]))
    tail: List[Any] = [Paragraph(_esc(total_line), s["shopTotal"])] if total_line else []
    if sections["stated_budget"]:
        tail.append(Paragraph(f"Your stated budget: {_esc(sections['stated_budget'])}.", s["shopNote"]))
    tail.append(Paragraph(_esc(SHOPPING_DISCLAIMER), s["shopNote"]))
    if sections["links"]:
        if sections["links_are_search"]:
            tail.append(
                Paragraph(
                    "Links open a labeled retailer search. Confirm the exact product before you buy.",
                    s["shopNote"],
                )
            )
        else:
            tail.append(
                Paragraph(
                    "Product pages are linked where verified; search links are labeled. Confirm stock and price before you buy.",
                    s["shopNote"],
                )
            )
    frame_h = _guide_frame_height()
    # The heading never sits alone at a page foot, and the total and link note never
    # sit alone at a page top: the first and last rows travel with them.
    head_rows = min(2, max(0, len(items) - 2))
    shopping: List[Any] = [
        KeepTogether([Paragraph("SHOPPING LIST", s["guideH"]), *items[:head_rows]]),
        *items[head_rows:-2],
        KeepTogether([*items[-2:], *tail]),
    ]
    show_views = "views" in modules
    source_pairs = (images.get("source_pairs") or []) if show_views else []
    has_compare = show_views and bool(
        (isinstance(source_pairs, list) and len(source_pairs) >= 2)
        or coerce_image_bytes(images.get("after"))
        or coerce_image_bytes(images.get("before"))
    )
    if "shopping" in modules:
        # One consolidated list that moves to the next page whole, unless that would
        # leave this page mostly empty.
        story.append(_ListBlock(shopping, frame_h, followed=has_compare))
    if not has_compare:
        doc.build(story)
        return buf.getvalue(), doc.fills()

    def _compare_page(text: List[Any], before: Optional[bytes], after: Optional[bytes], **panel: Any) -> None:
        story.append(NextPageTemplate("compare"))
        story.append(_ComparePage(text, before, after, content_w, frame_h, **panel))

    if isinstance(source_pairs, list) and len(source_pairs) >= 2:
        # One before|after page per required room photo. A missing after stays
        # empty — it is not replaced by another source or a hero crop.
        any_missing = any(not coerce_image_bytes(pair.get("after")) for pair in source_pairs if isinstance(pair, dict))
        for index, pair in enumerate(source_pairs):
            if not isinstance(pair, dict):
                continue
            from image_board import customer_view_caption

            ready = bool(coerce_image_bytes(pair.get("after")))
            name = customer_view_caption(index, lead, missing=not ready)
            block: List[Any] = [Paragraph(_esc(name), s["guideH"])]
            if ready:
                reference = (
                    "The organized view was edited from this photo, same camera. "
                    "Windows and room proportions follow your photos. Paint is optional and is not applied in the visual."
                )
            else:
                reference = (
                    "This view is not ready. The package stays incomplete. "
                    "A missing angle is not replaced by another photo or by a crop."
                )
            block.append(Paragraph(reference, s["guideBody"]))
            if any_missing and index == 0:
                block.append(
                    Paragraph(
                        "A required view is still missing its organized photo. "
                        "That view is not filled from another angle.",
                        s["guideBody"],
                    )
                )
            _compare_page(
                block,
                coerce_image_bytes(pair.get("before")),
                coerce_image_bytes(pair.get("after")),
                before_banner="Your photo",
                after_banner="Organized view",
            )
        doc.build(story)
        return buf.getvalue(), doc.fills()

    before_bytes = coerce_image_bytes(images.get("before"))
    after_bytes = coerce_image_bytes(images.get("after"))
    if after_bytes:
        # Organized after exists. Do not print the
        # "we do not invent" / "organized view unavailable" disclaimer.
        if before_bytes:
            reference = (
                "This page shows the organized after beside your original photo. "
                "Windows and room proportions follow your photos. Paint is optional and is not applied in the visual."
            )
        else:
            reference = (
                "This page shows the organized after. "
                "Windows and room proportions follow your photos. Paint is optional and is not applied in the visual."
            )
        _compare_page(
            [
                Paragraph("ORGANIZED VIEW", s["guideH"]),
                Paragraph(reference, s["guideBody"]),
            ],
            before_bytes,
            after_bytes,
        )
    elif before_bytes:
        _compare_page(
            [
                Paragraph("BEFORE &amp; AFTER — PHOTO REFERENCE", s["guideH"]),
                Paragraph(
                    f"The {DESIGN_PLAN_NAME} is the primary visual. Your original photo is shown first. "
                    "An organized after was not produced for this package. "
                    "Do not invent an after.",
                    s["guideBody"],
                ),
            ],
            before_bytes,
            None,
        )

    doc.build(story)
    return buf.getvalue(), doc.fills()


def companion_page_fill(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Optional[bytes]],
) -> List[float]:
    """Fraction of each companion page's frame the content reaches (0–1), in page order."""
    return _render_companion(lead=lead, deliverable=deliverable, images=images)[1]
