"""Image board is the visual file. It must not invent an after or a floor plan."""
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from blueprint_presentation import build_presentation
from copy_shape import ends_dangling
from image_board import (
    board_layout,
    board_spec,
    build_image_board,
    customer_board_text,
)
from pdf_generator import build_pdf, customer_project_title

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
    assert spec["headline"] == "Nicholas's Nursery"
    assert spec["plan_title"] == "Nicholas's Nursery"
    assert "Camila's Kids" not in spec["headline"]
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
        assert not ends_dangling(move["title"]) and not move["title"].endswith(".")
        assert move["body"].endswith(".") and not ends_dangling(move["body"])


def test_possessive_nursery_in_the_outcome_names_the_title():
    """The live outcome says "Nicholas's nursery" and never "is turning"."""
    lead = {
        "name": "Camila Sales",
        "space_type": "kids_room",
        "goals": "Keep the space theme and make the nursery safer and calmer.",
    }
    outcome = (
        "Camila, this refresh transforms Nicholas's nursery into a safer, warmer, "
        "calmer haven without changing a single wall or replacing a single piece of furniture."
    )
    deliverable = {"summary": outcome, "intro": "A calmer room.", "shopping_list": []}
    assert customer_project_title(lead, deliverable) == "Nicholas's Nursery"
    spec = board_spec(lead, deliverable, {})
    assert spec["headline"] == "Nicholas's Nursery"
    assert spec["plan_title"] == "Nicholas's Nursery"
    view = build_presentation(lead, deliverable, {})
    assert view["headline"] == "Nicholas's Nursery"
    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)
    assert "Nicholas's Nursery" in text

    curly = outcome.replace("Nicholas's", "Nicholas\u2019s")
    assert customer_project_title(lead, {"summary": curly}) == "Nicholas's Nursery"
    assert customer_project_title(lead, {"summary": "This refresh is for Nicholas' nursery."}) == "Nicholas's Nursery"

    # A name that is not tied to the child stays the generic nursery title.
    assert customer_project_title(lead, {"summary": "Camila's nursery stays as it is."}) == "Nursery"
    assert customer_project_title(lead, {"summary": "A calmer room for the toddler."}) == "Nursery"
    assert customer_project_title(
        {"name": "Ada", "space_type": "garage", "goals": "Park the cars."},
        {"summary": "Nicholas's nursery is not this garage."},
    ) == ""


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
    assert "CRIB" in spec["topdown"]["furniture"]
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
    low = " ".join(text.lower().split())
    assert "organized view" in low
    assert "final organized" not in low
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


def test_companion_is_the_short_customer_guide_with_one_total():
    lead, deliverable = _load()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    text = " ".join(
        "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages).split()
    )
    low = text.lower()
    for heading in ("SAFETY ESSENTIALS", "CLIMATE COMFORT", "WHY THE FLOWSPACE ZONE APPROACH HELPS", "SHOPPING LIST", "LIST TOTAL"):
        assert heading in text
    for idea in ("open path", "fewer decisions", "reset", "calmer"):
        assert idea in low
    assert "six-drawer dresser" in low
    assert "$174" in text
    assert "Nicholas's Nursery" in text
    assert "Camila's Kids" not in text
    assert "$124" not in text
    assert "$154" not in text
    assert "Large open cubby unit" not in text
    assert "Basket set to replace" not in text
    assert "68" in text
    # The Do Not list, notes, zone essays, steps, and the ritual stay in the internal record.
    assert "do not" not in low
    assert "notes:" not in low
    assert "Diaper & Dress Zone" not in text
    assert "step by step" not in low
    assert "bedtime ritual" not in low
    assert "towel" not in low
    assert "rabbit" not in low
    assert "measurements are approximate" not in low
    assert "9dbedfba" not in text
    assert "SOURCE_" not in text and "AFTER_" not in text
    assert not re.search(r"\bQA\b", text)


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
    # "draft sweep" is a real shopping line. A review DRAFT label is not.
    assert not re.search(r"\bDRAFT\b", re.sub(r"draft sweep", "", blob, flags=re.I), re.I)
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


def test_room_flow_card_is_the_measured_zone_map():
    """The card draws Camila's zone map: measured outline, door at the lower-left corner."""
    lead, deliverable = _load()
    spec = board_spec(lead, deliverable, {})
    topdown = spec["topdown"]
    assert topdown["drawing"] == "zone_map"
    assert topdown["measured_outline"] is True
    assert topdown["approximate"] is True
    assert topdown["board_caption"] == "Room outline based on your measurements. Furniture footprints and zones are approximate."
    assert "not a measured" not in topdown["caption"].lower()
    assert [item["name"] for item in topdown["legend"]] == ["Sleep", "Change", "Comfort", "Play + Storage"]
    assert {"DRESSER", "CRIB", "ROCKER", "RUG + BASKET"} <= set(topdown["furniture"])
    flow = topdown["room_flow"]
    assert flow["walls"][3] == {"door": True}
    door = (flow["outline"][3], flow["outline"][4])
    assert max(p[0] for p in door) < 1.0 and min(p[1] for p in door) > 2.0
    png = build_image_board(lead=lead, deliverable=deliverable, images={})
    board = Image.open(io.BytesIO(png))
    x0, y0, x1, y1 = board_layout(spec)["plan"]
    crop = board.crop((x0, y0, x1, y1)).convert("RGB")
    colors = {pixel for pixel in crop.getdata()}
    # Wall green, zone tints, and furniture fills are all painted inside the card.
    assert (36, 72, 52) in colors
    assert (219, 233, 225) in colors
    assert (237, 217, 192) in colors


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


def _drawn_text(monkeypatch, lead, deliverable, images):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    build_image_board(lead=lead, deliverable=deliverable, images=images)
    return "\n".join(drawn)


def test_editorial_changes_are_a_compact_grid_and_shopping_is_itemized():
    lead, deliverable = _load()
    frames = []
    for _ in range(4):
        buf = io.BytesIO()
        _quadrant(240, 480).save(buf, format="PNG")
        frames.append(buf.getvalue())
    images = {
        "source_pairs": [
            {"label": f"SOURCE_{i + 1:02d}", "after_label": f"AFTER_{i + 1:02d}", "before": frames[i], "after": frames[i]}
            for i in range(4)
        ]
    }
    spec = board_spec(lead, deliverable, images)
    layout = board_layout(spec)
    changes_h = layout["changes"][3] - layout["changes"][1]
    assert 280 <= changes_h <= 360
    shopping = layout["shopping"]
    assert shopping[3] - shopping[1] >= 80
    assert layout["changes"][3] <= shopping[1]
    assert shopping[3] <= layout["sources"][0][1]
    assert spec["products"]
    assert spec["budget_display"] == "$174"


def test_board_paints_zones_title_and_shopping_lines(monkeypatch):
    lead, deliverable = _load()
    blob = _drawn_text(monkeypatch, lead, deliverable, {})
    assert "Nicholas's Nursery" in blob
    assert "Camila's Kids" not in blob
    assert "Change" in blob
    assert "Room outline based on your measurements. Furniture footprints and zones are approximate." in blob
    assert "Not measured" not in blob
    assert "Play/Storage" not in blob
    assert "SHOPPING" in blob
    assert "$174" in blob
    assert "more in the companion guide" in blob
    assert any("anchor" in line.lower() for line in blob.splitlines())
    assert "SOURCE_" not in blob
    assert "AFTER_" not in blob


def test_board_drops_a_lone_total_when_there_are_no_line_items(monkeypatch):
    lead, deliverable = _load()
    deliverable = {**deliverable, "shopping_list": [], "budget_note": "Total $240.", "budget_display": "$240"}
    blob = _drawn_text(monkeypatch, lead, deliverable, {})
    assert "$240" not in blob
    assert "$" not in blob
    assert "SHOPPING" not in blob


def test_nursery_changes_merge_preserve_drawers_and_routine():
    lead, deliverable = _load()
    moves = board_spec(lead, deliverable, {})["moves"]
    assert len(moves) == 4
    assert len({move["title"].lower() for move in moves}) == 4
    for move in moves:
        assert not ends_dangling(move["title"]) and not move["title"].endswith(".")
        assert move["body"].endswith(".") and not ends_dangling(move["body"])
    routine_moves = [
        move for move in moves if "routine" in move["body"].lower() or "one step" in move["body"].lower()
    ]
    assert len(routine_moves) == 1
    assert "drawer" in routine_moves[0]["body"].lower()
    bodies = " ".join(move["body"].lower() for move in moves)
    assert "anchor" in bodies
    assert "path" in bodies
    assert "curtain" in bodies or "thermal" in bodies or "january" in bodies or "warm" in bodies


def test_nursery_companion_reflow_keeps_photo_pages_and_drops_blank_ones():
    lead, deliverable = _load()
    frames = []
    for index in range(4):
        before = io.BytesIO()
        Image.new("RGB", (240, 480), (140, 40 + index * 20, 40)).save(before, format="JPEG", quality=80)
        after = io.BytesIO()
        Image.new("RGB", (240, 480), (20, 80 + index * 10, 90)).save(after, format="JPEG", quality=80)
        frames.append((before.getvalue(), after.getvalue()))
    pdf = build_pdf(
        lead=lead,
        deliverable=deliverable,
        images={
            "source_pairs": [
                {
                    "label": f"SOURCE_{i + 1:02d}",
                    "after_label": f"AFTER_{i + 1:02d}",
                    "before": frames[i][0],
                    "after": frames[i][1],
                }
                for i in range(4)
            ]
        },
    )
    reader = PdfReader(io.BytesIO(pdf))
    pair_pages = []
    for page in reader.pages:
        text = " ".join((page.extract_text() or "").split())
        images = len(page.images)
        assert len(text) >= 80 or images >= 1
        # A heading with no body and no photo is an orphan page.
        # A text page under 500 characters is the notes-only sheet this reflow removes.
        assert not (images == 0 and len(text) < 500)
        if "same camera" in text.lower():
            pair_pages.append(page)
            assert images >= 2
    assert len(pair_pages) == 4
    joined = " ".join("\n".join((page.extract_text() or "") for page in reader.pages).lower().split())
    assert joined.count("no portable heater") == 1
    assert "do not" not in joined
    assert "source_" not in joined
    assert "after_" not in joined
    names = ("window and crib", "crib wall", "rocker", "dresser and door")
    for index, (page, name) in enumerate(zip(pair_pages, names)):
        assert name in " ".join((page.extract_text() or "").split()).lower()
        # Each page shows its own source and the after edited from it, in that order.
        colors = [img.image.convert("RGB").resize((1, 1)).getpixel((0, 0)) for img in page.images]
        assert sum(_near(c, (140, 40 + index * 20, 40), tol=12) for c in colors) == 1
        assert sum(_near(c, (20, 80 + index * 10, 90), tol=12) for c in colors) == 1


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_room_flow_card_wall_labels_clear_the_legend_and_caption():
    """Live board drew "1.70 m" on top of "02 Change"."""
    from image_board import _draw_plan

    lead, deliverable = _load()
    topdown = board_spec(lead, deliverable, {})["topdown"]
    for box in (
        (36, 1237, 735, 1752),
        (36, 1292, 757, 1752),
        (36, 708, 735, 1752),
        (36, 1380, 1164, 1752),
        (36, 1300, 1164, 1752),
        (36, 1440, 640, 1752),
    ):
        canvas = Image.new("RGBA", (1200, 1800), (243, 238, 230, 255))
        geo = _draw_plan(canvas, box, topdown)
        regions = geo["regions"]
        assert not _overlap(regions["legend"], regions["caption"])
        assert regions["plan"][3] <= regions["legend"][1]
        assert len(geo["label_boxes"]) == 4
        for label in geo["label_boxes"]:
            px0, py0, px1, py1 = regions["plan"]
            assert px0 - 1 <= label[0] and label[2] <= px1 + 1, (box, label)
            assert py0 - 1 <= label[1] and label[3] <= py1 + 1, (box, label)
            assert not _overlap(label, regions["legend"]), (box, label)
            assert not _overlap(label, regions["caption"]), (box, label)


def test_board_fonts_do_not_fall_back_to_the_bitmap_default(monkeypatch):
    """The slim production image has no system fonts; the bundled files must load."""
    import image_board

    bundled_only = {
        kind: tuple(path for path in paths if not path.startswith("/usr/share/fonts"))
        for kind, paths in image_board._FONT_PATHS.items()
    }
    monkeypatch.setattr(image_board, "_FONT_PATHS", bundled_only)
    monkeypatch.setattr(image_board, "_fonts", {})
    for kind in bundled_only:
        face = image_board._font(kind, 15)
        assert isinstance(face, ImageFont.FreeTypeFont), kind
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    face = image_board._font("sans", 15)
    assert probe.textlength("zones approximate", font=face) > probe.textlength("zonesapproximate", font=face) + 2
