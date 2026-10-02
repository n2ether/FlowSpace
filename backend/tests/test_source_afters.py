"""Per-source afters: classification, contact sheet, board grid, PDF pairs, final gate."""
import io

from PIL import Image, ImageDraw
from pypdf import PdfReader

from contact_sheet import build_contact_sheet
from image_board import board_layout, board_spec, build_image_board
from pdf_generator import build_pdf
from source_photos import (
    classify_image_bytes,
    classify_upload,
    draft_send_block_reason,
    final_email_block_reason,
    mapping_is_own_source,
)


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


def _own(label="SOURCE_01", photo_id="abc"):
    return {
        "label": label,
        "source_photo_id": photo_id,
        "derived_from_photo_id": photo_id,
        "status": "approved",
        "after_url": f"/api/uploads/photo/{photo_id}-after",
        "edit_kind": "own_source",
    }


def test_final_email_blocks_incomplete_and_missing_after_urls():
    assert final_email_block_reason({"package_status": "incomplete"})
    assert final_email_block_reason(
        {
            "package_status": "review",
            "source_afters": [
                {"label": "SOURCE_02", "status": "failed", "after_url": None, "edit_kind": "missing"},
            ],
        }
    )
    assert final_email_block_reason({"package_status": "review"}) is None
    assert final_email_block_reason({"package_status": "review", "source_afters": [_own()]}) is None
    assert final_email_block_reason({}) is None


def test_final_email_requires_explicit_own_source_mapping():
    approved_url = {
        "label": "SOURCE_01",
        "source_photo_id": "abc",
        "status": "approved",
        "after_url": "/api/uploads/photo/abc",
    }
    assert final_email_block_reason({"package_status": "review", "source_afters": [approved_url]})
    assert mapping_is_own_source(approved_url) is False

    crop = {**_own(), "edit_kind": "crop"}
    invented = {**_own(), "edit_kind": "invented_angle"}
    other = {**_own(), "derived_from_photo_id": "different-photo"}
    for row in (crop, invented, other):
        reason = final_email_block_reason({"package_status": "review", "source_afters": [row]})
        assert reason
        assert "own-source" in reason.lower()
        assert mapping_is_own_source(row) is False

    missing_required = final_email_block_reason(
        {
            "package_status": "review",
            "required_source_ids": ["abc", "def"],
            "source_afters": [_own(photo_id="abc")],
        }
    )
    assert missing_required
    assert "def" in missing_required

    legacy = {
        "package_status": "review",
        "source_afters": [
            {
                "label": "SOURCE_01",
                "source_photo_id": "abc",
                "status": "approved",
                "after_url": "/api/uploads/photo/abc",
            }
        ],
    }
    assert final_email_block_reason(legacy)
    assert draft_send_block_reason(legacy) is None
    assert draft_send_block_reason({"package_status": "incomplete", "source_afters": [_own()]})
    assert draft_send_block_reason({"package_status": "review", "source_afters": [{**_own(), "edit_kind": "crop"}]})
    assert draft_send_block_reason({"package_status": "review", "source_afters": [_own()]}) is None


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
    assert spec["hero_mode"] == "hero_plus_afters"
    assert spec["claims_organized_photo"] is False
    assert spec["detail_sources"] == ["SOURCE_01", "SOURCE_02", "SOURCE_03"]
    assert "after_crop" not in spec["detail_sources"]
    assert "view_1" not in spec["detail_sources"]
    png = build_image_board(lead=LEAD, deliverable=PLAN, images=images)
    img = Image.open(io.BytesIO(png))
    layout = board_layout(board_spec(LEAD, PLAN, images))

    def mid(box):
        return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)

    # Hero is the first full-room after (blue), not a crop of another angle.
    for point in (mid(layout["hero"]), (layout["hero"][0] + 20, layout["hero"][1] + 20)):
        assert img.getpixel(point)[2] > 140
    # Remaining full-room afters: red, then an empty gap. Not a crop fill.
    assert len(layout["sources"]) == 2
    supporting = img.getpixel(mid(layout["sources"][0]))
    assert supporting[0] > 140 and supporting[1] < 80
    missing = img.getpixel(mid(layout["sources"][1]))
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
