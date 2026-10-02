"""Per-source afters: classification, contact sheet, board grid, PDF pairs, final gate."""
import io

from PIL import Image, ImageDraw
from pypdf import PdfReader

from contact_sheet import build_contact_sheet
from image_board import board_spec, build_image_board
from pdf_generator import build_pdf
from source_photos import classify_image_bytes, classify_upload, final_email_block_reason


def _jpeg(color, size=(240, 160)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _screenshot() -> bytes:
    img = Image.new("RGB", (360, 720), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for y in range(40, 640, 64):
        draw.rectangle((20, y, 340, y + 36), fill=(236, 239, 242))
    draw.rectangle((20, 660, 180, 700), fill=(31, 61, 44))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


LEAD = {"name": "Camila", "space_type": "kids_room", "email": "camila@example.com"}
PLAN = {"intro": "A calmer room.", "needs": ["Clear the floor"], "zones": [], "shopping_list": []}


def test_solid_and_photo_like_uploads_are_room_sources():
    assert classify_image_bytes(_jpeg((20, 110, 70)))[0] == "room"
    assert classify_image_bytes(_jpeg((255, 255, 255)))[0] == "room"
    assert classify_image_bytes(b"not-an-image")[0] == "room"


def test_intake_screenshot_is_not_a_required_source():
    shot = _screenshot()
    assert classify_image_bytes(shot) == ("non_room", "ui_screenshot")
    assert classify_image_bytes(_jpeg((20, 110, 70)), filename="Screen Shot 2026-10-02.png")[0] == "non_room"
    assert classify_upload({"kind": "non_room"}, _jpeg((1, 2, 3))) == ("non_room", "override")
    assert classify_upload({"kind": "room"}, shot) == ("room", "override")


def test_final_email_blocks_incomplete_and_missing_after_urls():
    assert final_email_block_reason({"package_status": "incomplete"})
    assert final_email_block_reason(
        {
            "package_status": "review",
            "source_afters": [
                {"label": "SOURCE_02", "status": "failed", "after_url": None},
            ],
        }
    )
    assert final_email_block_reason({"package_status": "review"}) is None
    assert (
        final_email_block_reason(
            {
                "package_status": "review",
                "source_afters": [
                    {"label": "SOURCE_01", "status": "approved", "after_url": "/api/uploads/photo/abc"},
                ],
            }
        )
        is None
    )
    assert final_email_block_reason({}) is None


def test_contact_sheet_pairs_sources_with_afters_and_leaves_a_gap():
    before = _jpeg((180, 40, 40), (320, 200))
    after = _jpeg((20, 90, 70), (320, 200))
    png = build_contact_sheet(
        [
            {"label": "SOURCE_01", "after_label": "AFTER_01", "before": before, "after": after},
            {"label": "SOURCE_02", "after_label": "AFTER_02", "before": before, "after": None},
        ],
        customer_name="Camila",
        incomplete=True,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size[0] >= 1400
    assert img.size[1] > img.size[0] * 0.4
    # Left column of row 1 is the red source. Right column is the green after.
    assert img.getpixel((180, 220))[0] > 140
    assert img.getpixel((1000, 220))[1] > 60
    # Second after is an empty panel, not a copy of the green after.
    gap = img.getpixel((1000, 700))
    assert abs(gap[1] - 20) > 30


def test_board_shows_every_source_after_and_does_not_crop_fill_a_gap():
    a1 = _jpeg((12, 40, 180), (400, 260))
    a2 = _jpeg((180, 40, 40), (400, 260))
    images = {
        "front_view": a1,
        "front_view_kind": "organized",
        "before": _jpeg((10, 10, 10)),
        "after": a1,
        "view_1": _jpeg((1, 1, 1)),
        "source_pairs": [
            {"label": "SOURCE_01", "after_label": "AFTER_01", "before": _jpeg((10, 10, 10)), "after": a1, "status": "approved"},
            {"label": "SOURCE_02", "after_label": "AFTER_02", "before": _jpeg((10, 10, 10)), "after": a2, "status": "approved"},
            {"label": "SOURCE_03", "after_label": "AFTER_03", "before": _jpeg((10, 10, 10)), "after": None, "status": "failed"},
        ],
    }
    spec = board_spec(LEAD, PLAN, images)
    assert spec["hero_mode"] == "source_grid"
    assert spec["claims_organized_photo"] is False
    assert spec["detail_sources"] == ["SOURCE_01", "SOURCE_02", "SOURCE_03"]
    assert "after_crop" not in spec["detail_sources"]
    assert "view_1" not in spec["detail_sources"]
    png = build_image_board(lead=LEAD, deliverable=PLAN, images=images)
    img = Image.open(io.BytesIO(png))
    # Top-left cell is the blue after, not a crop pretending to be another angle.
    assert img.getpixel((200, 280))[2] > 140
    # A missing source stays a light empty panel, not the blue or red after.
    missing = img.getpixel((200, 700))
    assert missing[0] > 180 and missing[1] > 180


def test_pdf_prints_one_before_after_pair_per_source():
    before = _jpeg((140, 110, 70), (320, 200))
    after = _jpeg((20, 110, 70), (320, 200))
    images = {
        "front_view": after,
        "front_view_kind": "organized",
        "before": before,
        "after": after,
        "source_pairs": [
            {"label": "SOURCE_01", "after_label": "AFTER_01", "before": before, "after": after, "status": "approved"},
            {"label": "SOURCE_02", "after_label": "AFTER_02", "before": before, "after": after, "status": "approved"},
        ],
    }
    pdf = build_pdf(lead=LEAD, deliverable=PLAN, images=images)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "SOURCE_01" in text and "AFTER_01" in text
    assert "SOURCE_02" in text and "AFTER_02" in text
    assert "same camera" in text.lower()
    pair_pages = [page for page in reader.pages if "SOURCE_" in (page.extract_text() or "")]
    assert len(pair_pages) == 2
    assert all(len(page.images) >= 2 for page in pair_pages)
