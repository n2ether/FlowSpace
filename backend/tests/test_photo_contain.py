"""Room photos keep their field of view when painted into a Blueprint slot."""
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.platypus import Flowable, Table

from image_board import board_layout, board_spec, build_image_board
from pdf_generator import ClippedPhoto, _compare_panel
from photo_contain import contain_pixels, contain_rect

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json"


def _load():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]

RED = (220, 20, 20)
BLUE = (20, 20, 220)
GREEN = (20, 180, 40)
GOLD = (220, 200, 20)
PAPER = (246, 247, 244)


def _near(pixel, expected, tol=18) -> bool:
    return all(abs(int(pixel[i]) - expected[i]) <= tol for i in range(3))


def _quadrant(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), RED)
    draw = ImageDraw.Draw(img)
    mid_x, mid_y = width // 2, height // 2
    draw.rectangle((0, 0, mid_x - 1, mid_y - 1), fill=RED)
    draw.rectangle((mid_x, 0, width - 1, mid_y - 1), fill=BLUE)
    draw.rectangle((0, mid_y, mid_x - 1, height - 1), fill=GREEN)
    draw.rectangle((mid_x, mid_y, width - 1, height - 1), fill=GOLD)
    return img


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _walk(flow):
    if isinstance(flow, ClippedPhoto):
        yield flow
    cells = getattr(flow, "_cellvalues", None)
    if not cells:
        return
    for row in cells:
        for cell in row:
            items = cell if isinstance(cell, (list, tuple)) else (cell,)
            for item in items:
                if isinstance(item, Flowable):
                    yield from _walk(item)


def test_contain_rect_fits_a_portrait_frame_inside_a_wide_slot():
    ox, oy, dw, dh = contain_rect(300, 600, 800, 240)
    assert abs((dw / dh) - 0.5) < 0.01
    assert dh <= 240
    assert dw <= 800
    assert abs(dh - 240) < 0.2
    assert abs(dw - 120) < 0.6
    assert ox > 100
    assert oy < 1
    # Cover would scale up until the slot is filled and then crop the height.
    cover_scale = max(800 / 300, 240 / 600)
    contain_scale = min(800 / 300, 240 / 600)
    assert cover_scale > contain_scale


def test_one_portrait_after_paints_into_a_wide_slot_without_crop():
    """One view, first. A wide 800×240 cell must not zoom or cut the portrait."""
    src = _quadrant(300, 600)
    slot = Image.new("RGB", (800, 240), (10, 10, 10))
    ox, oy, dw, dh = contain_pixels(src.width, src.height, slot.width, slot.height)
    fitted = src.resize((dw, dh), Image.Resampling.LANCZOS)
    slot.paste(fitted, (ox, oy))

    assert abs((dw / dh) - (src.width / src.height)) < 0.02
    assert slot.getpixel((2, slot.height // 2)) == (10, 10, 10)
    assert slot.getpixel((slot.width - 3, slot.height // 2)) == (10, 10, 10)
    assert _near(slot.getpixel((ox + 2, oy + 2)), RED)
    assert _near(slot.getpixel((ox + dw - 3, oy + 2)), BLUE)
    assert _near(slot.getpixel((ox + 2, oy + dh - 3)), GREEN)
    assert _near(slot.getpixel((ox + dw - 3, oy + dh - 3)), GOLD)


def test_board_hero_contains_one_portrait_after():
    lead, deliverable = _load()
    portrait = _png(_quadrant(240, 480))
    images = {
        "front_view": portrait,
        "front_view_kind": "organized",
        "before": portrait,
        "after": portrait,
    }
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    board = Image.open(io.BytesIO(png))
    hero = board_layout(board_spec(lead, deliverable, images))["hero"]
    x0, y0, x1, y1 = hero
    # Editorial hero is a full-width cover slot, not a letterboxed portrait.
    assert (x1 - x0) == 1600 - 2 * 72
    assert (x1 - x0) / (y1 - y0) > 1.5
    assert x0 == 72
    mid = board.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
    assert mid != PAPER
    # The margin outside the content column is the board paper.
    assert _near(board.getpixel((24, (y0 + y1) // 2)), PAPER, tol=6)


def test_board_contains_each_of_four_portrait_views():
    lead, deliverable = _load()
    frames = [
        _png(_quadrant(240, 480)),
        _png(_quadrant(240, 480)),
        _png(_quadrant(180, 420)),
        _png(_quadrant(200, 460)),
    ]
    images = {
        "front_view": frames[0],
        "front_view_kind": "organized",
        "before": frames[0],
        "after": frames[0],
        "source_pairs": [
            {"label": f"SOURCE_{i + 1:02d}", "after_label": f"AFTER_{i + 1:02d}", "before": frames[i], "after": frames[i], "status": "approved"}
            for i in range(4)
        ],
    }
    png = build_image_board(lead=lead, deliverable=deliverable, images=images)
    board = Image.open(io.BytesIO(png))
    layout = board_layout(board_spec(lead, deliverable, images))
    boxes = [layout["hero"], *layout["sources"]]
    assert len(boxes) == 4
    width, height = board.size
    for box in boxes:
        x0, y0, x1, y1 = box
        assert 0 <= x0 < x1 <= width
        assert 0 <= y0 < y1 <= height
        pixel = board.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
        assert pixel != PAPER
    def _overlaps(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    assert all(not _overlaps(layout["hero"], box) for box in layout["sources"])
    assert layout["plan"] is None
    assert layout["sources"][-1][3] <= layout["story"][1]
    assert layout["palette"][3] <= height - 8
    assert layout["roadmap"][-1][3] <= height - 8
    hero_h = layout["hero"][3] - layout["hero"][1]
    assert hero_h >= 380


def test_pdf_compare_panel_contains_a_portrait_room_photo():
    src = _quadrant(200, 400)
    buf = io.BytesIO()
    src.save(buf, format="JPEG", quality=90)
    panel = _compare_panel(buf.getvalue(), 300, 220, "AFTER_01 — ORGANIZED VIEW", "Missing", "Empty")
    assert isinstance(panel, Table)
    photos = list(_walk(panel))
    assert len(photos) == 1
    photo = photos[0]
    assert photo.fill is False
    dw, dh = photo.placed_size()
    assert abs((dw / dh) - 0.5) < 0.02
    assert dw <= photo.width + 0.2
    assert dh <= photo.height + 0.2
    assert dw < photo.width - 20
