"""Room organization plan (GPT) + branded PDF report + image utilities."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from emergentintegrations.llm.chat import LlmChat, UserMessage
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from plans import ROOM_LABELS, STYLE_LABELS

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

BRAND_GREEN = colors.HexColor("#10B981")
BRAND_GREEN_DARK = colors.HexColor("#059669")
BRAND_SAGE = colors.HexColor("#5C7A65")
BRAND_BLUE = colors.HexColor("#2563EB")
BRAND_INK = colors.HexColor("#0F172A")
BRAND_MUTE = colors.HexColor("#475569")
BRAND_SOFT = colors.HexColor("#F8FAFC")
BRAND_LINE = colors.HexColor("#E2E8F0")

DISCLAIMER = (
    "AI-generated room transformations are conceptual renderings and may not perfectly "
    "reflect actual dimensions, installation requirements, product availability, labor "
    "costs, or final results."
)


# ------------------------------------------------------------------ images
def strip_data_url(s: str) -> Tuple[str, bytes]:
    if s.startswith("data:"):
        head, b64 = s.split(",", 1)
        m = re.match(r"data:([^;]+);base64", head)
        mime = m.group(1) if m else "image/jpeg"
    else:
        b64, mime = s, "image/jpeg"
    return mime, base64.b64decode(b64)


def to_pil(b: bytes) -> Image.Image:
    return Image.open(io.BytesIO(b)).convert("RGB")


def downscale_to_data_uri(raw: bytes, max_side: int = 1280, quality: int = 85) -> str:
    img = to_pil(raw)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def add_watermark(raw: bytes, text: str = "FlowSpace · Free Preview") -> bytes:
    img = to_pil(raw)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(18, img.width // 22))
    except Exception:
        font = ImageFont.load_default()
    tw = draw.textlength(text, font=font)
    step = int(tw + 120)
    for y in range(0, img.height + step, step):
        for x in range(-step, img.width + step, step):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 70))
    watermarked = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    watermarked.save(buf, "JPEG", quality=88)
    return buf.getvalue()


# ------------------------------------------------------------------ prompt
def build_prompt(room_type: str, style: str) -> str:
    room = ROOM_LABELS.get(room_type, room_type)
    style_label = STYLE_LABELS.get(style, style)
    return (
        f"Using the uploaded {room} photo as the reference, create a realistic organized "
        f"version of this same space in a {style_label} style. "
        "Preserve exact room dimensions. Preserve walls, flooring, windows, doors, ceilings, "
        "architectural features, lighting, and room proportions. Do not remodel. Do not "
        "renovate. Do not change paint colors. Do not replace flooring. Do not move structural "
        "features. Do not transform the room into a different home. Only remove clutter and "
        "improve organization. Add realistic organization systems such as shelving, storage "
        "bins, labeled containers, garage racks, closet systems, pantry containers, cabinets, "
        "hooks, baskets, drawer organizers, laundry organizers, and wall storage systems. "
        "The final image should appear professionally organized, realistic, attainable, clean, "
        "bright, and visually appealing."
    )


# ------------------------------------------------------------------ affiliate
def affiliate_links(name: str) -> List[Dict[str, str]]:
    q = re.sub(r"\s+", "+", name.strip())
    return [
        {"store": "Amazon", "url": f"https://www.amazon.com/s?k={q}"},
        {"store": "Home Depot", "url": f"https://www.homedepot.com/s/{q}"},
        {"store": "Lowe's", "url": f"https://www.lowes.com/search?searchTerm={q}"},
        {"store": "The Container Store", "url": f"https://www.containerstore.com/s?q={q}"},
    ]


# ------------------------------------------------------------------ GPT plan
def _fallback_plan(room_type: str, style: str) -> Dict:
    room = ROOM_LABELS.get(room_type, room_type)
    return {
        "summary": (
            f"Start by clearing the floor of your {room.lower()} and sorting items into Keep, "
            "Donate, and Toss. Group like items into labeled bins and use vertical wall storage "
            "to free up floor space, keeping daily-use items at eye level."
        ),
        "organization_score": 88,
        "estimated_cost": 320.0,
        "estimated_time": "A weekend (6-8 hours)",
        "difficulty": "Easy",
        "steps": [
            {"title": "Clear the floor", "detail": "Remove all clutter and sort into keep, donate, toss."},
            {"title": "Install shelving", "detail": "Add wall-mounted or free-standing shelving units."},
            {"title": "Add labeled bins", "detail": "Group like items into clear, labeled containers."},
            {"title": "Create zones", "detail": "Define dedicated zones for each category of items."},
            {"title": "Maintain", "detail": "Adopt a quick weekly reset to keep the system working."},
        ],
        "materials": [
            "Heavy-duty wire shelving", "Stackable clear bins", "Pegboard + hooks",
            "Adhesive labels", "Overhead/wall racks",
        ],
        "shopping_list": [
            {"name": "Stackable clear bins (set of 6)", "quantity": 1, "reason": "Group and contain loose items", "price_range": "$40-$60", "est_price": 48.0},
            {"name": "5-tier wire shelving unit", "quantity": 1, "reason": "Vertical storage for boxes and supplies", "price_range": "$80-$110", "est_price": 89.0},
            {"name": "Pegboard + hook kit", "quantity": 1, "reason": "Keep tools and gear off the floor", "price_range": "$30-$45", "est_price": 35.0},
            {"name": "Label maker", "quantity": 1, "reason": "Make every bin easy to find", "price_range": "$18-$28", "est_price": 22.0},
            {"name": "Overhead storage rack", "quantity": 1, "reason": "Store seasonal items up high", "price_range": "$110-$140", "est_price": 129.0},
        ],
    }


async def generate_room_plan(room_type: str, style: str, language: str = "en") -> Dict:
    fallback = _fallback_plan(room_type, style)
    if not EMERGENT_LLM_KEY:
        return _attach_affiliates(fallback)

    lang_name = {"es": "Spanish", "pt": "Brazilian Portuguese"}.get(language, "English")
    room = ROOM_LABELS.get(room_type, room_type)
    style_label = STYLE_LABELS.get(style, style)
    system = (
        "You are FlowSpace, a professional home-organization designer. Given a room type and "
        "style, produce a concise, practical, achievable organizing plan. ALWAYS respond with "
        "VALID JSON ONLY — no markdown, no code fences. Use realistic US retail prices in USD. "
        f"All natural-language strings must be written in {lang_name}."
    )
    user_text = (
        "Generate a JSON object with EXACTLY these keys:\n"
        '  "summary": string (3-4 sentences),\n'
        '  "organization_score": number 0-100 (how organized the result is),\n'
        '  "estimated_cost": number (total USD),\n'
        '  "estimated_time": string (e.g. "A weekend (6-8 hours)"),\n'
        '  "difficulty": string ("Easy", "Moderate", or "Advanced"),\n'
        '  "steps": array of 5 objects {"title": string, "detail": string},\n'
        '  "materials": string[] (5-7 short items),\n'
        '  "shopping_list": array of 5-8 objects {"name": string, "quantity": number, '
        '"reason": string, "price_range": string (e.g. "$40-$60"), "est_price": number}.\n\n'
        f"Room type: {room}\nStyle: {style_label}"
    )
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"flowspace-plan-{uuid.uuid4()}",
            system_message=system,
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=user_text))
        text = response if isinstance(response, str) else getattr(response, "content", str(response))
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        plan = json.loads(text)
        for k, v in fallback.items():
            plan.setdefault(k, v)
        if not plan.get("estimated_cost"):
            try:
                plan["estimated_cost"] = sum(float(x.get("est_price", 0)) for x in plan["shopping_list"])
            except Exception:
                plan["estimated_cost"] = fallback["estimated_cost"]
        return _attach_affiliates(plan)
    except Exception as e:
        logger.exception(f"GPT plan generation failed: {e}")
        return _attach_affiliates(fallback)


def _attach_affiliates(plan: Dict) -> Dict:
    for item in plan.get("shopping_list", []):
        item["affiliate_links"] = affiliate_links(str(item.get("name", "")))
    return plan


# ------------------------------------------------------------------ PDF
def _logo(c: canvas.Canvas, x: float, y: float, size: float = 0.4 * inch):
    c.saveState()
    c.setStrokeColor(BRAND_SAGE)
    c.setLineWidth(2.2)
    c.setLineCap(1)
    c.setLineJoin(1)
    s = size / 64.0
    pts = [(10, 32), (32, 10), (54, 32), (54, 56), (10, 56)]
    pp = [(x + p[0] * s, y + (64 - p[1]) * s) for p in pts]
    path = c.beginPath()
    path.moveTo(*pp[0])
    for px, py in pp[1:]:
        path.lineTo(px, py)
    path.close()
    c.drawPath(path, stroke=1, fill=0)
    w_pts = [(14, 42), (24, 34), (30, 50), (40, 42), (46, 37), (50, 42), (54, 42)]
    wp = [(x + p[0] * s, y + (64 - p[1]) * s) for p in w_pts]
    path = c.beginPath()
    path.moveTo(*wp[0])
    path.curveTo(*wp[1], *wp[2], *wp[3])
    path.curveTo(*wp[4], *wp[5], *wp[6])
    c.drawPath(path, stroke=1, fill=0)
    c.restoreState()
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(BRAND_INK)
    c.drawString(x + size + 8, y + size / 2 - 4, "FlowSpace Solutions")


def _wrap(c, text, x, y, w, font="Helvetica", size=10, color=BRAND_INK, leading=13) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    c.setFillColor(color)
    c.setFont(font, size)
    line, cy = "", y
    for word in (text or "").split():
        cand = (line + " " + word).strip()
        if stringWidth(cand, font, size) <= w:
            line = cand
        else:
            c.drawString(x, cy, line)
            cy -= leading
            line = word
    if line:
        c.drawString(x, cy, line)
        cy -= leading
    return cy


def _section(c, label, x, y):
    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, label.upper())
    c.setStrokeColor(BRAND_GREEN)
    c.setLineWidth(0.8)
    c.line(x, y - 3, x + 24, y - 3)


def _image_box(c, raw: bytes, x, y, w, h, label=""):
    try:
        pil = to_pil(raw)
        ratio = min(w / pil.width, h / pil.height)
        nw, nh = int(pil.width * ratio), int(pil.height * ratio)
        pil = pil.resize((nw, nh))
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=82)
        buf.seek(0)
        c.drawImage(ImageReader(buf), x + (w - nw) / 2, y + (h - nh) / 2, width=nw, height=nh, mask="auto")
    except Exception:
        c.setStrokeColor(BRAND_LINE)
        c.setFillColor(BRAND_SOFT)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
    if label:
        c.setFillColor(BRAND_GREEN if label.lower() == "after" else colors.white)
        tw = c.stringWidth(label, "Helvetica-Bold", 7) + 10
        c.roundRect(x + 6, y + h - 18, tw, 13, 6, fill=1, stroke=0)
        c.setFillColor(colors.white if label.lower() == "after" else BRAND_INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 11, y + h - 14, label.upper())


def build_room_pdf(
    *, user_name: str, room_type: str, style: str, plan: Dict,
    pairs: list, with_affiliate: bool = True,
) -> bytes:
    """pairs: list of (before_bytes, after_bytes) tuples — one per uploaded photo."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    room = ROOM_LABELS.get(room_type, room_type)
    style_label = STYLE_LABELS.get(style, style)
    first_before, first_after = pairs[0] if pairs else (None, None)

    # Header
    _logo(c, 0.6 * inch, height - 0.85 * inch)
    c.setFont("Helvetica", 8)
    c.setFillColor(BRAND_MUTE)
    c.drawRightString(width - 0.6 * inch, height - 0.6 * inch, "AI Organization Report")
    c.drawRightString(width - 0.6 * inch, height - 0.73 * inch, f"Prepared for {user_name}")
    c.setStrokeColor(BRAND_LINE)
    c.line(0.6 * inch, height - 1.0 * inch, width - 0.6 * inch, height - 1.0 * inch)

    title = f"Your {room} — {style_label}"
    if len(pairs) > 1:
        title += f"  ({len(pairs)} views)"
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(BRAND_INK)
    c.drawString(0.6 * inch, height - 1.35 * inch, title)

    # Before / after (first photo)
    box_h = 1.7 * inch
    box_w = (width - 1.2 * inch - 0.2 * inch) / 2
    top = height - 1.55 * inch - box_h
    if first_before:
        _image_box(c, first_before, 0.6 * inch, top, box_w, box_h, "Before")
    if first_after:
        _image_box(c, first_after, 0.6 * inch + box_w + 0.2 * inch, top, box_w, box_h, "After")

    y = top - 0.25 * inch
    _section(c, "Organization plan", 0.6 * inch, y)
    y -= 16
    y = _wrap(c, plan.get("summary", ""), 0.6 * inch, y, width - 1.2 * inch, "Helvetica", 10, BRAND_INK, 14)
    y -= 6

    # Stats row
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BRAND_GREEN_DARK)
    stats = (
        f"Score: {plan.get('organization_score', '—')}/100      "
        f"Est. cost: ${float(plan.get('estimated_cost', 0)):,.0f}      "
        f"Time: {plan.get('estimated_time', '—')}      "
        f"Difficulty: {plan.get('difficulty', '—')}"
    )
    c.drawString(0.6 * inch, y, stats)
    y -= 18

    # Steps
    for i, step in enumerate(plan.get("steps", [])[:6], start=1):
        if y < 1.4 * inch:
            break
        c.setFillColor(BRAND_INK)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(0.6 * inch, y, f"{i}. {step.get('title', '')}")
        y -= 12
        y = _wrap(c, step.get("detail", ""), 0.8 * inch, y, width - 1.5 * inch, "Helvetica", 9, BRAND_MUTE, 12)
        y -= 4

    # Additional photos (pairs[1:]) on their own page(s)
    extra = pairs[1:]
    if extra:
        c.showPage()
        _logo(c, 0.6 * inch, height - 0.85 * inch)
        c.setStrokeColor(BRAND_LINE)
        c.line(0.6 * inch, height - 1.0 * inch, width - 0.6 * inch, height - 1.0 * inch)
        _section(c, "More transformations", 0.6 * inch, height - 1.25 * inch)
        eh = 1.5 * inch
        ew = (width - 1.2 * inch - 0.2 * inch) / 2
        ey = height - 1.45 * inch - eh
        for bef, aft in extra:
            if ey < 1.0 * inch:
                c.showPage()
                _logo(c, 0.6 * inch, height - 0.85 * inch)
                ey = height - 1.45 * inch - eh
            if bef:
                _image_box(c, bef, 0.6 * inch, ey, ew, eh, "Before")
            if aft:
                _image_box(c, aft, 0.6 * inch + ew + 0.2 * inch, ey, ew, eh, "After")
            ey -= eh + 0.3 * inch

    # New page for shopping list
    c.showPage()
    _logo(c, 0.6 * inch, height - 0.85 * inch)
    c.setStrokeColor(BRAND_LINE)
    c.line(0.6 * inch, height - 1.0 * inch, width - 0.6 * inch, height - 1.0 * inch)
    sy = height - 1.3 * inch
    _section(c, "Shopping list", 0.6 * inch, sy)
    sy -= 20
    for item in plan.get("shopping_list", [])[:10]:
        if sy < 1.6 * inch:
            break
        name = str(item.get("name", ""))
        price = item.get("price_range") or f"${float(item.get('est_price', 0)):,.0f}"
        c.setFillColor(BRAND_INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.6 * inch, sy, f"{name}  (x{item.get('quantity', 1)})")
        c.setFillColor(BRAND_MUTE)
        c.drawRightString(width - 0.6 * inch, sy, price)
        sy -= 13
        sy = _wrap(c, str(item.get("reason", "")), 0.6 * inch, sy, width - 1.2 * inch, "Helvetica-Oblique", 8.5, BRAND_MUTE, 11)
        if with_affiliate and item.get("affiliate_links"):
            lx = 0.6 * inch
            c.setFont("Helvetica", 8)
            for link in item["affiliate_links"]:
                c.setFillColor(BRAND_BLUE)
                label = link["store"]
                c.linkURL(link["url"], (lx, sy - 2, lx + 95, sy + 9), relative=0)
                c.drawString(lx, sy, label)
                lx += c.stringWidth(label, "Helvetica", 8) + 16
            sy -= 12
        sy -= 6

    # Total + disclaimer
    total = float(plan.get("estimated_cost", 0) or 0)
    c.setFillColor(BRAND_GREEN)
    c.roundRect(0.6 * inch, 1.15 * inch, width - 1.2 * inch, 26, 6, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.75 * inch, 1.23 * inch, "Estimated project total")
    c.drawRightString(width - 0.75 * inch, 1.23 * inch, f"${total:,.2f}")

    c.setFillColor(BRAND_MUTE)
    _wrap(c, DISCLAIMER, 0.6 * inch, 0.95 * inch, width - 1.2 * inch, "Helvetica-Oblique", 7.5, BRAND_MUTE, 10)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(0.6 * inch, 0.45 * inch, "FlowSpace Solutions · flowspace.solutions")

    c.showPage()
    c.save()
    return buf.getvalue()
