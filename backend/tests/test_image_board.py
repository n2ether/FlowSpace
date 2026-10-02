"""Image board is the visual file. It must not invent an after or a floor plan."""
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader

from image_board import board_layout, board_spec, build_image_board, customer_board_text, plan_geometry
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


def _png(color, size):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _quadrant(width, height):
    img = Image.new("RGB", (width, height), (220, 20, 20))
    draw = ImageDraw.Draw(img)
    mid_x, mid_y = width // 2, height // 2
    draw.rectangle((0, 0, mid_x - 1, mid_y - 1), fill=(220, 20, 20))
    draw.rectangle((mid_x, 0, width - 1, mid_y - 1), fill=(20, 20, 220))
    draw.rectangle((0, mid_y, mid_x - 1, height - 1), fill=(20, 180, 40))
    draw.rectangle((mid_x, mid_y, width - 1, height - 1), fill=(220, 200, 20))
    return img


def _near(pixel, expected, tol=22) -> bool:
    return all(abs(int(pixel[i]) - expected[i]) <= tol for i in range(3))


LEAD_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"


def test_portrait_hero_is_larger_without_cropping_and_board_hides_internal_codes(monkeypatch):
    """The old multi-photo board capped a 1:2 hero near 417px and captioned SOURCE_/AFTER_."""
    lead, deliverable = _load()
    lead = {**lead, "id": LEAD_ID}
    frames = []
    for _ in range(4):
        buf = io.BytesIO()
        _quadrant(240, 480).save(buf, format="PNG")
        frames.append(buf.getvalue())
    images = {
        "front_view": frames[0],
        "front_view_kind": "organized",
        "before": frames[0],
        "after": frames[0],
        "source_pairs": [
            {
                "label": f"SOURCE_{i + 1:02d}",
                "after_label": f"AFTER_{i + 1:02d}",
                "before": frames[i],
                "after": frames[i],
                "status": "approved",
            }
            for i in range(4)
        ],
    }
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    blob = "\n".join(drawn)
    assert "SOURCE_" not in blob
    assert "AFTER_" not in blob
    assert LEAD_ID not in blob
    assert not re.search(r"\bDRAFT\b", blob, re.I)
    assert not re.search(r"\bQA\b", blob)
    spec = board_spec(lead, deliverable, images)
    assert "SOURCE_" not in customer_board_text(spec)
    assert "AFTER_" not in customer_board_text(spec)
    layout = board_layout(spec)
    hero = layout["hero"]
    hw, hh = hero[2] - hero[0], hero[3] - hero[1]
    assert hh >= 560
    assert hw * hh >= int(208 * 417 * 1.5)
    assert 0.45 <= hw / hh <= 0.58
    board = Image.open(io.BytesIO(png))
    assert _near(board.getpixel((hero[0] + 14, hero[1] + 14)), (220, 20, 20))
    assert _near(board.getpixel((hero[2] - 14, hero[1] + 14)), (20, 20, 220))
    assert _near(board.getpixel((hero[0] + 14, hero[3] - 48)), (20, 180, 40))
    assert _near(board.getpixel((hero[2] - 14, hero[3] - 48)), (220, 200, 20))
    assert b"SOURCE_" not in png
    assert LEAD_ID.encode() not in png


def test_room_plan_is_a_topdown_room_not_only_horizontal_bars():
    lead, deliverable = _load()
    spec = board_spec(lead, deliverable, {})
    topdown = spec["topdown"]
    assert topdown["drawing"] == "room"
    ids = {place["id"] for place in topdown["places"]}
    assert {"sleep", "change", "comfort", "play"} <= ids
    assert "SLEEP" in topdown["furniture"]
    # Even inside a short wide card, furniture stays on walls instead of spanning the room.
    geo = plan_geometry((36, 900, 1164, 1220), topdown)
    room = geo["room"]
    rw, rh = room[2] - room[0], room[3] - room[1]
    assert rh >= 140
    assert rw / rh <= 2.4
    for place in geo["places"]:
        rect = place["rect"]
        assert rect[2] - rect[0] <= int(rw * 0.58) + 1
        assert rect[0] >= room[0] and rect[2] <= room[2]
    png = build_image_board(lead=lead, deliverable=deliverable, images={})
    board = Image.open(io.BytesIO(png))
    laid = plan_geometry(board_layout(spec)["plan"], topdown)
    floor = (250, 246, 239)
    soft = (207, 226, 215)
    open_hits = 0
    block_hits = 0
    rx0, ry0, rx1, ry1 = laid["room"]
    rects = [place["rect"] for place in laid["places"]]
    for y in range(ry0 + 16, ry1 - 16, 6):
        for x in range(rx0 + 16, rx1 - 16, 6):
            inside = any(r[0] + 2 <= x <= r[2] - 2 and r[1] + 2 <= y <= r[3] - 2 for r in rects)
            pixel = board.getpixel((x, y))
            if inside and _near(pixel, soft, tol=28):
                block_hits += 1
            if not inside and _near(pixel, floor, tol=12):
                open_hits += 1
    assert block_hits > 20
    assert open_hits > 20


def test_landscape_hero_reaches_across_the_board():
    lead, deliverable = _load()
    frame = _png((30, 90, 70), (900, 600))
    images = {
        "front_view": frame,
        "front_view_kind": "organized",
        "before": frame,
        "after": frame,
        "source_pairs": [
            {"label": f"SOURCE_{i + 1:02d}", "after_label": f"AFTER_{i + 1:02d}", "before": frame, "after": frame}
            for i in range(4)
        ],
    }
    layout = board_layout(board_spec(lead, deliverable, images))
    hero = layout["hero"]
    content_w = 1200 - 72
    assert (hero[2] - hero[0]) >= int(content_w * 0.78)
    assert abs(((hero[2] - hero[0]) / (hero[3] - hero[1])) - 1.5) < 0.05
