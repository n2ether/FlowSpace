"""
FlowSpace branded PDF deliverable generator.

Layout reference (structure only — not a bedroom-redesign product):
  Header brand bar
  Space-aware title (Garage Organization Plan, Closet Blueprint, …)
  Two columns — visuals | callout, needs, numbered zones,
                 optional paint recommendation
  Full-width shopping list + budget
  Bottom row — Design Strategy | Simple Action Plan | Benefits
  Footer: windows/dimensions ~95% true to the photo; paint is optional

Primary spaces: closets, garages, laundry rooms, pantries, mudrooms, storage.
Never invent wall/window/dimension callouts. Floor plans only when provided.

Pure reportlab — no external services needed.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as PlatypusImage,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Brand
BRAND_DARK = HexColor("#1F3D2C")   # deep sage / forest
BRAND_GREEN = HexColor("#5C7A65")  # sage line
BRAND_ACCENT = HexColor("#10b981") # emerald accent
INK = HexColor("#1f2937")
MUTED = HexColor("#6b7280")
LINE = HexColor("#e5e7eb")
SOFT_BG = HexColor("#f7faf9")
TAGLINE = "Clear space. Create flow. Live better."

# Customer-facing space names. Underscored intake ids → readable labels.
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
    "Optional recommendation only. Not applied in the visual. "
    "Consider this color if it helps your organization goal."
)


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
MARGIN = 0.55 * inch
HEADER_H = 0.55 * inch


def _draw_header(canvas, doc, customer_name: str = "") -> None:
    """Draw the brand bar at the top of every page."""
    canvas.saveState()
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)

    # Logo (simple SVG-like house + wave drawn with primitives)
    cx, cy = MARGIN + 12, PAGE_H - HEADER_H / 2
    canvas.setStrokeColor(colors.white)
    canvas.setLineWidth(1.8)
    # House
    p = canvas.beginPath()
    p.moveTo(cx - 11, cy - 2)
    p.lineTo(cx, cy + 11)
    p.lineTo(cx + 11, cy - 2)
    p.lineTo(cx + 11, cy - 12)
    p.lineTo(cx - 11, cy - 12)
    p.close()
    canvas.drawPath(p, stroke=1, fill=0)
    # Wave inside
    p2 = canvas.beginPath()
    p2.moveTo(cx - 9, cy - 6)
    p2.curveTo(cx - 4, cy - 9, cx, cy - 3, cx + 4, cy - 6)
    p2.curveTo(cx + 7, cy - 8, cx + 9, cy - 6, cx + 11, cy - 6)
    canvas.drawPath(p2, stroke=1, fill=0)

    # Brand name
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(MARGIN + 32, PAGE_H - HEADER_H / 2 - 4, "FlowSpace")
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(HexColor("#cfe2d7"))
    canvas.drawString(MARGIN + 32 + 78, PAGE_H - HEADER_H / 2 - 3, TAGLINE)

    # Right side — page number
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(HexColor("#cfe2d7"))
    canvas.drawRightString(
        PAGE_W - MARGIN,
        PAGE_H - HEADER_H / 2 - 3,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=BRAND_DARK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=BRAND_DARK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=BRAND_GREEN,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=MUTED,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=12,
            bulletIndent=2,
            textColor=INK,
        ),
        "label": ParagraphStyle(
            "label",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=BRAND_DARK,
        ),
        "imgCaption": ParagraphStyle(
            "imgCaption",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "keywords": ParagraphStyle(
            "keywords",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=BRAND_GREEN,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "banner": ParagraphStyle(
            "banner",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "calloutTitle": ParagraphStyle(
            "calloutTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
        ),
        "calloutBody": ParagraphStyle(
            "calloutBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=HexColor("#e8f5ee"),
        ),
        "zoneNum": ParagraphStyle(
            "zoneNum",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "colHead": ParagraphStyle(
            "colHead",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=BRAND_DARK,
            spaceBefore=0,
            spaceAfter=4,
        ),
        "footerNote": ParagraphStyle(
            "footerNote",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _safe_image(src: Optional[bytes], width: float, height: float) -> Any:
    """Return a Flowable for an image, or a placeholder Table if bytes invalid."""
    if not src:
        return _placeholder(width, height, "Image not provided")
    try:
        bio = io.BytesIO(src)
        bio.seek(0)
        img = PlatypusImage(bio, width=width, height=height)
        img.hAlign = "CENTER"
        return img
    except Exception:
        return _placeholder(width, height, "Image unavailable")


def _placeholder(w: float, h: float, label: str):
    t = Table([[Paragraph(f"<font color='#9ca3af'>{label}</font>", _styles()["body"])]], colWidths=[w], minRowHeights=[h])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def _hr():
    t = Table([[""]], colWidths=[PAGE_W - 2 * MARGIN], rowHeights=[0.5])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.7, LINE)]))
    return t


def _bullet_list(items: List[str], style) -> List[Any]:
    out = []
    for it in items:
        if not it:
            continue
        out.append(Paragraph(f"• {it}", style))
    return out


def _shopping_table(
    items: List[Dict[str, Any]],
    currency: str = "$",
    available_width: Optional[float] = None,
) -> Table:
    header = ["Item", "Qty", "Est. Price", "Subtotal"]
    rows = [header]
    total = 0.0
    full_w = available_width if available_width else (PAGE_W - 2 * MARGIN)
    name_w = full_w * 0.46
    qty_w = full_w * 0.12
    price_w = full_w * 0.21
    sub_w = full_w * 0.21

    for it in items or []:
        name = str(it.get("name", ""))
        qty = float(it.get("qty", 1) or 1)
        price = float(it.get("price", 0) or 0)
        subtotal = qty * price
        total += subtotal
        rows.append(
            [
                Paragraph(name, _styles()["body"]),
                f"{int(qty) if qty.is_integer() else qty}",
                f"{currency}{price:,.2f}",
                f"{currency}{subtotal:,.2f}",
            ]
        )
    rows.append(["", "", "Estimated Total", f"{currency}{total:,.2f}"])

    table = Table(rows, colWidths=[name_w, qty_w, price_w, sub_w])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, SOFT_BG]),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), HexColor("#ecfdf5")),
                ("TEXTCOLOR", (0, -1), (-1, -1), BRAND_DARK),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _links_table(links: List[Dict[str, str]]) -> Table:
    rows = [["Item", "Link"]]
    for link in links or []:
        name = link.get("name", "") or ""
        url = link.get("url", "") or ""
        link_html = f'<link href="{url}" color="#2563eb"><u>{url}</u></link>' if url else ""
        rows.append([Paragraph(name, _styles()["body"]), Paragraph(link_html, _styles()["body"])])

    table = Table(rows, colWidths=[1.9 * inch, 4.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT_BG]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _zones_table(zones: List[Dict[str, str]], available_width: float) -> Table:
    rows = []
    for z in zones or []:
        title = z.get("title", "") or ""
        desc = z.get("desc", "") or ""
        rows.append(
            [
                Paragraph(f"<b>{title}</b>", _styles()["body"]),
                Paragraph(desc, _styles()["body"]),
            ]
        )
    if not rows:
        return _placeholder(available_width, 36, "No zones provided")
    # Reserve a smaller, proportional label column and give the rest to
    # the description column. Small safety margin subtracted for cell padding.
    label_w = min(0.9 * inch, available_width * 0.32)
    desc_w = max(available_width - label_w - 4, 0.8 * inch)
    t = Table(rows, colWidths=[label_w, desc_w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _wall_color_block(
    name: str,
    code: str,
    hex_color: str,
    note: str,
    available_width: Optional[float] = None,
) -> Table:
    swatch_color = HexColor(hex_color) if hex_color and hex_color.startswith("#") else HexColor("#a3b8c2")
    swatch = Table([[""]], colWidths=[0.48 * inch], rowHeights=[0.48 * inch])
    swatch.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), swatch_color),
                ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#cbd5e1")),
            ]
        )
    )
    s = _styles()
    info = [
        Paragraph(f"<b>{name or 'Optional paint suggestion'}</b>", s["body"]),
        Paragraph(f"<font color='#6b7280'>{code or ''}</font>", s["body"]),
        Spacer(1, 2),
        Paragraph(note or OPTIONAL_PAINT_NOTE, s["muted"]),
    ]
    full_w = available_width if available_width else (PAGE_W - 2 * MARGIN)
    t = Table([[swatch, info]], colWidths=[0.62 * inch, max(full_w - 0.62 * inch, 1.2 * inch)])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


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
    return "  ·  ".join(b.upper() for b in bits[:3])


def _visual_block(img_bytes: Optional[bytes], caption: str, width: float, height: float) -> Table:
    """Image with a dark sage caption banner — template '3D VISUAL – FRONT VIEW' style."""
    s = _styles()
    banner = Table([[Paragraph(caption, s["banner"])]], colWidths=[width], rowHeights=[16])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    img = _safe_image(img_bytes, width, height)
    block = Table([[banner], [img]], colWidths=[width])
    block.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return block


def _callout_box(width: float) -> Table:
    s = _styles()
    inner = [
        Paragraph("DESIGNED FOR HOW YOU LIVE", s["calloutTitle"]),
        Spacer(1, 3),
        Paragraph(
            "Smart storage and a calmer layout — less visual noise, less daily stress. "
            "We organize the room you already have.",
            s["calloutBody"],
        ),
    ]
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _numbered_zones(zones: List[Dict[str, str]], available_width: float) -> Table:
    s = _styles()
    rows = []
    for i, z in enumerate(zones or [], 1):
        title = z.get("title", "") or ""
        desc = z.get("desc", "") or ""
        badge = Table([[Paragraph(str(i), s["zoneNum"])]], colWidths=[16], rowHeights=[16])
        badge.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        text = [
            Paragraph(f"<b>{title}</b>", s["label"]),
            Paragraph(desc, s["body"]),
        ]
        rows.append([badge, text])
    if not rows:
        return _placeholder(available_width, 32, "Zones will follow your real layout")
    badge_w = 22
    t = Table(rows, colWidths=[badge_w, max(available_width - badge_w - 4, 0.8 * inch)])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def _budget_box(note: str, width: float) -> Table:
    s = _styles()
    body = note or "Budget is an estimate from typical retail ranges. Confirm prices before you buy."
    t = Table(
        [[Paragraph("<b>BUDGET RANGE</b>", s["calloutTitle"])], [Paragraph(body, s["calloutBody"])]],
        colWidths=[width],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ]
        )
    )
    return t


def _three_col_section(
    strategy: List[str],
    action_plan: List[str],
    benefits: List[str],
) -> Table:
    s = _styles()
    col_w = (PAGE_W - 2 * MARGIN - 16) / 3

    def col(title: str, items: List[str], numbered: bool = False) -> List[Any]:
        out: List[Any] = [Paragraph(title, s["colHead"])]
        if not items:
            out.append(Paragraph("—", s["muted"]))
            return out
        for i, item in enumerate(items, 1):
            if not item:
                continue
            prefix = f"{i}. " if numbered else "✓  "
            out.append(Paragraph(f"{prefix}{item}", s["bullet"]))
        return out

    t = Table(
        [[col("Design Strategy", strategy), col("Simple Action Plan", action_plan, True), col("Benefits", benefits)]],
        colWidths=[col_w, col_w, col_w],
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (0, 0), 0.4, LINE),
                ("BOX", (1, 0), (1, 0), 0.4, LINE),
                ("BOX", (2, 0), (2, 0), 0.4, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT_BG),
            ]
        )
    )
    return t


def build_pdf(
    *,
    lead: Dict[str, Any],
    deliverable: Dict[str, Any],
    images: Dict[str, Optional[bytes]],
) -> bytes:
    """
    Render the design deliverable PDF.

    `lead` — the questionnaire/lead document (name, email, space_type, etc.)
    `deliverable` — admin-provided design content (zones, needs, shopping_list, ...)
    `images` — dict with raw bytes for:
        front_view, floor_plan, view_1, view_2, view_3, and customer_photos (list)
    Returns: PDF bytes.
    """
    buf = io.BytesIO()
    s = _styles()
    space_key = lead.get("space_type") or "space"
    space_name = space_label(space_key)
    title_text = plan_title(space_key)
    customer_name = lead.get("name") or "there"

    frame = Frame(
        MARGIN,
        MARGIN,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 2 * MARGIN - HEADER_H + 0.1 * inch,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        showBoundary=0,
    )
    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=lambda c, d: _draw_header(c, d, customer_name),
    )

    doc = BaseDocTemplate(
        buf,
        pagesize=LETTER,
        pageTemplates=[template],
        title=f"{title_text} — FlowSpace",
        author="FlowSpace",
    )

    story: List[Any] = []

    # --- Page 1: organization plan (template structure, space-aware title)
    content_w = PAGE_W - 2 * MARGIN
    left_w = content_w * 0.54
    right_w = content_w * 0.46 - 8

    story.append(Paragraph(f"Hi {customer_name}!", s["body"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(title_text, s["h1"]))
    story.append(Paragraph(_keyword_line(lead), s["keywords"]))
    intro = (
        deliverable.get("intro")
        or "A calmer, easier space to live with — organized around the room you already have."
    )
    story.append(Paragraph(intro, s["body"]))
    story.append(Spacer(1, 8))

    # Left: visuals. Right: needs / zones / palette / shopping.
    # Skip empty floor-plan / extra-view slots so we never invent architecture
    # and so the two-column plan can stay on the first page.
    fv = _visual_block(images.get("front_view"), "3D VISUAL – FRONT VIEW", left_w, 1.85 * inch)
    left_col: List[Any] = [fv]
    if images.get("floor_plan"):
        left_col += [Spacer(1, 5), _visual_block(images.get("floor_plan"), "FLOOR PLAN (TOP VIEW)", left_w, 1.35 * inch)]
    else:
        left_col += [
            Spacer(1, 4),
            Paragraph(
                "Floor plan not included — we do not invent room dimensions.",
                s["muted"],
            ),
        ]

    extra_slots = [
        (images.get("view_1"), "VIEW 1"),
        (images.get("view_2"), "VIEW 2"),
        (images.get("view_3"), "VIEW 3"),
    ]
    provided_views = [(b, cap) for b, cap in extra_slots if b]
    if provided_views:
        v_w = (left_w - 8) / max(len(provided_views), 1)
        v_h = 0.85 * inch
        extra_views = Table(
            [[_visual_block(b, cap, v_w, v_h) for b, cap in provided_views]],
            colWidths=[v_w] * len(provided_views),
        )
        extra_views.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        left_col += [Spacer(1, 5), extra_views]

    needs = deliverable.get("needs") or []
    zones = deliverable.get("zones") or []
    shopping = deliverable.get("shopping_list") or []
    budget_note = deliverable.get("budget_note") or ""

    right_col: List[Any] = [_callout_box(right_w), Spacer(1, 8)]
    right_col.append(Paragraph(f"{space_name} needs", s["h3"]))
    if needs:
        right_col.extend(_bullet_list(needs, s["bullet"]))
    else:
        right_col.append(Paragraph("—", s["muted"]))
    right_col.append(Spacer(1, 6))
    right_col.append(Paragraph("Room Layout & Zones", s["h3"]))
    right_col.append(_numbered_zones(zones, right_w - 6))
    right_col.append(Spacer(1, 6))

    wall_name = (deliverable.get("wall_color_name") or "").strip()
    wall_hex = (deliverable.get("wall_color_hex") or "").strip()
    if wall_name or wall_hex:
        right_col.append(Paragraph(OPTIONAL_PAINT_HEADING, s["h3"]))
        right_col.append(
            _wall_color_block(
                wall_name,
                deliverable.get("wall_color_code", ""),
                wall_hex,
                deliverable.get("wall_color_note", ""),
                available_width=right_w - 4,
            )
        )
        right_col.append(Spacer(1, 6))

    main = Table([[left_col, right_col]], colWidths=[left_w, right_w + 8])
    main.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 6),
                ("LEFTPADDING", (1, 0), (1, 0), 6),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ]
        )
    )
    story.append(main)
    story.append(Spacer(1, 8))

    # Full-width shopping keeps the two-column block short enough for page 1
    story.append(Paragraph("Shopping List &amp; Estimated Budget", s["h3"]))
    story.append(_shopping_table(shopping, available_width=content_w))
    if budget_note:
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"<b>Budget range:</b> {budget_note}", s["muted"]))
    story.append(Spacer(1, 8))

    strategy = deliverable.get("strategy") or []
    action_plan = deliverable.get("action_plan") or []
    benefits = deliverable.get("benefits") or []
    story.append(_three_col_section(strategy, action_plan, benefits))

    notes = deliverable.get("notes") or DEFAULT_NOTES
    story.append(Spacer(1, 8))
    story.append(Paragraph(notes, s["footerNote"]))

    # --- Extra pages: Customer photos (only when present) ------------
    customer_photos: List[Optional[bytes]] = images.get("customer_photos") or []
    included_photos = 0
    for idx, b in enumerate(customer_photos, 1):
        if not b:
            continue
        included_photos += 1
        story.append(PageBreak())
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph(f"Reference Photo {idx}", s["h3"]))
        story.append(Spacer(1, 4))
        # Full-bleed-ish image preserving aspect ratio
        max_w = PAGE_W - 2 * MARGIN
        max_h = PAGE_H - 2 * MARGIN - HEADER_H - 0.6 * inch
        try:
            bio = io.BytesIO(b)
            ir = ImageReader(bio)
            iw, ih = ir.getSize()
            ratio = min(max_w / iw, max_h / ih)
            w = iw * ratio
            h = ih * ratio
            bio.seek(0)
            img = PlatypusImage(bio, width=w, height=h)
            img.hAlign = "CENTER"
            story.append(img)
        except Exception:
            story.append(_placeholder(max_w, max_h, "Photo unavailable"))

    # --- Summary + Shopping Links (new page only if photos used space)
    if included_photos:
        story.append(PageBreak())
    else:
        story.append(Spacer(1, 10))
    story.append(Paragraph("Design Summary", s["h2"]))
    summary = deliverable.get("summary") or (
        "A calm, functional space tailored to how you live — with smart storage, "
        "a clear visual layout, and a shopping plan you can actually follow."
    )
    story.append(Paragraph(summary, s["body"]))
    story.append(Spacer(1, 10))

    attachment_note = deliverable.get("attachment_note") or ""
    if attachment_note:
        story.append(Paragraph("Attachment Included", s["h3"]))
        story.append(Paragraph(attachment_note, s["body"]))
        story.append(Spacer(1, 10))

    links = deliverable.get("shopping_links") or []
    if links:
        story.append(Paragraph("Shopping Links", s["h3"]))
        story.append(_links_table(links))
        story.append(Spacer(1, 12))

    story.append(_hr())
    story.append(Spacer(1, 6))
    story.append(Paragraph("Warmly,", s["body"]))
    story.append(Paragraph("<b>The FlowSpace Design Team</b>", s["body"]))
    story.append(Paragraph(TAGLINE, s["muted"]))

    doc.build(story)
    return buf.getvalue()
