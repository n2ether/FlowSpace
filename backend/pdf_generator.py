"""
FlowSpace Blueprint PDF — magazine-style organization plan.

Visual template (layout only): numbered sections, site emerald/slate palette,
Fraunces display + Inter body. Content is always an organization plan for closets, garages,
laundry rooms, pantries, mudrooms, and storage — never a bedroom redesign.

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
    Image as PlatypusImage,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from blueprint_layers import layer_card_copy, resolve_layers

# ──────────────────────────── Palette (site design system) ─────────────────────────────
# Matches frontend/src/index.css — emerald / mint / slate / white
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
# Legacy aliases so remaining helpers can be migrated incrementally
FOREST = EMERALD
FOREST_DEEP = EMERALD_DEEP
SAGE = HexColor("#10b981")
SAGE_SOFT = HexColor("#a7f3d0")
CREAM = SURFACE
CREAM_CARD = SURFACE
WOOD = HexColor("#A67C52")
INK = SLATE
MUTED = SLATE_MUTED
LINE = BORDER
SOFT_BG = SOFT
TAGLINE = "Clear space. Create flow. Live better."
VALUES_LINE = "BOUTIQUE  ·  FUNCTIONAL  ·  INTENTIONAL  ·  AFFORDABLE"
RADIUS = 8  # ~0.75rem at 72dpi

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

DEFAULT_PRINCIPLES = [
    "One home per item",
    "Hide visual noise",
    "Match the bins",
    "Keep the floor clear",
    "Zones, not piles",
    "Leave a path",
]

DEFAULT_RESET = [
    "Return items to their labeled bin",
    "Clear the landing zone / floor path",
    "Recycle empty packaging",
    "Wipe one work surface",
]

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
MARGIN = 0.42 * inch
HEADER_H = 0.62 * inch
FOOTER_H = 0.38 * inch


# ──────────────────────────── Styles ─────────────────────────────
def _styles():
    _register_fonts()
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Title"], fontName=_font("FSSerif-Bold"),
            fontSize=20, leading=23, textColor=SLATE, alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "values": ParagraphStyle(
            "values", parent=base["BodyText"], fontName=_font("FSSans-Medium"),
            fontSize=6.5, leading=9, textColor=EMERALD_DEEP, alignment=TA_LEFT,
        ),
        "kicker": ParagraphStyle(
            "kicker", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7, leading=9, textColor=EMERALD_DEEP, alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=_font("FSSerif-Bold"),
            fontSize=12, leading=14, textColor=SLATE, spaceBefore=0, spaceAfter=3,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName=_font("FSSans-Semi"),
            fontSize=8.5, leading=11, textColor=EMERALD_DEEP, spaceBefore=2, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=8, leading=10.5, textColor=INK,
        ),
        "bodySmall": ParagraphStyle(
            "bodySmall", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.2, leading=9.4, textColor=INK,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["BodyText"], fontName=_font("FSSans-Italic"),
            fontSize=7.2, leading=9.4, textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=7.6, leading=10, leftIndent=8, textColor=INK,
        ),
        "label": ParagraphStyle(
            "label", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=8, leading=10, textColor=SLATE,
        ),
        "cardCat": ParagraphStyle(
            "cardCat", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6, leading=8, textColor=EMERALD_DEEP, alignment=TA_LEFT,
        ),
        "cardTitle": ParagraphStyle(
            "cardTitle", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.4, leading=9.4, textColor=SLATE,
        ),
        "cardMeta": ParagraphStyle(
            "cardMeta", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.8, leading=8.6, textColor=MUTED,
        ),
        "banner": ParagraphStyle(
            "banner", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.5, leading=8, textColor=WHITE, alignment=TA_CENTER,
        ),
        "badge": ParagraphStyle(
            "badge", parent=base["BodyText"], fontName=_font("FSSans-Bold"),
            fontSize=6.2, leading=8, textColor=WHITE, alignment=TA_CENTER,
        ),
        "scoreBig": ParagraphStyle(
            "scoreBig", parent=base["Title"], fontName=_font("FSSerif-Bold"),
            fontSize=16, leading=18, textColor=EMERALD, alignment=TA_CENTER,
        ),
        "scoreLabel": ParagraphStyle(
            "scoreLabel", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.2, leading=8, textColor=MUTED, alignment=TA_CENTER,
        ),
        "footerSeg": ParagraphStyle(
            "footerSeg", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.2, leading=8, textColor=HexColor("#e2e8f0"), alignment=TA_CENTER,
        ),
        "whiteTiny": ParagraphStyle(
            "whiteTiny", parent=base["BodyText"], fontName=_font("FSSans"),
            fontSize=6.4, leading=8.2, textColor=HexColor("#ecfdf5"),
        ),
        "th": ParagraphStyle(
            "th", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=6.4, leading=8, textColor=WHITE,
        ),
        "signoff": ParagraphStyle(
            "signoff", parent=base["BodyText"], fontName=_font("FSSerif-Italic"),
            fontSize=8.5, leading=11, textColor=SLATE,
        ),
        "price": ParagraphStyle(
            "price", parent=base["BodyText"], fontName=_font("FSSans-Semi"),
            fontSize=7.2, leading=9, textColor=EMERALD_DEEP,
        ),
    }


# ──────────────────────────── Primitives ─────────────────────────────
def _safe_image(src: Optional[bytes], width: float, height: float) -> Any:
    if not src:
        return _placeholder(width, height, "Image not provided")
    try:
        bio = io.BytesIO(src)
        bio.seek(0)
        img = PlatypusImage(bio, width=width, height=height, kind="proportional")
        img.hAlign = "CENTER"
        return img
    except Exception:
        return _placeholder(width, height, "Image unavailable")


def _cover_image(src: Optional[bytes], width: float, height: float) -> Any:
    """Crop-to-fill a box so the hero reads like a magazine photo."""
    if not src:
        return _placeholder(
            width, height, "Organized view coming soon", "Your photo, re-zoned — visual arrives with the plan"
        )
    try:
        ir = ImageReader(io.BytesIO(src))
        iw, ih = ir.getSize()
        if iw <= 0 or ih <= 0:
            raise ValueError("empty")
        scale = max(width / iw, height / ih)
        draw_w, draw_h = iw * scale, ih * scale
        # ReportLab Image doesn't crop; we letterbox on white instead of inventing pixels.
        img = PlatypusImage(io.BytesIO(src), width=min(draw_w, width), height=min(draw_h, height))
        img.hAlign = "CENTER"
        return img
    except Exception:
        return _placeholder(width, height, "Image unavailable")


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


class CategoryChip(Flowable):
    """Small mint thumbnail for shopping cards."""

    def __init__(self, label: str, width: float, height: float = 26):
        super().__init__()
        self.label = (label or "ORG")[:10]
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(MINT_BG)
        c.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        c.setStrokeColor(MINT)
        c.setLineWidth(0.7)
        c.roundRect(0.3, 0.3, self.width - 0.6, self.height - 0.6, 5, fill=0, stroke=1)
        c.setFillColor(EMERALD_DEEP)
        c.setFont(_font("FSSans-Semi"), 6.4)
        c.drawCentredString(self.width / 2.0, self.height / 2.0 - 2.2, self.label)


class ZoneMosaic(Flowable):
    """Abstract zone tiles — not a measured floor plan."""

    def __init__(self, zones: Sequence[Dict[str, str]], width: float, height: float):
        super().__init__()
        self.zones = list(zones or [])[:6]
        self.width = width
        self.height = max(height, 72)

    def draw(self):
        c = self.canv
        c.setFillColor(SOFT)
        c.roundRect(0, 0, self.width, self.height, RADIUS, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.7)
        c.roundRect(0.4, 0.4, self.width - 0.8, self.height - 0.8, RADIUS, fill=0, stroke=1)

        n = max(len(self.zones), 1)
        cols = 3 if n >= 5 else (2 if n >= 4 else min(n, 3) or 1)
        rows = (n + cols - 1) // cols
        pad = 7
        gap = 5
        inner_w = self.width - pad * 2
        inner_h = self.height - pad * 2
        tw = (inner_w - gap * (cols - 1)) / cols
        th = (inner_h - gap * (rows - 1)) / rows
        fills = (WHITE, MINT_BG)

        for i in range(n):
            z = self.zones[i] if i < len(self.zones) else {}
            r, col = divmod(i, cols)
            x = pad + col * (tw + gap)
            y = self.height - pad - (r + 1) * th - r * gap
            c.setFillColor(fills[i % 2])
            c.roundRect(x, y, tw, th, 5, fill=1, stroke=0)
            c.setStrokeColor(MINT)
            c.setLineWidth(0.8)
            c.roundRect(x, y, tw, th, 5, fill=0, stroke=1)
            badge_r = 6
            c.setFillColor(EMERALD if i % 2 == 0 else EMERALD_DEEP)
            c.circle(x + 10, y + th - 11, badge_r, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont(_font("FSSans-Bold"), 7)
            c.drawCentredString(x + 10, y + th - 13.4, str(i + 1))
            max_chars = max(10, int((tw - 24) / 4.0))
            title = (z.get("title") or f"Zone {i + 1}").upper()
            c.setFillColor(SLATE)
            c.setFont(_font("FSSans-Semi"), 6.2)
            c.drawString(x + 20, y + th - 14, title[:max_chars])
            if th > 30:
                desc_chars = max(12, int((tw - 12) / 3.6))
                desc = (z.get("desc") or "Keep the existing shell.")[:desc_chars]
                c.setFillColor(SLATE_MUTED)
                c.setFont(_font("FSSans"), 5.6)
                c.drawString(x + 8, y + 8, desc)


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
        label = str(self.n)
        c.drawCentredString(r, r - self.size * 0.18, label)


def _section_head(number: str, title: str, width: float) -> Table:
    s = _styles()
    badge = NumberBadge(int(number) if str(number).isdigit() else 0, size=11)
    # number may be like "01"
    try:
        badge = NumberBadge(int(str(number).lstrip("0") or "0") or int(number), size=12)
    except Exception:
        badge = NumberBadge(1, size=12)
    title_p = Paragraph(title.upper(), s["kicker"])
    rule = Table([[""]], colWidths=[18], rowHeights=[1.1])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MINT)]))
    head = Table([[badge, title_p, rule]], colWidths=[16, max(width - 40, 40), 22])
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return head


def _hairline(width: float) -> Table:
    t = Table([[""]], colWidths=[width], rowHeights=[0.6])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.5, LINE)]))
    return t


def _card(inner, width: float, pad: float = 6) -> Table:
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
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
    )
    for keys, cat in rules:
        if any(k in n for k in keys):
            return cat
    return "ORGANIZER"


def _price_label(item: Dict[str, Any]) -> str:
    try:
        price = float(item.get("price", 0) or 0)
        qty = float(item.get("qty", 1) or 1)
    except (TypeError, ValueError):
        return "Typical retail"
    if price <= 0:
        return "Typical retail"
    # Honest unit price from the plan; qty noted when it matters.
    unit = f"${price:,.0f}" if price >= 10 else f"${price:,.2f}"
    if qty and qty != 1:
        q = int(qty) if float(qty).is_integer() else qty
        return f"{unit} ea · qty {q}"
    return f"{unit} ea"


def _materials(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> List[Tuple[str, str, Optional[str]]]:
    """(label, kind, hex_or_none) — organization materials, not a bedroom palette."""
    out: List[Tuple[str, str, Optional[str]]] = []
    colors_pref = [str(c).replace("_", " ").title() for c in (lead.get("color_prefs") or [])[:2]]
    styles = [str(c).replace("_", " ").title() for c in (lead.get("style_prefs") or [])[:2]]
    if "Sage" in " ".join(colors_pref) or "Green" in " ".join(colors_pref):
        out.append(("Sage bins", "tone", "#10b981"))
    if any("wood" in s.lower() or "natural" in s.lower() for s in styles + colors_pref):
        out.append(("Natural wood", "material", "#A67C52"))
    if any("white" in s.lower() or "light" in s.lower() for s in colors_pref):
        out.append(("Soft white", "tone", "#f8fafc"))
    out.append(("Clear / labeled", "material", "#e2e8f0"))
    out.append(("Woven / linen", "material", "#d6d3d1"))
    # de-dupe by label
    seen = set()
    unique = []
    for item in out:
        if item[0] not in seen:
            seen.add(item[0])
            unique.append(item)
    return unique[:5]


def _assessment(deliverable: Dict[str, Any]) -> Dict[str, Any]:
    """Plan-completeness scores — never room measurements."""
    zones = len(deliverable.get("zones") or [])
    needs = len(deliverable.get("needs") or [])
    shop = len(deliverable.get("shopping_list") or [])
    actions = len(deliverable.get("action_plan") or [])
    strategy = len(deliverable.get("strategy") or [])

    def clamp(n: float) -> float:
        return round(min(9.6, max(6.8, n)), 1)

    scores = [
        ("Storage", clamp(6.6 + zones * 0.55)),
        ("Function", clamp(6.6 + needs * 0.5)),
        ("Daily flow", clamp(6.8 + actions * 0.45)),
        ("Maintenance", clamp(7.2 + (0.4 if actions else 0))),
        ("Visual calm", clamp(7.0 + strategy * 0.4)),
        ("Shop-ready", clamp(6.5 + shop * 0.35)),
    ]
    overall = round(sum(v for _, v in scores) / len(scores), 1)
    return {"scores": scores, "overall": overall}


# ──────────────────────────── Page chrome ─────────────────────────────
def _draw_logo(canvas, x: float, y: float, size: float = 16) -> None:
    canvas.saveState()
    canvas.setStrokeColor(WHITE)
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


def _draw_chrome(canvas, doc, customer_name: str = "") -> None:
    canvas.saveState()
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Header bar — emerald, matching site CTAs
    canvas.setFillColor(EMERALD)
    canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)
    canvas.setFillColor(MINT)
    canvas.rect(0, PAGE_H - HEADER_H - 2.2, PAGE_W, 2.2, fill=1, stroke=0)
    _draw_logo(canvas, MARGIN, PAGE_H - HEADER_H / 2 + 1, 15)
    canvas.setFillColor(WHITE)
    canvas.setFont(_font("FSSerif-Bold"), 13.5)
    canvas.drawString(MARGIN + 22, PAGE_H - HEADER_H / 2 + 2, "FlowSpace")
    canvas.setFont(_font("FSSans"), 7)
    canvas.setFillColor(HexColor("#d1fae5"))
    canvas.drawString(MARGIN + 22 + 72, PAGE_H - HEADER_H / 2 + 3.5, TAGLINE.upper())

    # Blueprint badge
    badge_w, badge_h = 136, 24
    bx = PAGE_W - MARGIN - badge_w
    by = PAGE_H - HEADER_H / 2 - badge_h / 2 + 1
    canvas.setFillColor(EMERALD_DEEP)
    canvas.roundRect(bx, by, badge_w, badge_h, 6, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont(_font("FSSans-Bold"), 6.3)
    canvas.drawCentredString(bx + badge_w / 2, by + 13, "FLOWSPACE BLUEPRINT™")
    canvas.setFont(_font("FSSans"), 5.6)
    canvas.setFillColor(HexColor("#a7f3d0"))
    canvas.drawCentredString(bx + badge_w / 2, by + 5, "Your space. Your flow. Your life.")

    # Footer bar
    canvas.setFillColor(SLATE)
    canvas.rect(0, 0, PAGE_W, FOOTER_H, fill=1, stroke=0)
    canvas.setFillColor(MINT)
    canvas.rect(0, FOOTER_H, PAGE_W, 2, fill=1, stroke=0)
    segs = [
        "The FlowSpace Design Team",
        "Functional design",
        "Quality materials",
        "Thoughtful solutions",
        "Lasting value",
    ]
    canvas.setFillColor(HexColor("#e2e8f0"))
    canvas.setFont(_font("FSSans"), 6.2)
    gap = (PAGE_W - 2 * MARGIN) / len(segs)
    for i, seg in enumerate(segs):
        canvas.drawCentredString(MARGIN + gap * i + gap / 2, FOOTER_H / 2 - 2, seg)
    canvas.restoreState()


# ──────────────────────────── Sections ─────────────────────────────
def _hero_block(
    img_bytes: Optional[bytes],
    zones: List[Dict[str, str]],
    width: float,
    height: float,
) -> Table:
    s = _styles()
    photo = _cover_image(img_bytes, width, height - 14)
    banner = Table(
        [[Paragraph("ORGANIZED VIEW — YOUR REAL SPACE, RE-ZONED", s["banner"])]],
        colWidths=[width],
        rowHeights=[14],
    )
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
    # Compact numbered chips — organization systems, never invented dimensions.
    chips = []
    for i, z in enumerate((zones or [])[:5], 1):
        chips.append(Paragraph(f"<b>{i}</b>  {z.get('title') or f'Zone {i}'}", s["bodySmall"]))
    chip_row = None
    if chips:
        chip_row = Table([chips], colWidths=[width / len(chips)] * len(chips))
        chip_row.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), MINT_BG),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        stack = Table([[banner], [photo], [chip_row]], colWidths=[width])
    else:
        stack = Table([[banner], [photo]], colWidths=[width])
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
            ]
        )
    )
    return stack


def _whats_new(needs: List[str], zones: List[Dict[str, str]], width: float) -> List[Any]:
    s = _styles()
    rows = []
    items: List[Tuple[str, str]] = []
    for z in (zones or [])[:5]:
        items.append((z.get("title") or "Zone", z.get("desc") or "A clearer home for what you use."))
    if not items:
        for n in (needs or [])[:5]:
            items.append((n, "Keeps the physical shell; changes only the org system."))
    if not items:
        items = [
            ("Labeled bins", "Same footprint, less visual noise."),
            ("A clear path", "Circulation stays where the room already allows it."),
            ("A landing zone", "One place for drop-and-go items."),
        ]
    for i, (title, desc) in enumerate(items, 1):
        rows.append(
            [
                NumberBadge(i, size=12, fill=EMERALD),
                [
                    Paragraph(title, s["label"]),
                    Paragraph(desc, s["bodySmall"]),
                ],
            ]
        )
    t = Table(rows, colWidths=[16, max(width - 16, 40)])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
            ]
        )
    )
    return t


def _zone_flow(zones: List[Dict[str, str]], floor_plan: Optional[bytes], width: float) -> Table:
    s = _styles()
    left_w = width * 0.42
    right_w = width - left_w - 8
    if floor_plan:
        visual = _cover_image(floor_plan, left_w, 1.12 * inch)
        caption = Paragraph("Room flow from your photo — no invented dimensions.", s["muted"])
        left = [visual, Spacer(1, 3), caption]
    else:
        left = [
            ZoneMosaic(zones or [], left_w, 1.12 * inch),
            Spacer(1, 3),
            Paragraph("Conceptual zone map — not a measured floor plan. We do not invent room dimensions.", s["muted"]),
        ]

    titles = [z.get("title") or f"Zone {i}" for i, z in enumerate((zones or [])[:6], 1)]
    path = "  →  ".join(titles) if titles else "Zones will follow your real layout."
    move_rows = [
        Paragraph("HOW YOU MOVE", s["cardCat"]),
        Spacer(1, 3),
        Paragraph(path, s["label"]),
        Spacer(1, 4),
        Paragraph(
            "Enter, drop, walk the path the photo already shows, then store on existing walls. "
            "The stall / floor stays a destination — not a dump.",
            s["bodySmall"],
        ),
        Spacer(1, 5),
        Paragraph("Floor plan not included — we do not invent room dimensions.", s["muted"]),
    ]
    legend = _card(move_rows, right_w + 4, pad=7)
    t = Table([[left, legend]], colWidths=[left_w, right_w + 8])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ]
        )
    )
    return t


def _detail_cards(
    zones: List[Dict[str, str]],
    views: Sequence[Optional[bytes]],
    width: float,
) -> Table:
    s = _styles()
    cards = []
    provided = [b for b in views if b]
    count = min(5, max(len(zones or []), len(provided), 3))
    card_w = (width - 8) / count
    for i in range(count):
        z = (zones or [None] * count)[i] if i < len(zones or []) else None
        title = (z or {}).get("title") if z else f"Detail {i + 1}"
        desc = (z or {}).get("desc") if z else "A storage move that keeps the shell intact."
        bullets = [p.strip() for p in (desc or "").split(".") if p.strip()][:3] or [
            "Keep the existing footprint",
            "Contain clutter in matching bins",
        ]
        img = provided[i] if i < len(provided) else None
        zone_label = (title or f"Zone {i + 1}").upper()
        body = [
            _cover_image(img, card_w - 10, 0.52 * inch)
            if img
            else _placeholder(card_w - 10, 0.42 * inch, zone_label, "Existing shell"),
            Spacer(1, 3),
            Paragraph(f"0{i + 1}  {zone_label}", s["cardCat"]),
            Paragraph(title or "Storage detail", s["cardTitle"]),
        ]
        for b in bullets[:2]:
            body.append(Paragraph(f"· {b}", s["cardMeta"]))
        cards.append(_card(body, card_w, pad=5))
    t = Table([cards], colWidths=[card_w] * count)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _item_value(name: str) -> str:
    return {
        "BINS": "Contain · label · return",
        "BASKETS": "Corral loose daily items",
        "SHELVING": "Mount on existing walls",
        "HOOKS": "Hang daily, clear the floor",
        "LABELS": "Name every home",
        "LIGHTING": "See what you own",
        "FLOOR": "Mark the parking stall",
        "LAUNDRY": "Sort dirty from done",
        "HANGING": "Use the rod you have",
        "DIVIDERS": "Stop the pile-up",
        "TOOLS": "Park tools on the wall",
    }.get(_item_category(name), "Contain · label · return")


def _shopping_cards(items: List[Dict[str, Any]], width: float) -> Any:
    s = _styles()
    if not items:
        return Paragraph("Shopping list will follow your plan.", s["muted"])
    show = items[:8]
    cols = min(5, len(show))
    card_w = (width - 6) / cols
    row: List[Any] = []
    rows: List[List[Any]] = []
    for it in show:
        name = str(it.get("name") or "Organizer")
        cat = _item_category(name)
        body = [
            CategoryChip(cat, card_w - 10, 22),
            Spacer(1, 4),
            Paragraph(cat, s["cardCat"]),
            Paragraph(name, s["cardTitle"]),
            Paragraph(_price_label(it), s["price"]),
            Paragraph(_item_value(name), s["muted"]),
        ]
        row.append(_card(body, card_w, pad=5))
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        row += [""] * (cols - len(row))
        rows.append(row)
    t = Table(rows, colWidths=[card_w] * cols)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
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


def _palette_row(
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    width: float,
) -> Table:
    s = _styles()
    cells: List[Any] = []
    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    if wall_name or wall_hex:
        paint = [
            _swatch(wall_hex or "#CFD7D3", 26),
            Spacer(1, 2),
            Paragraph("OPTIONAL PAINT", s["cardCat"]),
            Paragraph(wall_name or "Consider only if it helps", s["cardTitle"]),
            Paragraph(deliverable.get("wall_color_code") or OPTIONAL_PAINT_HEADING, s["cardMeta"]),
        ]
        cells.append(_card(paint, width * 0.22, pad=5))
    mats = _materials(lead, deliverable)
    remain = width - (width * 0.22 + 6 if cells else 0)
    n = max(len(mats), 1)
    mw = remain / n
    for label, _kind, hx in mats:
        cells.append(
            _card(
                [
                    _swatch(hx or "#C4B49A", 22),
                    Spacer(1, 2),
                    Paragraph("MATERIAL", s["cardCat"]),
                    Paragraph(label, s["cardTitle"]),
                ],
                mw,
                pad=5,
            )
        )
    t = Table([cells], colWidths=[c._argW[0] if hasattr(c, "_argW") else width / len(cells) for c in cells])
    # colWidths from card wrappers:
    widths = []
    if wall_name or wall_hex:
        widths.append(width * 0.22)
        widths.extend([remain / max(len(mats), 1)] * len(mats))
    else:
        widths = [width / len(cells)] * len(cells)
    t = Table([cells], colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _roadmap(steps: List[str], width: float) -> Table:
    s = _styles()
    items = [x for x in (steps or []) if x][:5] or [
        "Declutter what does not belong",
        "Install the storage system",
        "Sort into labeled homes",
        "Reset the daily path",
    ]
    n = len(items)
    col_w = (width - 4) / n
    cols = []
    for i, step in enumerate(items, 1):
        cols.append(
            _card(
                [
                    Paragraph(f"STEP {i}", s["cardCat"]),
                    Paragraph(step, s["cardTitle"]),
                    Paragraph("Typical org session — no construction.", s["cardMeta"]),
                ],
                col_w,
                pad=5,
            )
        )
    t = Table([cols], colWidths=[col_w] * n)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _principles_and_reset(
    strategy: List[str],
    benefits: List[str],
    width: float,
) -> Table:
    s = _styles()
    rules = [x for x in (strategy or []) if x][:6] or DEFAULT_PRINCIPLES
    reset = DEFAULT_RESET[:]
    if benefits:
        extra = str(benefits[0]).strip()
        if extra and extra not in reset:
            reset.append(extra)

    left_items = []
    for i, rule in enumerate(rules[:6], 1):
        left_items.append(Paragraph(f"<b>{i:02d}</b>  {rule}", s["bodySmall"]))
    left = _card(
        [Paragraph("GUIDING PRINCIPLES", s["cardCat"]), Spacer(1, 3), *left_items],
        width * 0.52,
        pad=7,
    )
    right_items = [Paragraph(f"☐  {r}", s["bodySmall"]) for r in reset[:5]]
    right = _card(
        [
            Paragraph("10-MINUTE WEEKLY RESET", s["cardCat"]),
            Spacer(1, 3),
            *right_items,
            Spacer(1, 4),
            Paragraph("A short reset keeps the system — not a remodel.", s["muted"]),
        ],
        width * 0.46,
        pad=7,
    )
    t = Table([[left, right]], colWidths=[width * 0.53, width * 0.47])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _layers_strip(layers: Dict[str, Any], width: float) -> Table:
    """Customer-visible six Brain layers — compact 2×3 magazine cards."""
    s = _styles()
    cards = layer_card_copy(layers)
    col_w = (width - 8) / 3
    rows: List[List[Any]] = []
    row: List[Any] = []
    for num, title, body in cards:
        inner = [
            Paragraph(f"L{num}  {title}", s["label"]),
            Spacer(1, 2),
            Paragraph(body, s["bodySmall"]),
        ]
        row.append(_card(inner, col_w, pad=5))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        row += [""] * (3 - len(row))
        rows.append(row)
    t = Table(rows, colWidths=[col_w] * 3)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _validation_checks(layers: Dict[str, Any], width: float) -> Table:
    """Real validation — fit, flow, budget band, possession respect — not fluff scores."""
    s = _styles()
    val = (layers or {}).get("validation") or {}
    items = [
        ("Fit", val.get("fit") or {}),
        ("Flow", val.get("flow") or {}),
        ("Budget", val.get("budget_band") or {}),
        ("Possessions", val.get("possession_respect") or {}),
    ]
    col_w = (width - 6) / 2
    cards = []
    for label, check in items:
        status = str(check.get("status") or "watch").upper()
        note = check.get("note") or ""
        band = check.get("band") or ""
        body = [
            Paragraph(label.upper(), s["cardCat"]),
            Paragraph(status, s["cardTitle"]),
        ]
        if band:
            body.append(Paragraph(band, s["price"]))
        if note:
            body.append(Paragraph(note, s["cardMeta"]))
        cards.append(_card(body, col_w, pad=5))
    rows = [cards[0:2], cards[2:4]]
    checks = Table(rows, colWidths=[col_w, col_w])
    checks.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    extras: List[Any] = [checks]
    conflicts = [c for c in (val.get("conflicts") or []) if c]
    assumptions = [c for c in (val.get("assumptions") or []) if c]
    if conflicts:
        extras.append(Paragraph("Conflicts: " + "; ".join(conflicts[:3]), s["muted"]))
    if assumptions:
        extras.append(Paragraph("Assumptions: " + "; ".join(assumptions[:3]), s["muted"]))
    wrap = Table([[e] for e in extras], colWidths=[width])
    wrap.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return wrap


def _assessment_row(deliverable: Dict[str, Any], width: float) -> Table:
    s = _styles()
    data = _assessment(deliverable)
    score_w = (width * 0.72) / 6
    cells = []
    for label, value in data["scores"]:
        cells.append(
            [
                Paragraph(f"{value:.1f}", s["scoreBig"]),
                Paragraph(label, s["scoreLabel"]),
            ]
        )
    meters = Table([cells], colWidths=[score_w] * 6)
    meters.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    overall_inner = [
        Paragraph(f"{data['overall']:.1f}", s["scoreBig"]),
        Paragraph("OVERALL POTENTIAL", s["scoreLabel"]),
        Paragraph("Plan completeness — not a room measurement.", s["muted"]),
    ]
    overall = Table([[overall_inner]], colWidths=[width * 0.26])
    overall.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), MINT_BG),
                ("BOX", (0, 0), (-1, -1), 0.7, MINT),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    t = Table([[meters, overall]], colWidths=[width * 0.73, width * 0.27])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def _links_table(links: List[Dict[str, str]], width: float) -> Table:
    s = _styles()
    rows = [[Paragraph("ITEM", s["th"]), Paragraph("LINK", s["th"])]]
    for link in links or []:
        name = link.get("name", "") or ""
        url = link.get("url", "") or ""
        html = f'<link href="{url}" color="#047857"><u>{url}</u></link>' if url else ""
        rows.append([Paragraph(name, s["bodySmall"]), Paragraph(html, s["bodySmall"])])
    table = Table(rows, colWidths=[width * 0.28, width * 0.72])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _needs_line(needs: List[str]) -> str:
    clean = [n for n in (needs or []) if n]
    if not clean:
        return ""
    return "Needs: " + " · ".join(clean[:5])


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
    `images` — front_view, floor_plan, view_1/2/3, customer_photos
    """
    _register_fonts()
    buf = io.BytesIO()
    s = _styles()
    space_key = lead.get("space_type") or "space"
    space_name = space_label(space_key)
    title_text = plan_title(space_key)
    customer_name = lead.get("name") or "there"
    content_w = PAGE_W - 2 * MARGIN

    frame = Frame(
        MARGIN,
        FOOTER_H + 0.08 * inch,
        content_w,
        PAGE_H - HEADER_H - FOOTER_H - 0.16 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=4,
        bottomPadding=4,
        showBoundary=0,
    )
    template = PageTemplate(
        id="blueprint",
        frames=[frame],
        onPage=lambda c, d: _draw_chrome(c, d, customer_name),
    )
    doc = BaseDocTemplate(
        buf,
        pagesize=LETTER,
        pageTemplates=[template],
        title=f"{title_text} — FlowSpace Blueprint",
        author="FlowSpace",
    )

    layers = resolve_layers(lead, deliverable)
    zones = deliverable.get("zones") or []
    needs = deliverable.get("needs") or []
    shopping = deliverable.get("shopping_list") or []
    strategy = deliverable.get("strategy") or []
    action_plan = deliverable.get("action_plan") or []
    inst = layers.get("customer_instruction") or {}
    if inst.get("do_this_week"):
        action_plan = inst["do_this_week"]
    benefits = deliverable.get("benefits") or []
    intro = (
        deliverable.get("intro")
        or f"A calmer {space_name.lower()} — organized around the room you already have."
    )
    story: List[Any] = []

    # ── Title band
    eyebrow = Table(
        [[Paragraph("ORGANIZATION PLAN", s["kicker"])]],
        colWidths=[content_w * 0.46],
    )
    eyebrow.setStyle(
        TableStyle(
            [
                ("LINEBEFORE", (0, 0), (0, 0), 1.4, MINT),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    title_left = [
        eyebrow,
        Paragraph(title_text, s["h1"]),
        Paragraph(VALUES_LINE, s["values"]),
        Paragraph(_keyword_line(lead) + "  ·  SAME WALLS  ·  SAME WINDOWS", s["muted"]),
    ]
    story_blk = [
        Paragraph(f"Hi {customer_name} — this plan is designed for how you live.", s["bodySmall"]),
        Spacer(1, 2),
        Paragraph(intro, s["body"]),
    ]
    needs_line = _needs_line(needs)
    if needs_line:
        story_blk += [Spacer(1, 3), Paragraph(needs_line, s["muted"])]
    band = Table([[title_left, story_blk]], colWidths=[content_w * 0.46, content_w * 0.54])
    band.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(band)

    # ── Six Brain layers (customer-visible structured reasoning)
    story.append(Paragraph("SIX-LAYER REASONING  ·  OBSERVATION → INSTRUCTION", s["kicker"]))
    story.append(Spacer(1, 2))
    story.append(_layers_strip(layers, content_w))
    story.append(Spacer(1, 3))

    # ── 01 Hero + 02/03 story already above + What's new
    left_w = content_w * 0.56
    right_w = content_w * 0.42
    hero = _hero_block(images.get("front_view"), zones, left_w, 1.72 * inch)
    right = [
        _section_head("01", "Project story", right_w),
        Paragraph(
            deliverable.get("summary")
            or intro,
            s["bodySmall"],
        ),
        Spacer(1, 6),
        _section_head("02", "What's new & why", right_w),
        _whats_new(needs, zones, right_w),
    ]
    top = Table([[hero, right]], colWidths=[left_w + 6, right_w])
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 8),
            ]
        )
    )
    story.append(top)
    story.append(Spacer(1, 4))

    # ── 03 Room flow
    story.append(_section_head("03", f"{space_name} flow guide — Room layout & zones", content_w))
    story.append(_zone_flow(zones, images.get("floor_plan"), content_w))
    story.append(Spacer(1, 4))

    # ── 04 Detail cards
    story.append(_section_head("04", "System details", content_w))
    story.append(
        _detail_cards(
            zones,
            [images.get("view_1"), images.get("view_2"), images.get("view_3")],
            content_w,
        )
    )
    story.append(Spacer(1, 4))

    # ── 05 Curated selections
    shop_head = Table(
        [[
            _section_head("05", "Curated selections — Shopping list", content_w * 0.72),
            Paragraph(deliverable.get("budget_note") or "Estimated retail · confirm before you buy.", s["muted"]),
        ]],
        colWidths=[content_w * 0.72, content_w * 0.28],
    )
    shop_head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    shop_bits: List[Any] = [shop_head, Spacer(1, 2), _shopping_cards(shopping, content_w)]
    if shopping:
        total = 0.0
        for it in shopping:
            try:
                total += float(it.get("qty", 1) or 1) * float(it.get("price", 0) or 0)
            except (TypeError, ValueError):
                pass
        shop_bits += [
            Spacer(1, 3),
            Paragraph(f"<b>Estimated total</b>  ${total:,.2f}  ·  Budget is a typical retail range.", s["muted"]),
        ]
    early_links = deliverable.get("shopping_links") or []
    if early_links:
        shop_bits.append(Spacer(1, 3))
        shop_bits.append(Paragraph("Shopping Links", s["h3"]))
        link_line = "   ·   ".join(
            f'<link href="{lnk.get("url") or ""}" color="#047857"><u>{lnk.get("name") or lnk.get("url")}</u></link>'
            for lnk in early_links[:6]
            if lnk.get("name") or lnk.get("url")
        )
        if link_line:
            shop_bits.append(Paragraph(link_line, s["bodySmall"]))
    story.append(KeepTogether(shop_bits))
    story.append(Spacer(1, 3))

    # ── 06 Palette
    story.append(_section_head("06", "Color & material palette", content_w))
    story.append(_palette_row(lead, deliverable, content_w))
    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    if wall_name or wall_hex:
        story.append(Spacer(1, 2))
        story.append(Paragraph(OPTIONAL_PAINT_NOTE, s["muted"]))
    story.append(Spacer(1, 3))

    # ── 07 Roadmap
    story.append(_section_head("07", "Implementation roadmap — Simple action plan", content_w))
    story.append(_roadmap(action_plan, content_w))
    story.append(Spacer(1, 3))

    # ── 08 / 09 Principles + reset
    story.append(_section_head("08", "Styling rules & weekly reset", content_w))
    story.append(_principles_and_reset(strategy, benefits, content_w))
    story.append(Spacer(1, 3))

    # ── 09 Notes
    notes = deliverable.get("notes") or DEFAULT_NOTES
    story.append(_section_head("09", "Notes & tips", content_w))
    notes_card = Table([[Paragraph(notes, s["bodySmall"])]], colWidths=[content_w])
    notes_card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LINEBEFORE", (0, 0), (0, 0), 3, MINT),
                ("ROUNDEDCORNERS", [RADIUS, RADIUS, RADIUS, RADIUS]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(notes_card)
    story.append(Spacer(1, 3))

    # ── 10 Assessment + real validation (fit / flow / budget / possessions)
    story.append(
        KeepTogether(
            [
                _section_head("10", "Designer assessment", content_w),
                _assessment_row(deliverable, content_w),
            ]
        )
    )
    story.append(Spacer(1, 4))
    story.append(Paragraph("Validation — real checks, not room measurements.", s["muted"]))
    story.append(Spacer(1, 2))
    story.append(_validation_checks(layers, content_w))

    # ── Extra pages: customer photos
    customer_photos: List[Optional[bytes]] = images.get("customer_photos") or []
    included_photos = 0
    for idx, b in enumerate(customer_photos, 1):
        if not b:
            continue
        included_photos += 1
        story.append(PageBreak())
        story.append(Paragraph(f"Reference Photo {idx}", s["h3"]))
        story.append(Paragraph("Customer photo — the physical shell we organize, not a redesign.", s["muted"]))
        story.append(Spacer(1, 4))
        max_w = content_w
        max_h = PAGE_H - HEADER_H - FOOTER_H - 1.1 * inch
        try:
            bio = io.BytesIO(b)
            ir = ImageReader(bio)
            iw, ih = ir.getSize()
            ratio = min(max_w / iw, max_h / ih)
            bio.seek(0)
            img = PlatypusImage(bio, width=iw * ratio, height=ih * ratio)
            img.hAlign = "CENTER"
            story.append(img)
        except Exception:
            story.append(_placeholder(max_w, max_h, "Photo unavailable"))

    links = deliverable.get("shopping_links") or []
    attachment_note = deliverable.get("attachment_note") or ""
    # Compact links already sit under curated selections. Only add a full table
    # when there are reference photos or a fulfillment attachment note.
    if included_photos or attachment_note:
        link_bits: List[Any] = []
        if included_photos:
            story.append(PageBreak())
        else:
            link_bits.append(Spacer(1, 6))
        if attachment_note or (links and included_photos):
            link_bits.append(Paragraph("Shopping Links", s["h3"]))
        if attachment_note:
            link_bits.append(Paragraph(attachment_note, s["bodySmall"]))
            link_bits.append(Spacer(1, 3))
        if links and included_photos:
            link_bits.append(_links_table(links, content_w))
        if link_bits:
            story.append(KeepTogether(link_bits))

    doc.build(story)
    return buf.getvalue()
