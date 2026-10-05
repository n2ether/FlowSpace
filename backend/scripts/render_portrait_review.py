#!/usr/bin/env python3
"""Render a portrait Blueprint, room-flow zone map, companion PDF, and customer email HTML.

Does not send email, does not call send-final or send-draft, and does not
run retry-automation. Image files already on disk are pasted as-is.

Examples:
  python scripts/render_portrait_review.py --out /tmp/portrait-review
  python scripts/render_portrait_review.py --out /tmp/portrait-review --fixture fixtures/nursery_nico.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from email_service import customer_email_html  # noqa: E402
from image_board import build_image_board  # noqa: E402
from pdf_generator import build_pdf, customer_project_title  # noqa: E402
from room_flow import build_zone_map  # noqa: E402
from blueprint_consistency import internal_record  # noqa: E402
from blueprint_presentation import build_presentation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(BACKEND / "fixtures" / "nursery_nico.json"))
    parser.add_argument("--out", default=str(BACKEND / "tmp" / "portrait-review"))
    args = parser.parse_args()

    doc = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    lead = doc["lead"]
    deliverable = doc["deliverable"]
    images = doc.get("images") or {}
    title = customer_project_title(lead, deliverable)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    board = build_image_board(lead=lead, deliverable=deliverable, images=images)
    pdf = build_pdf(lead=lead, deliverable=deliverable, images=images)
    zone_map = build_zone_map(lead=lead, deliverable=deliverable, images=images)
    zone_map_review = build_zone_map(lead=lead, deliverable=deliverable, images=images, review=True)
    html = customer_email_html(
        lead.get("name") or "there",
        lead.get("space_type") or "space",
        project_title=title,
        preview_src="board.png",
        room_flow_src="zone-map.png",
    )
    presentation = build_presentation(lead, deliverable, images, lead_id="local-preview")
    (out / "board.png").write_bytes(board)
    (out / "zone-map.png").write_bytes(zone_map)
    (out / "zone-map-review.png").write_bytes(zone_map_review)
    (out / "internal-record.json").write_text(
        json.dumps(internal_record(lead, deliverable), indent=2), encoding="utf-8"
    )
    (out / "companion.pdf").write_bytes(pdf)
    (out / "customer-email.html").write_text(html, encoding="utf-8")
    (out / "presentation.json").write_text(json.dumps(presentation, indent=2), encoding="utf-8")
    print(f"title: {title or presentation.get('headline')}")
    print(f"board: {out / 'board.png'}")
    print(f"zone map: {out / 'zone-map.png'} (review banner: zone-map-review.png)")
    print(f"internal record (admin only): {out / 'internal-record.json'}")
    print(f"pdf: {out / 'companion.pdf'}")
    print(f"email: {out / 'customer-email.html'}")
    print(f"phone model: {out / 'presentation.json'}")
    print("Live lead, admin auth, no send:")
    print("  GET /api/admin/leads/<id>/deliverable/board")
    print("  GET /api/admin/leads/<id>/deliverable/pdf")
    print("  GET /api/admin/leads/<id>/deliverable/zone-map[?review=1]")
    print("  GET /api/admin/leads/<id>/deliverable/internal-record")
    print("  GET /api/admin/leads/<id>/deliverable/email-preview")
    print("  open /admin/leads/<id>/blueprint at about 390px")


if __name__ == "__main__":
    main()
