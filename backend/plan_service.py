"""
FlowSpace plan generation service:
- Uses Gemini Nano Banana to generate a tidier version of each user-uploaded photo
- Uses GPT-5.2 to generate an organizing summary, materials, shopping list, total cost
- Renders a branded PDF (reportlab) matching the FlowSpace site design
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple

from PIL import Image
from emergentintegrations.llm.chat import (
    LlmChat,
    UserMessage,
    ImageContent,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# Brand colors (matches header / hero)
BRAND_GREEN = colors.HexColor("#10B981")
BRAND_GREEN_DARK = colors.HexColor("#059669")
BRAND_SAGE = colors.HexColor("#5C7A65")
BRAND_BLUE = colors.HexColor("#2563EB")
BRAND_INK = colors.HexColor("#0F172A")
BRAND_MUTE = colors.HexColor("#475569")
BRAND_SOFT = colors.HexColor("#F8FAFC")
BRAND_LINE = colors.HexColor("#E2E8F0")

PHOTO_LIMIT = 2  # AI generation cap per submission


# ------------------------------------------------------------------
# Image utilities
# ------------------------------------------------------------------
def _strip_data_url(s: str) -> Tuple[str, bytes]:
    """Return (mime, raw_bytes) for either a data:URL or plain base64 string."""
    if s.startswith("data:"):
        head, b64 = s.split(",", 1)
        m = re.match(r"data:([^;]+);base64", head)
        mime = m.group(1) if m else "image/jpeg"
    else:
        b64 = s
        mime = "image/jpeg"
    return mime, base64.b64decode(b64)


def _to_pil(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def _pil_to_b64(img: Image.Image, fmt: str = "JPEG", quality: int = 85) -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ------------------------------------------------------------------
# Gemini Nano Banana — tidier image generation
# ------------------------------------------------------------------
async def generate_tidier_image(
    source_data_url: str,
    space_type: str,
    goals: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a 'tidier' AI version of the user's photo.
    Returns base64 PNG string (no data: prefix) or None on failure.
    """
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY missing — skipping image generation")
        return None

    try:
        _, raw = _strip_data_url(source_data_url)
        # Downscale to keep request small
        src = _to_pil(raw)
        src.thumbnail((1024, 1024))
        src_b64 = _pil_to_b64(src, "JPEG", 80)

        goals_str = f" The owner's goals: {goals.strip()}." if goals else ""
        prompt = (
            f"Reimagine this {space_type} as a clean, beautifully organized version "
            f"of the SAME room. Keep the architecture, walls, doors, windows, lighting, "
            f"and the room's overall structure identical. Remove visual clutter, place "
            f"items neatly on shelves, in bins, and on hooks. Add tasteful storage "
            f"solutions (shelves, labeled bins, racks) only where they fit the space. "
            f"Photorealistic, natural daylight, magazine-quality interior shot."
            f"{goals_str}"
        )

        chat = (
            LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"flowspace-img-{uuid.uuid4()}",
                system_message="You are an interior design AI that transforms cluttered spaces into beautifully organized versions.",
            )
            .with_model("gemini", "gemini-3.1-flash-image-preview")
            .with_params(modalities=["image", "text"])
        )

        msg = UserMessage(
            text=prompt,
            file_contents=[ImageContent(src_b64)],
        )
        _, images = await chat.send_message_multimodal_response(msg)
        if not images:
            logger.warning("Gemini returned no images")
            return None
        # Return first image data (base64 string)
        return images[0]["data"]
    except Exception as e:
        logger.exception(f"Tidier image generation failed: {e}")
        return None


# ------------------------------------------------------------------
# GPT-5.2 — plan generation
# ------------------------------------------------------------------
async def generate_plan(
    space_type: str,
    goals: Optional[str],
    language: str = "en",
) -> Dict:
    """
    Returns dict with keys: summary, materials, shopping_list (list of {name,est_price}),
    total_estimated_cost, change_summary
    """
    fallback = {
        "summary": (
            "Start by sorting every item into Keep, Donate, and Toss. Group like items "
            "in clear, labeled bins. Use vertical wall storage to free floor space and "
            "place daily-use items at eye level."
        ),
        "materials": [
            "Heavy-duty wire shelving",
            "Stackable clear storage bins (medium + large)",
            "Pegboard with hook assortment",
            "Adhesive bin labels",
            "Overhead ceiling racks",
        ],
        "shopping_list": [
            {"name": "Stackable clear bins (set of 6)", "est_price": 48.0},
            {"name": "Wire shelving unit, 5-tier", "est_price": 89.0},
            {"name": "Pegboard + hook kit", "est_price": 35.0},
            {"name": "Label maker", "est_price": 22.0},
            {"name": "Ceiling-mount overhead rack", "est_price": 129.0},
        ],
        "total_estimated_cost": 323.0,
        "change_summary": (
            "Cleared visible clutter, moved items to labeled bins on wall-mounted "
            "shelving, and grouped tools by use-case so everything has a home."
        ),
    }

    if not EMERGENT_LLM_KEY:
        return fallback

    lang_name = {"es": "Spanish", "pt": "Brazilian Portuguese"}.get(language, "English")
    system = (
        "You are FlowSpace, a professional home-organization designer. "
        "Given a space type and the owner's goals, you produce a concise, practical "
        "organizing plan. ALWAYS respond with VALID JSON ONLY — no markdown, no prose, "
        "no code fences. Use realistic US retail prices in USD. "
        f"All natural-language strings in the JSON must be written in {lang_name}."
    )
    user_text = (
        "Generate a JSON object with EXACTLY these keys:\n"
        '  "summary": string (3-4 sentences of organizing suggestions specific to the goals),\n'
        '  "materials": string[] (5-7 short items, e.g. "Wall-mounted pegboard"),\n'
        '  "shopping_list": array of objects {"name": string, "est_price": number},\n'
        '  "total_estimated_cost": number (sum of est_price),\n'
        '  "change_summary": string (2 sentences describing what changed and why; '
        "this will sit beneath a before/after photo).\n\n"
        f"Space type: {space_type}\n"
        f"Owner's goals: {goals or 'A calmer, more functional space.'}"
    )

    try:
        chat = (
            LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"flowspace-plan-{uuid.uuid4()}",
                system_message=system,
            ).with_model("openai", "gpt-5.2")
        )
        # Plan generation is short — non-streaming for simplicity
        response = await chat.send_message(UserMessage(text=user_text))
        text = response if isinstance(response, str) else getattr(response, "content", str(response))
        # Strip code fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        plan = json.loads(text)
        # Normalize structure
        plan.setdefault("summary", fallback["summary"])
        plan.setdefault("materials", fallback["materials"])
        plan.setdefault("shopping_list", fallback["shopping_list"])
        plan.setdefault("change_summary", fallback["change_summary"])
        # Compute total if missing or zero
        if not plan.get("total_estimated_cost"):
            try:
                plan["total_estimated_cost"] = sum(
                    float(x.get("est_price", 0)) for x in plan["shopping_list"]
                )
            except Exception:
                plan["total_estimated_cost"] = fallback["total_estimated_cost"]
        return plan
    except Exception as e:
        logger.exception(f"GPT plan generation failed: {e}")
        return fallback


# ------------------------------------------------------------------
# PDF rendering
# ------------------------------------------------------------------
def _draw_logo(c: canvas.Canvas, x: float, y: float, size: float = 0.45 * inch):
    """Draw the FlowSpace line-art house with wave inside."""
    c.saveState()
    c.setStrokeColor(BRAND_SAGE)
    c.setLineWidth(2.2)
    c.setLineCap(1)
    c.setLineJoin(1)
    # House outline (scaled from 64x64 svg)
    s = size / 64.0
    # path: M10 32 L32 10 L54 32 L54 56 L10 56 Z (svg has y flipped)
    pts = [(10, 32), (32, 10), (54, 32), (54, 56), (10, 56)]
    pts_pdf = [(x + p[0] * s, y + (64 - p[1]) * s) for p in pts]
    p = c.beginPath()
    p.moveTo(*pts_pdf[0])
    for px, py in pts_pdf[1:]:
        p.lineTo(px, py)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    # Wave: M14 42 C24 34, 30 50, 40 42 C46 37, 50 42, 54 42
    w_pts = [(14, 42), (24, 34), (30, 50), (40, 42), (46, 37), (50, 42), (54, 42)]
    w_pdf = [(x + p[0] * s, y + (64 - p[1]) * s) for p in w_pts]
    p = c.beginPath()
    p.moveTo(*w_pdf[0])
    p.curveTo(*w_pdf[1], *w_pdf[2], *w_pdf[3])
    p.curveTo(*w_pdf[4], *w_pdf[5], *w_pdf[6])
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()

    # Wordmark
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(BRAND_INK)
    c.drawString(x + size + 8, y + size / 2 - 4, "FlowSpace")


def _para(text: str, font_size: int = 9, color=BRAND_MUTE, leading: float = 12) -> Paragraph:
    style = ParagraphStyle(
        name="P",
        fontName="Helvetica",
        fontSize=font_size,
        leading=leading,
        textColor=color,
        alignment=TA_LEFT,
    )
    return Paragraph(text, style)


def _draw_image_box(
    c: canvas.Canvas,
    img_bytes: bytes,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str = "",
):
    """Draw a rounded image box with a small label badge."""
    try:
        pil = _to_pil(img_bytes)
        # Resize to fit aspect-correctly inside w x h
        ratio = min(w / pil.width, h / pil.height)
        new_w, new_h = int(pil.width * ratio), int(pil.height * ratio)
        pil = pil.resize((new_w, new_h))
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=82)
        buf.seek(0)
        from reportlab.lib.utils import ImageReader
        img = ImageReader(buf)
        off_x = x + (w - new_w) / 2
        off_y = y + (h - new_h) / 2
        c.drawImage(img, off_x, off_y, width=new_w, height=new_h, mask="auto")
    except Exception as e:
        logger.warning(f"Image draw failed: {e}")
        c.setStrokeColor(BRAND_LINE)
        c.setFillColor(BRAND_SOFT)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        c.setFillColor(BRAND_MUTE)
        c.setFont("Helvetica", 9)
        c.drawCentredString(x + w / 2, y + h / 2, "Image unavailable")

    if label:
        c.setFillColor(BRAND_GREEN if label.lower() == "after" else colors.white)
        c.setStrokeColor(BRAND_LINE)
        tw = c.stringWidth(label, "Helvetica-Bold", 7) + 10
        c.roundRect(x + 6, y + h - 18, tw, 13, 6, fill=1, stroke=0)
        c.setFillColor(colors.white if label.lower() == "after" else BRAND_INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 11, y + h - 14, label.upper())


def _draw_wrapped(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    w: float,
    font: str = "Helvetica",
    size: int = 10,
    color=BRAND_INK,
    leading: float = 13,
) -> float:
    """Crude word-wrap. Returns new y (after the text block)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = (text or "").split()
    c.setFillColor(color)
    c.setFont(font, size)
    line = ""
    cy = y
    for word in words:
        candidate = (line + " " + word).strip()
        if stringWidth(candidate, font, size) <= w:
            line = candidate
        else:
            c.drawString(x, cy, line)
            cy -= leading
            line = word
    if line:
        c.drawString(x, cy, line)
        cy -= leading
    return cy


def _section_title(c: canvas.Canvas, label: str, x: float, y: float):
    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, label.upper())
    c.setStrokeColor(BRAND_GREEN)
    c.setLineWidth(0.8)
    c.line(x, y - 3, x + 24, y - 3)


def _affiliate_links(name: str) -> List[Tuple[str, str]]:
    """Placeholder search URLs (affiliate IDs added later)."""
    q = name.replace(" ", "+")
    return [
        ("Amazon", f"https://www.amazon.com/s?k={q}"),
        ("Walmart", f"https://www.walmart.com/search?q={q}"),
        ("Home Depot", f"https://www.homedepot.com/s/{q}"),
    ]


def build_pdf(
    *,
    lead_name: str,
    space_type: str,
    goals: Optional[str],
    plan: Dict,
    photo_pairs: List[Tuple[bytes, Optional[bytes]]],
    language: str = "en",
) -> bytes:
    """Render the personalized plan PDF and return its bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    # ----- HEADER -----
    _draw_logo(c, 0.6 * inch, height - 0.85 * inch)
    c.setFont("Helvetica", 8)
    c.setFillColor(BRAND_MUTE)
    c.drawRightString(width - 0.6 * inch, height - 0.55 * inch, "Personalized organizing plan")
    c.drawRightString(width - 0.6 * inch, height - 0.7 * inch, f"Prepared for {lead_name}")
    # Divider
    c.setStrokeColor(BRAND_LINE)
    c.line(0.6 * inch, height - 1.0 * inch, width - 0.6 * inch, height - 1.0 * inch)

    # ----- TITLE -----
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(BRAND_INK)
    title = f"Your {space_type.title()} — From cluttered to functional"
    c.drawString(0.6 * inch, height - 1.4 * inch, title)
    c.setFont("Helvetica", 10)
    c.setFillColor(BRAND_MUTE)
    if goals:
        _draw_wrapped(
            c,
            f"Your goals: {goals}",
            0.6 * inch,
            height - 1.65 * inch,
            width - 1.2 * inch,
            "Helvetica-Oblique",
            10,
            BRAND_MUTE,
            13,
        )

    # ----- TWO-COLUMN BODY -----
    col_gap = 0.3 * inch
    left_x = 0.6 * inch
    left_w = (width - 1.2 * inch - col_gap) * 0.58
    right_x = left_x + left_w + col_gap
    right_w = width - 1.2 * inch - left_w - col_gap

    y = height - 2.05 * inch

    # LEFT COLUMN — summary + photo pairs
    _section_title(c, "Suggestions", left_x, y)
    y -= 18
    y = _draw_wrapped(
        c,
        plan.get("summary", ""),
        left_x,
        y,
        left_w,
        "Helvetica",
        10,
        BRAND_INK,
        14,
    )
    y -= 8

    # Photo pairs
    box_h = 1.4 * inch
    box_gap = 0.12 * inch
    for idx, (before_b, after_b) in enumerate(photo_pairs):
        if y - box_h - 70 < 1 * inch:
            # New page if needed
            c.showPage()
            _draw_logo(c, 0.6 * inch, height - 0.85 * inch)
            y = height - 1.2 * inch

        pair_w = (left_w - box_gap) / 2
        _draw_image_box(c, before_b, left_x, y - box_h, pair_w, box_h, "Before")
        if after_b:
            _draw_image_box(
                c, after_b, left_x + pair_w + box_gap, y - box_h, pair_w, box_h, "After"
            )
        else:
            c.setStrokeColor(BRAND_LINE)
            c.setFillColor(BRAND_SOFT)
            c.roundRect(left_x + pair_w + box_gap, y - box_h, pair_w, box_h, 6, stroke=1, fill=1)
            c.setFillColor(BRAND_MUTE)
            c.setFont("Helvetica-Oblique", 9)
            c.drawCentredString(
                left_x + pair_w + box_gap + pair_w / 2,
                y - box_h / 2,
                "AI render pending",
            )
        y -= box_h + 8
        y = _draw_wrapped(
            c,
            plan.get("change_summary", ""),
            left_x,
            y,
            left_w,
            "Helvetica-Oblique",
            9,
            BRAND_MUTE,
            12,
        )
        y -= 6

    # RIGHT COLUMN
    ry = height - 2.05 * inch
    # Materials
    _section_title(c, "Materials used", right_x, ry)
    ry -= 18
    c.setFillColor(BRAND_INK)
    c.setFont("Helvetica", 10)
    for m in plan.get("materials", [])[:8]:
        c.setFillColor(BRAND_GREEN)
        c.circle(right_x + 3, ry + 3, 2, stroke=0, fill=1)
        c.setFillColor(BRAND_INK)
        ry = _draw_wrapped(c, m, right_x + 12, ry + 6, right_w - 12, "Helvetica", 10, BRAND_INK, 13)
        ry -= 2

    ry -= 6
    # Shopping list
    _section_title(c, "Shopping list", right_x, ry)
    ry -= 16
    c.setFillColor(BRAND_INK)
    c.setFont("Helvetica", 9)
    for item in plan.get("shopping_list", [])[:10]:
        name = str(item.get("name", ""))[:60]
        price = float(item.get("est_price", 0) or 0)
        c.setFillColor(BRAND_INK)
        c.setFont("Helvetica", 9.5)
        c.drawString(right_x, ry, name)
        c.setFillColor(BRAND_MUTE)
        c.drawRightString(right_x + right_w, ry, f"${price:,.2f}")
        ry -= 14

    ry -= 4
    # Total banner
    total = float(plan.get("total_estimated_cost", 0) or 0)
    c.setFillColor(BRAND_GREEN)
    c.roundRect(right_x, ry - 24, right_w, 28, 6, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x + 10, ry - 14, "Estimated total")
    c.drawRightString(right_x + right_w - 10, ry - 14, f"${total:,.2f}")
    ry -= 38

    # ----- AFFILIATE LINKS FOOTER -----
    # Move to a footer area at bottom
    footer_y = 1.4 * inch
    c.setStrokeColor(BRAND_LINE)
    c.line(0.6 * inch, footer_y + 10, width - 0.6 * inch, footer_y + 10)
    _section_title(c, "Where to buy", 0.6 * inch, footer_y - 4)
    fy = footer_y - 22
    c.setFont("Helvetica", 8.5)
    for item in plan.get("shopping_list", [])[:4]:
        name = str(item.get("name", ""))[:46]
        c.setFillColor(BRAND_INK)
        c.drawString(0.6 * inch, fy, name)
        lx = 3.4 * inch
        for label, url in _affiliate_links(name):
            c.setFillColor(BRAND_BLUE)
            c.linkURL(url, (lx, fy - 2, lx + 60, fy + 9), relative=0)
            c.drawString(lx, fy, label)
            lx += 60
        fy -= 12

    # ----- BOTTOM TAGLINE -----
    c.setFillColor(BRAND_MUTE)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(0.6 * inch, 0.5 * inch, "FlowSpace · Design your space. Find your calm.")
    c.drawRightString(width - 0.6 * inch, 0.5 * inch, "flowspace.app")

    c.showPage()
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------
async def build_plan_pdf_for_lead(lead: dict) -> bytes:
    """Top-level helper: takes a lead document and returns PDF bytes."""
    space_type = lead.get("space_type", "space")
    goals = lead.get("goals") or lead.get("biggest_challenge") or ""
    language = lead.get("language", "en")
    photos = lead.get("photos", []) or []

    # Generate up to PHOTO_LIMIT tidier versions
    photo_pairs: List[Tuple[bytes, Optional[bytes]]] = []
    for src in photos[:PHOTO_LIMIT]:
        try:
            _, raw = _strip_data_url(src)
        except Exception:
            continue
        tidier_b64 = await generate_tidier_image(src, space_type, goals)
        after_bytes: Optional[bytes] = None
        if tidier_b64:
            try:
                after_bytes = base64.b64decode(tidier_b64)
            except Exception:
                after_bytes = None
        photo_pairs.append((raw, after_bytes))

    # Generate plan text
    plan = await generate_plan(space_type, goals, language)

    return build_pdf(
        lead_name=lead.get("name", "there"),
        space_type=space_type,
        goals=goals,
        plan=plan,
        photo_pairs=photo_pairs,
        language=language,
    )
