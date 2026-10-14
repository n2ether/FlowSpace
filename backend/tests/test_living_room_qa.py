"""QA fixes for the living-room package: invented sizes, mid-sentence cuts, and the window-wall overlap."""
from PIL import Image, ImageDraw

from blueprint_consistency import prepare_deliverable
from copy_shape import complete_clip, ends_dangling
from image_board import _Pen, _change_rows, board_spec
from package_facts import apply_measurement_rule, package_facts
from room_flow import _s, build_zone_map

LEAD = {
    "id": "4a2f3284-6628-4bda-9952-6f5de13ec936",
    "name": "Camila Sales",
    "email": "camila.sales@gmail.com",
    "space_type": "living_room",
}
NURSERY_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"
ENTRY = (
    "The entry path keeps clear circulation with a small landing for shoes, bags, and keys."
)
CHANGE = "Add a soft textile layer for warmth and tie the seating to the wood already in the room."


def _deliverable():
    return {
        "lead_id": LEAD["id"],
        "wall_color_name": "keep existing",
        "package_status": "review",
        "package_version": 2,
        "zones": [
            {"title": "Entry Path", "desc": ENTRY},
            {"title": "Living", "desc": "The seating stays easy to walk around."},
            {"title": "Dining", "desc": "The table stays clear between meals."},
        ],
        "strategy": [
            "Give bags one home by the door.",
            CHANGE,
        ],
        "shopping_list": [
            {"name": "botanical print set 16x20 inches each", "qty": 1, "price": 24, "priority": "decorative"},
            {"name": "tray 14x10 inches", "qty": 1, "price": 12},
            {"name": "pillow covers 18x18 inches", "qty": 2, "price": 18, "priority": "decorative"},
            {"name": "Woven basket 14 x 10 in", "qty": 2, "price": 18},
        ],
    }


def _drawn(monkeypatch, draw_fn):
    calls = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        calls.append((str(text), tuple(xy)))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    draw_fn()
    return calls


def test_prints_trays_and_pillows_lose_invented_sizes():
    prepared = prepare_deliverable(LEAD, _deliverable())
    names = [item["name"] for item in prepared["shopping_list"]]
    assert names == ["botanical print set", "tray", "pillow covers", "Woven basket"]
    assert all(item.get("measure_first") for item in prepared["shopping_list"])
    facts = package_facts(LEAD, _deliverable(), prepared=prepared)
    assert facts["measure_items"]
    assert "16x20" not in " ".join(names) and "14x10" not in " ".join(names) and "18x18" not in " ".join(names)
    prose = prepare_deliverable(
        LEAD,
        {
            **_deliverable(),
            "strategy": ["Hang the botanical print set 16x20 inches above the sofa."],
        },
    )
    assert "16x20" not in prose["strategy"][0]
    assert "measure before buying" in prose["strategy"][0].lower()
    nursery = {"id": NURSERY_ID, "space_type": "kids_room"}
    basket = {"shopping_list": [{"name": "Woven basket 14 x 10 in", "qty": 1, "price": 18}]}
    assert apply_measurement_rule(nursery, basket) == []
    assert basket["shopping_list"][0]["name"] == "Woven basket 14 x 10 in"


def test_copy_is_not_cut_mid_sentence(monkeypatch):
    clipped = complete_clip(CHANGE, 8)
    assert clipped.endswith(".")
    assert not clipped.endswith("tie.")
    assert not ends_dangling(clipped)
    assert "tie the seating" in clipped

    spec = board_spec(LEAD, _deliverable(), {})
    body = spec["moves"][-1]["body"]
    assert body == CHANGE if CHANGE.endswith(".") else CHANGE + "."
    assert not body.endswith("tie.")
    pen = _Pen(Image.new("RGB", (3200, 4000), "white"), 2)
    _title, lines, _size = _change_rows(pen, spec["moves"], 720)[-1]
    shown = " ".join(lines)
    assert shown.endswith(".")
    assert not shown.endswith("tie.")
    assert "tie the seating" in shown

    calls = _drawn(monkeypatch, lambda: build_zone_map(lead=LEAD, deliverable=_deliverable(), images={}))
    words = [text for text, _xy in calls if text and not text.isupper()]
    joined = " ".join(words)
    assert "clear circulation with a small" in joined
    assert "landing" in joined
    assert not joined.rstrip(".").endswith("with a small")


def test_what_stays_sits_below_the_window_wall_label(monkeypatch):
    calls = _drawn(monkeypatch, lambda: build_zone_map(lead=LEAD, deliverable=_deliverable(), images={}))
    stays = [xy[1] for text, xy in calls if text.startswith("Keep the original wall color")]
    assert stays, calls
    # WINDOW WALL is tracked one letter at a time just above the outline.
    wall_y = [xy[1] for text, xy in calls if text in set("WINDOWALL") and xy[1] < _s(360)]
    assert wall_y, "WINDOW WALL label was not drawn"
    assert min(stays) > max(wall_y) + 20
    assert min(stays) > _s(620)
