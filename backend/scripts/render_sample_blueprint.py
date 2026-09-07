#!/usr/bin/env python3
"""Render a sample FlowSpace Blueprint PDF (no Mongo / AI / Stripe).

Uses the bake-off garage fixture so the six Brain layers are customer-visible.

  cd backend
  python scripts/render_sample_blueprint.py

Writes:
  backend/samples/flowspace-blueprint-sample.pdf
  backend/samples/flowspace-blueprint-sample-pageN.png  (if PyMuPDF is installed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pdf_generator import build_pdf  # noqa: E402

FIXTURE = ROOT / "fixtures" / "bakeoff" / "garage_org_space.json"


def load_fixture() -> tuple[dict, dict]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def main() -> None:
    lead, deliverable = load_fixture()
    out_dir = ROOT / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / "flowspace-blueprint-sample.pdf"
    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    out_pdf.write_bytes(pdf)
    print(f"wrote {out_pdf} ({len(pdf)} bytes) from {FIXTURE.relative_to(ROOT)}")
    try:
        import pymupdf
    except ImportError:
        print("install pymupdf to rasterize pages")
        return
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    print(f"pages {doc.page_count}")
    for stale in out_dir.glob("flowspace-blueprint-sample-page*.png"):
        stale.unlink()
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False)
        png = out_dir / f"flowspace-blueprint-sample-page{i}.png"
        pix.save(str(png))
        print(f"wrote {png} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    main()
