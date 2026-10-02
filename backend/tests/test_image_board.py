"""Image board is the visual file. It must not invent an after or a floor plan."""
import io
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from image_board import board_spec, build_image_board
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


def test_board_png_is_a_wide_nonblank_image():
    lead, deliverable = _load()
    png = build_image_board(lead=lead, deliverable=deliverable, images={})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size[0] > img.size[1]
    assert img.size[0] >= 2000
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
    names = [swatch["name"] for swatch in spec["palette"]]
    assert "Existing walls" in names
    assert "Natural oak" in names
    assert any(swatch["note"] == "Not repainted" for swatch in spec["palette"])
    assert any(swatch["note"] == "Space theme" for swatch in spec["palette"])
    png = build_image_board(
        lead=lead,
        deliverable=deliverable,
        images={"front_view": after, "front_view_kind": "organized", "before": before, "after": after},
    )
    img = Image.open(io.BytesIO(png))
    # Right half of the hero is the organized after (solid test color).
    for point in ((200, 400), (980, 500)):
        pixel = img.getpixel(point)
        assert abs(pixel[0] - 20) < 8 and abs(pixel[1] - 90) < 8 and abs(pixel[2] - 70) < 8


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
