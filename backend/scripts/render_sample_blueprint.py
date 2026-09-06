#!/usr/bin/env python3
"""Render a sample FlowSpace Blueprint PDF (no Mongo / AI / Stripe).

  cd backend
  python scripts/render_sample_blueprint.py

Writes:
  /tmp/flowspace-blueprint-sample.pdf
  /tmp/flowspace-blueprint-sample-pageN.png  (if PyMuPDF is installed)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf_generator import build_pdf  # noqa: E402

LEAD = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "space_type": "garage",
    "style_prefs": ["minimal", "natural"],
    "color_prefs": ["sage", "wood"],
    "desired_feeling": ["practical", "calm"],
}

DELIVERABLE = {
    "intro": "A garage that is easy to park in and easy to find things — same walls and windows, a calmer system.",
    "needs": ["Hidden storage for tools", "Clear floor for the car", "A landing zone by the door"],
    "zones": [
        {"title": "Parking Zone", "desc": "Keep the existing stall clear. No new walls."},
        {"title": "Storage Zone", "desc": "Bins and wall-mounted shelves on the existing wall."},
        {"title": "Circulation Zone", "desc": "Keep the walk path your photo already shows."},
        {"title": "Workbench", "desc": "Tools in labeled bins, not a new built-in."},
        {"title": "Door Drop", "desc": "Hooks and a basket for daily in-and-out."},
    ],
    "wall_color_name": "Sea Salt",
    "wall_color_code": "SW 6204",
    "wall_color_hex": "#cfd7d3",
    "wall_color_note": "Optional — consider if it helps the goal.",
    "shopping_list": [
        {"name": "Lidded bins", "qty": 6, "price": 12.0},
        {"name": "Wall shelves", "qty": 2, "price": 39.0},
        {"name": "Peg hooks", "qty": 8, "price": 4.0},
        {"name": "Label maker tape", "qty": 2, "price": 8.0},
        {"name": "Floor mat", "qty": 1, "price": 29.0},
    ],
    "budget_note": "$100 – $300 typical for this starter kit",
    "strategy": [
        "Keep the layout balanced",
        "Hide clutter in matching bins",
        "Leave a path to the car",
        "One home per tool family",
    ],
    "action_plan": ["Declutter", "Mount shelves", "Place bins", "Label homes"],
    "benefits": ["Less visual noise", "Better daily routine", "Easier to park"],
    "notes": "",
    "summary": "Organize the garage you already have.",
    "shopping_links": [{"name": "Bins", "url": "https://example.com/bins"}],
}


def main() -> None:
    out_pdf = Path("/tmp/flowspace-blueprint-sample.pdf")
    pdf = build_pdf(lead=LEAD, deliverable=DELIVERABLE, images={})
    out_pdf.write_bytes(pdf)
    print(f"wrote {out_pdf} ({len(pdf)} bytes)")
    try:
        import pymupdf
    except ImportError:
        print("install pymupdf to rasterize pages")
        return
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    print(f"pages {doc.page_count}")
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False)
        png = Path(f"/tmp/flowspace-blueprint-sample-page{i}.png")
        pix.save(str(png))
        print(f"wrote {png} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    main()
