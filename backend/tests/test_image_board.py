"""Image board is the visual file. It must not invent an after or a floor plan."""
import io
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from image_board import board_layout, board_spec, build_image_board
from pdf_generator import build_pdf

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json"


def _jpeg(color, size=(640, 420)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _load():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def test_board_png_is_a_portrait_nonblank_image():
    lead, deliverable = _load()
    png = build_image_board(lead=lead, deliverable=deliverable, images={})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size[1] > img.size[0]
    ratio = img.size[1] / img.size[0]
    assert 1.45 <= ratio <= 1.55
    # Paper margin is drawn, not a full-bleed generated poster.
    corner = img.getpixel((4, 4))
    assert corner[0] > 220 and corner[1] > 210 and corner[2] > 200
    colors = img.getcolors(maxcolors=500000)
    assert colors is None or len(colors) > 8


def test_nursery_board_copy_matches_the_cleaned_plan():
    lead, deliverable = _load()
    spec = board_spec(lead, deliverable, {})
    assert spec["claims_organized_photo"] is False
    assert spec["hero_mode"] == "placeholder"
    assert spec["budget_display"] == "$174"
    assert spec["zones"][1] == "Diaper & Dress Zone"
    blob = json.dumps({k: spec[k] for k in ("moves", "products", "roadmap", "headline", "zones")}).lower()
    assert "cubby" not in blob
    assert "replace dresser drawers" not in blob
    assert "six-drawer" in blob or "dresser" in blob
    names = [row["name"].lower() for row in spec["products"]]
    assert any("anchor" in name for name in names)
    assert all("cubby" not in name for name in names)
    bodies = [move["body"].lower() for move in spec["moves"]]
    assert len(bodies) == len(set(bodies))
    for move in spec["moves"]:
        assert move["body"].lower().startswith(move["title"].lower())


def test_board_claims_after_only_when_the_render_exists():
    lead, deliverable = _load()
    after = _jpeg((20, 90, 70))
    before = _jpeg((150, 130, 100))
    spec = board_spec(
        lead,
        deliverable,
        {"front_view": after, "front_view_kind": "organized", "before": before, "after": after},
    )
    assert spec["hero_mode"] == "before_after"
    assert spec["claims_organized_photo"] is True
    assert spec["detail_sources"] == ["after_crop", "after_crop", "after_crop"]
    assert 2 <= len(spec["detail_sources"]) <= 4
    assert all("organized view" in caption.lower() for caption in spec["detail_captions"])
    assert spec["topdown"]["window"] == "WINDOW"
    assert spec["topdown"]["door"] == "DOOR"
    assert "CLEAR PATH" == spec["topdown"]["circulation"]
    assert "SLEEP" in spec["topdown"]["furniture"]
    assert spec["topdown"]["matches_after"] is True
    assert spec["topdown"]["approximate"] is True
    assert spec["space_theme"] is True
    assert spec["hero_before_overlay"] is False
    assert "astronaut" in spec["topdown"]["caption"].lower()
    assert spec["theme_line"] == "PLANETS · MOON · ROCKETS · ASTRONAUTS"
    names = [swatch["name"] for swatch in spec["palette"]]
    assert "Existing walls" in names
    assert "Natural oak" in names
    assert "Moon" in names
    assert "Rocket" in names
    assert "Planet" in names
    assert any(swatch["note"] == "Not repainted" for swatch in spec["palette"])
    assert any(swatch["note"] == "Space theme" for swatch in spec["palette"])
    images = {"front_view": after, "front_view_kind": "organized", "before": before, "after": after}
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    img = Image.open(io.BytesIO(png))
    hero = board_layout(board_spec(lead, deliverable, images))["hero"]
    x0, y0, x1, y1 = hero
    # The hero is the organized after. A before chip must not sit on top of it.
    for point in ((x0 + 24, y0 + 24), ((x0 + x1) // 2, (y0 + y1) // 2), (x0 + 24, y1 - 48)):
        pixel = img.getpixel(point)
        assert abs(pixel[0] - 20) < 8 and abs(pixel[1] - 90) < 8 and abs(pixel[2] - 70) < 8
        assert abs(pixel[0] - 150) > 20


def test_extra_views_are_captioned_by_focal_point():
    lead, deliverable = _load()
    after = _jpeg((20, 90, 70))
    images = {
        "front_view": after,
        "front_view_kind": "organized",
        "after": after,
        "view_1": _jpeg((12, 40, 180)),
        "view_2": _jpeg((180, 40, 40)),
        "view_3": _jpeg((40, 160, 70)),
    }
    spec = board_spec(lead, deliverable, images)
    assert spec["detail_sources"] == ["view_1", "view_2", "view_3"]
    assert spec["detail_captions"] == [
        "Dresser and changing station",
        "Rocker",
        "Door and circulation",
    ]


def test_nursery_pdf_hides_invent_disclaimer_when_the_after_exists():
    lead, deliverable = _load()
    after = _jpeg((20, 90, 70))
    before = _jpeg((150, 130, 100))
    pdf = build_pdf(
        lead=lead,
        deliverable=deliverable,
        images={
            "front_view": after,
            "front_view_kind": "organized",
            "before": before,
            "after": after,
        },
    )
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)
    low = text.lower()
    assert "final organized view" in low
    assert "do not invent an after" not in low
    assert "organized view unavailable" not in low
    assert "we do not invent an organized after" not in low
    assert "sleep sack" in low
    assert "no loose blankets" in low or "loose blankets" in low

    missing = build_pdf(
        lead=lead,
        deliverable=deliverable,
        images={"before": before, "front_view": before, "front_view_kind": "original"},
    )
    missing_low = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(missing)).pages).lower()
    assert "do not invent an after" in missing_low
    assert "organized view unavailable" in missing_low


def test_companion_keeps_the_full_zone_sentence_and_one_total():
    lead, deliverable = _load()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "bottom drawer" in text
    assert "bulky bedding" in text
    assert "Diaper & Dress Zone" in text
    assert "$174" in text
    assert "$124" not in text
    assert "$154" not in text
    assert "Large open cubby unit" not in text
    assert "Basket set to replace" not in text
    assert "safety" in text.lower()
    assert "climate" in text.lower()
    assert "68" in text
    assert "weekly reset" in text.lower() or "ten minutes" in text.lower()
