"""Diagonal DRAFT watermark for owner downloads of a package still in review.

Applied after rendering so the board and companion PDF layouts stay untouched.
"""
from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

WATERMARK_TEXT = "DRAFT"
_FILL = (180, 40, 40)
_ALPHA = 56


def _font(size: int) -> ImageFont.ImageFont:
    from pathlib import Path

    bold = Path(__file__).resolve().parent / "fonts" / "Inter-Bold.ttf"
    if bold.exists():
        return ImageFont.truetype(str(bold), size)
    return ImageFont.load_default(size=size)


def watermark_png(png: bytes, text: str = WATERMARK_TEXT) -> bytes:
    base = Image.open(io.BytesIO(png)).convert("RGBA")
    width, height = base.size
    size = max(24, int(min(width, height) * 0.22))
    face = _font(size)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=face)
    tile = Image.new("RGBA", (right - left + size, bottom - top + size), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((size // 2 - left, size // 2 - top), text, font=face, fill=(*_FILL, _ALPHA))
    tile = tile.rotate(30, expand=True, resample=Image.BICUBIC)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for centre in (0.2, 0.5, 0.8):
        overlay.paste(tile, ((width - tile.width) // 2, int(height * centre - tile.height / 2)), tile)
    out = Image.alpha_composite(base, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _pdf_stamp(width: float, height: float, text: str) -> bytes:
    from reportlab.lib.colors import Color
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.saveState()
    c.setFillColor(Color(_FILL[0] / 255, _FILL[1] / 255, _FILL[2] / 255, alpha=0.18))
    c.setFont("Helvetica-Bold", min(width, height) * 0.22)
    c.translate(width / 2, height / 2)
    c.rotate(35)
    c.drawCentredString(0, -min(width, height) * 0.08, text)
    c.restoreState()
    c.setFillColor(Color(_FILL[0] / 255, _FILL[1] / 255, _FILL[2] / 255, alpha=0.85))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(18, height - 16, f"{text} — in review, not final")
    c.save()
    return buf.getvalue()


def watermark_pdf(pdf: bytes, text: str = WATERMARK_TEXT) -> bytes:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(pdf))
    writer = PdfWriter()
    stamps: dict = {}
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        key = (round(width), round(height))
        if key not in stamps:
            stamps[key] = PdfReader(io.BytesIO(_pdf_stamp(width, height, text))).pages[0]
        page.merge_page(stamps[key])
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def needs_draft_watermark(deliverable: Optional[dict]) -> bool:
    from design_plan_standards import is_released

    return not is_released(deliverable)
