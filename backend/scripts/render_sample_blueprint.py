#!/usr/bin/env python3
"""Render sample FlowSpace Blueprint PDFs (no Mongo / AI / Stripe).

Uses the bake-off garage fixture (organization plan — not a bedroom redesign).

  cd backend
  python scripts/render_sample_blueprint.py

Writes:
    backend/samples/flowspace-blueprint-sample.pdf
        Synthetic original (``before``) + organized FLUX stand-in (``after`` /
        ``front_view``) + three extra views. Page 1 is the dashboard; page 2 is
        DIY + shopping. Before | After is a short page 3 when photos exist.
    backend/samples/flowspace-blueprint-sample-placeholders.pdf
        Same plan with ``images={}`` — mint “Organized view coming soon” hero.
    backend/samples/flowspace-blueprint-sample-pageN.png
    backend/samples/flowspace-blueprint-placeholders-pageN.png
        Rasterized pages when PyMuPDF is installed.

Image keys expected by build_pdf() are documented in backend/pdf_images.py.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf_generator import build_pdf  # noqa: E402
from pdf_images import assemble_pdf_images  # noqa: E402

FIXTURE = ROOT / "fixtures" / "bakeoff" / "garage_org_space.json"


def load_fixture() -> tuple[dict, dict]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def _synthetic_original_jpeg(width: int = 960, height: int = 640) -> bytes:
    """Stand-in for the customer's uploaded before photo."""
    img = Image.new("RGB", (width, height), (196, 176, 148))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, int(height * 0.62), width, height], fill=(92, 78, 58))
    draw.rectangle([0, 0, width, int(height * 0.62)], fill=(168, 148, 120))
    # Same window placement as the organized render (shell preserved)
    draw.rectangle([int(width * 0.62), 48, int(width * 0.90), int(height * 0.36)], fill=(140, 168, 188), outline=(80, 70, 50), width=6)
    # Clutter piles
    for i, x0 in enumerate((48, 170, 292, 414)):
        draw.rectangle([x0, 90 + (i % 2) * 20, x0 + 100, int(height * 0.58)], fill=(110, 72, 48), outline=(70, 50, 30), width=2)
    draw.ellipse([80, int(height * 0.68), 200, int(height * 0.88)], fill=(70, 60, 50))
    draw.ellipse([240, int(height * 0.72), 360, int(height * 0.92)], fill=(90, 70, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _synthetic_organized_jpeg(width: int = 960, height: int = 640) -> bytes:
    """Stand-in for a FLUX organized render — not a customer photo."""
    img = Image.new("RGB", (width, height), (236, 253, 245))
    draw = ImageDraw.Draw(img)
    # Floor / wall
    draw.rectangle([0, int(height * 0.58), width, height], fill=(226, 232, 240))
    draw.rectangle([0, 0, width, int(height * 0.58)], fill=(248, 250, 252))
    # Window (shell preserved)
    draw.rectangle([int(width * 0.62), 48, int(width * 0.90), int(height * 0.36)], fill=(186, 230, 253), outline=(5, 150, 105), width=6)
    # Matching bins / shelves
    shelf_y = int(height * 0.42)
    draw.rectangle([40, 80, int(width * 0.52), shelf_y], fill=(16, 185, 129), outline=(4, 120, 87), width=3)
    for i in range(4):
        x0 = 56 + i * 110
        draw.rectangle([x0, shelf_y + 16, x0 + 96, int(height * 0.78)], fill=(5, 150, 105), outline=(4, 120, 87), width=2)
    draw.rectangle([int(width * 0.12), int(height * 0.82), int(width * 0.88), int(height * 0.94)], fill=(15, 23, 42))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _rasterize(pdf: bytes, out_dir: Path, stem: str) -> None:
    try:
        import pymupdf
    except ImportError:
        print("install pymupdf to rasterize pages")
        return
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    print(f"{stem}: pages {doc.page_count}")
    for stale in out_dir.glob(f"{stem}-page*.png"):
        stale.unlink()
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False)
        png = out_dir / f"{stem}-page{i}.png"
        pix.save(str(png))
        print(f"wrote {png} ({pix.width}x{pix.height})")


def main() -> None:
    lead, deliverable = load_fixture()
    out_dir = ROOT / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    empty = build_pdf(lead=lead, deliverable=deliverable, images={})
    empty_pdf = out_dir / "flowspace-blueprint-sample-placeholders.pdf"
    empty_pdf.write_bytes(empty)
    print(f"wrote {empty_pdf} ({len(empty)} bytes) images={{}}")

    original = _synthetic_original_jpeg()
    organized = _synthetic_organized_jpeg()
    images = assemble_pdf_images(
        hero_bytes=organized,
        hero_kind="organized",
        before=original,
        after=organized,
        view_1=_synthetic_organized_jpeg(480, 320),
        view_2=_synthetic_organized_jpeg(420, 300),
        view_3=_synthetic_original_jpeg(420, 300),
        customer_photos=[original],
    )
    filled = build_pdf(lead=lead, deliverable=deliverable, images=images)
    filled_pdf = out_dir / "flowspace-blueprint-sample.pdf"
    filled_pdf.write_bytes(filled)
    print(f"wrote {filled_pdf} ({len(filled)} bytes) with before + after + front_view")

    _rasterize(filled, out_dir, "flowspace-blueprint-sample")
    _rasterize(empty, out_dir, "flowspace-blueprint-placeholders")


if __name__ == "__main__":
    main()
