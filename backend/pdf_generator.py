"""
FlowSpace branded PDF deliverable generator.

Layout reference: a multi-page design plan featuring
  Page 1: Overall Plan (3D front view, floor plan, additional views, room needs,
          zones, wall color, shopping list/budget, design strategy, action plan, benefits)
  Pages 2..N: Customer-uploaded space photos (one per page, full bleed)
  Last page: Design summary + shopping links table

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
            fontSize=24,
            leading=28,
            textColor=BRAND_DARK,
            alignment=TA_LEFT,
            spaceAfter=4,
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
    t = Table([[Paragraph(f"<font color='#9ca3af'>{label}</font>", _styles()["body"])]], colWidths=[w], rowHeights=[h])
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


def _shopping_table(items: List[Dict[str, Any]], currency: str = "$") -> Table:
    header = ["Item", "Qty", "Est. Price", "Subtotal"]
    rows = [header]
    total = 0.0
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
    rows.append(["", "", "Total", f"{currency}{total:,.2f}"])

    table = Table(rows, colWidths=[2.8 * inch, 0.55 * inch, 0.95 * inch, 1.0 * inch])
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
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
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


def _zones_table(zones: List[Dict[str, str]]) -> Table:
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
        return _placeholder(PAGE_W - 2 * MARGIN, 36, "No zones provided")
    t = Table(rows, colWidths=[1.2 * inch, PAGE_W - 2 * MARGIN - 1.2 * inch])
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


def _wall_color_block(name: str, code: str, hex_color: str, note: str) -> Table:
    swatch_color = HexColor(hex_color) if hex_color and hex_color.startswith("#") else HexColor("#a3b8c2")
    swatch = Table([[""]], colWidths=[0.65 * inch], rowHeights=[0.65 * inch])
    swatch.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), swatch_color),
                ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#cbd5e1")),
            ]
        )
    )
    info = [
        Paragraph(f"<b>{name or 'Suggested Wall Color'}</b>", _styles()["body"]),
        Paragraph(f"<font color='#6b7280'>{code or ''}</font>", _styles()["body"]),
        Spacer(1, 3),
        Paragraph(note or "", _styles()["muted"]),
    ]
    t = Table([[swatch, info]], colWidths=[0.85 * inch, PAGE_W - 2 * MARGIN - 0.85 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
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
    space_label = (lead.get("space_type") or "Space").capitalize()
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
        title=f"{space_label} Design Plan — FlowSpace",
        author="FlowSpace",
    )

    story: List[Any] = []

    # --- Page 1: Overall Plan ----------------------------------------
    story.append(Paragraph(f"Hi {customer_name}!", s["body"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"{space_label} Design Plan", s["h1"]))
    intro = (
        deliverable.get("intro")
        or "Here's your personalized plan. We focused on a layout that fits your real life, "
        "with a calm look you'll enjoy walking into every day."
    )
    story.append(Paragraph(intro, s["body"]))
    story.append(Spacer(1, 8))
    story.append(_hr())
    story.append(Paragraph("Overall Plan", s["h2"]))

    # Front view + floor plan side by side
    cw = (PAGE_W - 2 * MARGIN - 10) / 2
    img_h = 2.5 * inch
    fv = _safe_image(images.get("front_view"), cw, img_h)
    fp = _safe_image(images.get("floor_plan"), cw, img_h)
    top = Table(
        [
            [fv, fp],
            [
                Paragraph("3D Front View", s["imgCaption"]),
                Paragraph("Floor Plan (Top View)", s["imgCaption"]),
            ],
        ],
        colWidths=[cw, cw],
    )
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(top)
    story.append(Spacer(1, 6))

    # Additional 3 views row
    cw3 = (PAGE_W - 2 * MARGIN - 16) / 3
    h3 = 1.45 * inch
    v1 = _safe_image(images.get("view_1"), cw3, h3)
    v2 = _safe_image(images.get("view_2"), cw3, h3)
    v3 = _safe_image(images.get("view_3"), cw3, h3)
    row = Table(
        [
            [v1, v2, v3],
            [
                Paragraph("View 1", s["imgCaption"]),
                Paragraph("View 2", s["imgCaption"]),
                Paragraph("View 3", s["imgCaption"]),
            ],
        ],
        colWidths=[cw3, cw3, cw3],
    )
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(row)
    story.append(Spacer(1, 12))

    # Needs and Zones (two columns)
    needs = deliverable.get("needs") or []
    zones = deliverable.get("zones") or []

    needs_cell: List[Any] = [Paragraph(f"{space_label} Needs", s["h3"])]
    if needs:
        needs_cell += _bullet_list(needs, s["bullet"])
    else:
        needs_cell.append(Paragraph("—", s["muted"]))

    zones_cell: List[Any] = [Paragraph("Room Layout & Zones", s["h3"]), _zones_table(zones)]

    nz = Table([[needs_cell, zones_cell]], colWidths=[(PAGE_W - 2 * MARGIN - 12) / 2, (PAGE_W - 2 * MARGIN - 12) / 2])
    nz.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(nz)
    story.append(Spacer(1, 10))

    # Wall color
    story.append(Paragraph("Wall Color Suggestion", s["h3"]))
    story.append(
        _wall_color_block(
            deliverable.get("wall_color_name", ""),
            deliverable.get("wall_color_code", ""),
            deliverable.get("wall_color_hex", ""),
            deliverable.get("wall_color_note", ""),
        )
    )
    story.append(Spacer(1, 10))

    # Shopping list / budget
    shopping = deliverable.get("shopping_list") or []
    story.append(Paragraph("Shopping List & Estimated Budget", s["h3"]))
    story.append(_shopping_table(shopping))
    budget_note = deliverable.get("budget_note") or ""
    if budget_note:
        story.append(Spacer(1, 3))
        story.append(Paragraph(budget_note, s["muted"]))
    story.append(Spacer(1, 10))

    # Strategy + Action Plan + Benefits
    strategy = deliverable.get("strategy") or []
    action_plan = deliverable.get("action_plan") or []
    benefits = deliverable.get("benefits") or []

    if strategy:
        story.append(Paragraph("Design Strategy", s["h3"]))
        story.extend(_bullet_list(strategy, s["bullet"]))
        story.append(Spacer(1, 6))

    if action_plan:
        story.append(Paragraph("Simple Action Plan", s["h3"]))
        for i, step in enumerate(action_plan, 1):
            if step:
                story.append(Paragraph(f"{i}. {step}", s["bullet"]))
        story.append(Spacer(1, 6))

    if benefits:
        story.append(Paragraph("Benefits", s["h3"]))
        story.extend(_bullet_list(benefits, s["bullet"]))

    notes = deliverable.get("notes") or (
        "Important: All measurements are approximate. Confirm with a tape measure before purchasing."
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph(notes, s["muted"]))

    # --- Pages 2..N: Customer photos --------------------------------
    customer_photos: List[Optional[bytes]] = images.get("customer_photos") or []
    for idx, b in enumerate(customer_photos, 1):
        if not b:
            continue
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

    # --- Last page: Summary + Shopping Links -------------------------
    story.append(PageBreak())
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


def _fit_image(src: Optional[bytes], max_w: float, max_h: float) -> Any:
    if not src:
        return _placeholder(max_w, max_h, "Image not available")
    try:
        bio = io.BytesIO(src)
        ir = ImageReader(bio)
        iw, ih = ir.getSize()
        ratio = min(max_w / iw, max_h / ih)
        bio.seek(0)
        img = PlatypusImage(bio, width=iw * ratio, height=ih * ratio)
        img.hAlign = "CENTER"
        return img
    except Exception:
        return _placeholder(max_w, max_h, "Image unavailable")


def _product_links_from_plan(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    recommendations = plan.get("product_recommendations") or {}
    for store, items in recommendations.items():
        for item in items or []:
            term = item.get("term") or ""
            url = item.get("url") or ""
            if term and url:
                links.append({"name": f"{store}: {term}", "url": url})
    return links


def build_room_transformation_pdf(
    *,
    job: Dict[str, Any],
    plan: Dict[str, Any],
    original_images: List[Optional[bytes]],
    modified_images: List[Optional[bytes]],
) -> bytes:
    """Render the automated customer deliverable for a room transformation job."""
    buf = io.BytesIO()
    s = _styles()
    room = (job.get("room_type") or "Room").capitalize()
    customer_name = job.get("customer_name") or "there"

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
    doc = BaseDocTemplate(
        buf,
        pagesize=LETTER,
        pageTemplates=[
            PageTemplate(
                id="main",
                frames=[frame],
                onPage=lambda c, d: _draw_header(c, d, customer_name),
            )
        ],
        title=f"{room} Organization Plan - FlowSpace",
        author="FlowSpace",
    )

    story: List[Any] = []

    # Cover page
    story.append(Spacer(1, 0.35 * inch))
    story.append(Paragraph("FlowSpace Room Transformation", s["h1"]))
    story.append(Paragraph(f"{room} organization plan for {customer_name}", s["h2"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "A calm, practical plan for turning visual clutter into a room that feels easier to use, easier to reset, and more supportive of everyday wellbeing.",
            s["body"],
        )
    )
    story.append(Spacer(1, 16))
    meta_rows = [
        ["Room type", room],
        ["Pain point", job.get("pain_point") or "Not specified"],
        ["Budget", job.get("budget") or plan.get("estimated_budget") or "Not specified"],
        ["Preferred stores", ", ".join(job.get("preferred_stores") or ["Walmart", "Target", "IKEA"])],
        ["Rent/own", job.get("rent_or_own") or "Not specified"],
        ["Mounting allowed", "Yes" if job.get("mounting_allowed") else "No / renter-friendly preferred"],
    ]
    meta = Table(meta_rows, colWidths=[1.7 * inch, PAGE_W - 2 * MARGIN - 1.7 * inch])
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), SOFT_BG),
                ("TEXTCOLOR", (0, 0), (0, -1), BRAND_DARK),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 18))
    cover_image = modified_images[0] if modified_images else (original_images[0] if original_images else None)
    story.append(_fit_image(cover_image, PAGE_W - 2 * MARGIN, 3.4 * inch))

    # Image pages: before/after pairs
    pairs = max(len(original_images), len(modified_images))
    for idx in range(pairs):
        story.append(PageBreak())
        story.append(Paragraph(f"Room Photo {idx + 1}: Original and Organized", s["h2"]))
        story.append(Paragraph("The organized image should preserve the room structure, camera angle, walls, flooring, windows, doors, fixtures, and built-ins while changing only storage and organization elements.", s["muted"]))
        story.append(Spacer(1, 8))
        cw = (PAGE_W - 2 * MARGIN - 10) / 2
        before = _fit_image(original_images[idx] if idx < len(original_images) else None, cw, 4.2 * inch)
        after = _fit_image(modified_images[idx] if idx < len(modified_images) else None, cw, 4.2 * inch)
        table = Table(
            [
                [before, after],
                [Paragraph("Original upload", s["imgCaption"]), Paragraph("AI-organized concept", s["imgCaption"])],
            ],
            colWidths=[cw, cw],
        )
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(table)

    # Plan page
    story.append(PageBreak())
    story.append(Paragraph("Organization Strategy", s["h2"]))
    story.append(Paragraph(plan.get("room_summary") or "", s["body"]))
    story.append(Spacer(1, 8))

    if plan.get("organization_strategy"):
        story.append(Paragraph("Strategy", s["h3"]))
        story.extend(_bullet_list(plan.get("organization_strategy") or [], s["bullet"]))
        story.append(Spacer(1, 6))

    if plan.get("mental_health_benefits"):
        story.append(Paragraph("Mental-health benefits", s["h3"]))
        story.extend(_bullet_list(plan.get("mental_health_benefits") or [], s["bullet"]))
        story.append(Spacer(1, 6))

    solutions = plan.get("storage_solutions") or []
    if solutions:
        rows = [["Storage solution", "Why it helps", "Estimate"]]
        for solution in solutions:
            rows.append(
                [
                    Paragraph(solution.get("name", ""), s["body"]),
                    Paragraph(solution.get("why", ""), s["body"]),
                    Paragraph(solution.get("estimated_cost", ""), s["body"]),
                ]
            )
        t = Table(rows, colWidths=[1.8 * inch, 3.1 * inch, 1.0 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT_BG]),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(Paragraph("Storage solutions used", s["h3"]))
        story.append(t)
        story.append(Spacer(1, 8))

    story.append(Paragraph("DIY Step-by-step Build Guide", s["h2"]))
    for idx, step in enumerate(plan.get("diy_steps") or [], 1):
        story.append(Paragraph(f"{idx}. {step}", s["bullet"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Estimated difficulty:</b> {plan.get('estimated_difficulty') or 'Not specified'}", s["body"]))
    story.append(Paragraph(f"<b>Estimated time:</b> {plan.get('estimated_time') or 'Not specified'}", s["body"]))
    story.append(Paragraph(f"<b>Estimated budget:</b> {plan.get('estimated_budget') or job.get('budget') or 'Not specified'}", s["body"]))

    # Shopping page
    story.append(PageBreak())
    story.append(Paragraph("Shopping Links", s["h2"]))
    story.append(Paragraph("These are starter search links, not exact affiliate placements. Confirm measurements, reviews, and availability before purchasing.", s["muted"]))
    story.append(Spacer(1, 8))
    links = _product_links_from_plan(plan)
    if links:
        story.append(_links_table(links))
    else:
        story.extend(_bullet_list(plan.get("product_search_terms") or [], s["bullet"]))

    # Closing page
    story.append(PageBreak())
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("A calmer room starts with one repeatable system.", s["h1"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "You do not need a perfect room to feel relief. Start with one category, give it a clear home, and let each small reset create more space for focus, rest, and daily ease.",
            s["body"],
        )
    )
    story.append(Spacer(1, 18))
    story.append(_hr())
    story.append(Spacer(1, 8))
    story.append(Paragraph("Warmly,", s["body"]))
    story.append(Paragraph("<b>Ryan at FlowSpace</b>", s["body"]))
    story.append(Paragraph(TAGLINE, s["muted"]))

    doc.build(story)
    return buf.getvalue()
