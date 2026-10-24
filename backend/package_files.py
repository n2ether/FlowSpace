"""File names and file set for a delivered package.

Every surface that hands a customer or a reviewer files — the email, the admin
zip, the admin and member downloads — names them here:

    FlowSpace_<Project>_Design_Plan.png / .pdf
    FlowSpace_<Project>_Room_Flow.png / .pdf
    FlowSpace_<Project>_Companion_Guide.pdf
    FlowSpace_<Project>_View_01.jpg, _View_02.jpg, …

A review copy adds ``_DRAFT`` before the extension. A package carries exactly
one Companion Guide; ``assert_single_companion`` enforces it.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

PIECES = {
    "design_plan": "Design_Plan",
    "room_flow": "Room_Flow",
    "companion_guide": "Companion_Guide",
    "view": "View",
}
COMPANION_PIECE = PIECES["companion_guide"]


def project_stem(title: str) -> str:
    """``Nicholas's Nursery`` → ``Nicholas_Nursery``; ``Living Room`` → ``Living_Room``."""
    text = re.sub(r"['’]s\b", "", title or "")
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "_".join(words) or "Project"


def package_filename(title: str, piece: str, ext: str, *, index: Optional[int] = None, draft: bool = False) -> str:
    part = PIECES.get(piece, piece)
    if piece == "view":
        part = f"{part}_{int(index or 1):02d}"
    suffix = "_DRAFT" if draft else ""
    return f"FlowSpace_{project_stem(title)}_{part}{suffix}.{ext.lstrip('.')}"


def png_to_pdf(png: bytes, *, title: str = "") -> bytes:
    """One-page PDF of a board PNG, lossless, page sized to the image at 144 dpi."""
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.open(io.BytesIO(png))
    img.load()
    width, height = img.size
    page = (width * 72 / 144, height * 72 / 144)
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=page, pageCompression=1)
    if title:
        pdf.setTitle(title)
    pdf.setAuthor("FlowSpace")
    pdf.drawImage(ImageReader(img.convert("RGB")), 0, 0, width=page[0], height=page[1])
    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def companion_count(names: Iterable[str]) -> int:
    return sum(1 for name in names if f"_{COMPANION_PIECE}" in str(name) and str(name).lower().endswith(".pdf"))


class PackageFileError(ValueError):
    """A package file set that breaks the delivery rules."""


def assert_single_companion(attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Raise unless the downloadable files hold exactly one Companion Guide."""
    names = [a.get("filename") for a in attachments if not a.get("content_id")]
    count = companion_count(n for n in names if n)
    if count != 1:
        raise PackageFileError(f"A package must carry exactly one Companion Guide, found {count}.")
    return attachments


def package_file_set(
    *,
    title: str,
    board_png: Optional[bytes],
    zone_map_png: Optional[bytes],
    companion_pdf: bytes,
    views: Optional[List[bytes]] = None,
    draft: bool = False,
) -> List[Dict[str, Any]]:
    """Ordered ``{"filename", "data", "content_type", "piece"}`` rows for one package."""
    rows: List[Dict[str, Any]] = []
    for piece, png in (("design_plan", board_png), ("room_flow", zone_map_png)):
        if not png:
            continue
        rows.append({"filename": package_filename(title, piece, "png", draft=draft), "data": png, "content_type": "image/png", "piece": piece})
        try:
            pdf = png_to_pdf(png, title=f"{title} — FlowSpace {PIECES[piece].replace('_', ' ')}")
        except Exception as exc:
            logger.warning("Could not build the %s PDF; the PNG still goes out: %s", piece, exc)
            continue
        rows.append(
            {
                "filename": package_filename(title, piece, "pdf", draft=draft),
                "data": pdf,
                "content_type": "application/pdf",
                "piece": piece,
            }
        )
    for index, data in enumerate(views or [], start=1):
        rows.append({"filename": package_filename(title, "view", "jpg", index=index, draft=draft), "data": data, "content_type": "image/jpeg", "piece": "view"})
    rows.append(
        {
            "filename": package_filename(title, "companion_guide", "pdf", draft=draft),
            "data": companion_pdf,
            "content_type": "application/pdf",
            "piece": "companion_guide",
        }
    )
    if companion_count(r["filename"] for r in rows) != 1:
        raise PackageFileError("A package must carry exactly one Companion Guide.")
    return rows
