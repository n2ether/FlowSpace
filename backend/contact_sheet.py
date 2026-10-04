"""Contact sheet for review before a package is final.

One row per required room photo: SOURCE_0N beside AFTER_0N. A missing after
is an empty panel. The sheet never claims the customer board or PDF is final.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

from pdf_images import coerce_image_bytes
from photo_contain import contain_pixels

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
)

PAPER = (243, 238, 230)
INK = (42, 38, 34)
GREEN = (31, 61, 44)
MUTED = (110, 101, 92)
CARD = (255, 252, 248)
EMPTY = (236, 244, 239)
WHITE = (255, 255, 255)


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    paths = list(_FONT_CANDIDATES)
    if not bold:
        paths = list(reversed(paths))
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _open(data: Optional[bytes]) -> Optional[Image.Image]:
    raw = coerce_image_bytes(data)
    if not raw:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img.convert("RGB")
    except Exception:
        return None


def _panel(
    base: Image.Image,
    box: tuple,
    image: Optional[Image.Image],
    banner: str,
    *,
    empty_title: str,
    empty_sub: str,
) -> None:
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=12, fill=CARD)
    bar_h = 36
    photo_box = (x0 + 8, y0 + bar_h + 8, x1 - 8, y1 - 8)
    px0, py0, px1, py1 = photo_box
    pw, ph = max(1, px1 - px0), max(1, py1 - py0)
    if image is None:
        draw.rectangle(photo_box, fill=EMPTY)
        title_font = _font(22, bold=True)
        sub_font = _font(16)
        draw.text((px0 + 16, py0 + ph // 2 - 28), empty_title, font=title_font, fill=GREEN)
        draw.text((px0 + 16, py0 + ph // 2 + 4), empty_sub, font=sub_font, fill=MUTED)
    else:
        ox, oy, dw, dh = contain_pixels(image.width, image.height, pw, ph)
        fitted = image.resize((max(1, dw), max(1, dh)), Image.Resampling.LANCZOS)
        base.paste(fitted, (px0 + ox, py0 + oy))
    draw.rectangle((x0, y0, x1, y0 + bar_h), fill=GREEN)
    draw.text((x0 + 12, y0 + 8), banner, font=_font(16, bold=True), fill=WHITE)


def build_contact_sheet(
    pairs: Sequence[Dict[str, Any]],
    *,
    customer_name: str = "",
    incomplete: bool = False,
) -> bytes:
    """PNG review sheet. Rows are SOURCE_0N → AFTER_0N. Not a final deliverable."""
    rows: List[Dict[str, Any]] = [p for p in pairs if isinstance(p, dict)]
    if not rows:
        rows = [{}]
    width = 1600
    header_h = 96
    row_h = 460
    height = header_h + 24 + len(rows) * row_h
    base = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(base)
    draw.text((36, 18), "FLOWSPACE CONTACT SHEET", font=_font(22, bold=True), fill=GREEN)
    status = "DRAFT. Review version. Not yet approved. Customer release held."
    if incomplete:
        status = f"{status} A required after is still missing."
    draw.text((36, 52), status, font=_font(16, bold=True), fill=INK)
    who = (customer_name or "Customer").strip()
    note = f"{who}. Each row is one source photo and the after edited from that same camera."
    draw.text((36, 76), note[:140], font=_font(14), fill=MUTED)

    gap = 16
    inner_w = width - 72
    col_w = (inner_w - gap) // 2
    for index, pair in enumerate(rows):
        top = header_h + index * row_h
        label = str(pair.get("label") or f"SOURCE_{index + 1:02d}")
        after_label = str(pair.get("after_label") or f"AFTER_{index + 1:02d}")
        before = _open(pair.get("before"))
        after = _open(pair.get("after"))
        left = (36, top, 36 + col_w, top + row_h - 20)
        right = (36 + col_w + gap, top, 36 + col_w + gap + col_w, top + row_h - 20)
        _panel(
            base,
            left,
            before,
            label,
            empty_title=f"{label} missing",
            empty_sub="Source photo was not available.",
        )
        _panel(
            base,
            right,
            after,
            after_label,
            empty_title=f"{after_label} unavailable",
            empty_sub="Not filled from another angle.",
        )

    out = io.BytesIO()
    base.save(out, format="PNG", optimize=True)
    return out.getvalue()
