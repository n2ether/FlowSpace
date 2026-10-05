"""Conceptual Zone Map / Flow Plan — the standard room-flow layout."""
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw

from room_flow import (
    build_zone_map,
    default_room_flow,
    edge_length,
    outline_phrases,
    resolve_room_flow,
    validate_room_flow,
    zone_map_spec,
    zone_map_text,
)

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "fixtures" / "nursery_nico.json"
GARAGE = BACKEND / "fixtures" / "bakeoff" / "garage_org_space.json"
LEAD_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"
FOUR_VIEWS = {"source_pairs": [{"label": f"SOURCE_0{i}"} for i in range(1, 5)]}


def _load(path=FIXTURE):
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc["lead"], doc["deliverable"]


def _drawn(monkeypatch, **kwargs):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kw):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kw)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    png = build_zone_map(**kwargs)
    # Letter-spaced lines are painted one glyph at a time.
    return png, "".join(drawn), "\n".join(drawn)


def test_nicholas_record_is_the_measured_outline_from_camilas_map():
    lead, deliverable = _load()
    flow = resolve_room_flow(lead, deliverable)
    assert flow["outline_source"] == "measured"
    assert validate_room_flow(flow) == []
    outline = flow["outline"]
    lengths = [round(edge_length(outline, i), 2) for i in range(len(outline))]
    # Window wall (top), right, bottom, the door diagonal, left.
    assert lengths[0] == 2.26
    assert lengths[1] == 2.76
    assert lengths[2] == 1.70
    assert lengths[4] == 2.05
    assert flow["walls"][3] == {"door": True}
    # The door corner is the lower-left one.
    door_a, door_b = outline[3], outline[4]
    assert max(door_a[0], door_b[0]) < 1.0 and min(door_a[1], door_b[1]) > 2.0
    assert flow["window"]["wall"] == 0
    zones = [(z["number"], z["title"]) for z in flow["zones"]]
    assert zones == [("01", "Sleep"), ("02", "Change"), ("03", "Comfort"), ("04", "Play + Storage")]
    kinds = {item["kind"]: item for item in flow["furniture"]}
    assert set(kinds) == {"dresser", "crib", "rocker", "rug", "basket"}
    assert kinds["dresser"]["drawers"] == 6
    assert kinds["dresser"]["zone"] == "change"
    # Dresser on the left wall, crib and rocker on the right wall, crib nearer the window.
    assert kinds["dresser"]["rect"][0] < 0.3
    assert kinds["crib"]["rect"][2] > 2.0 and kinds["rocker"]["rect"][2] > 2.0
    assert kinds["crib"]["rect"][1] < kinds["rocker"]["rect"][1]


def test_header_and_footer_both_say_measured_outline(monkeypatch):
    lead, deliverable = _load()
    spec = zone_map_spec(lead, deliverable, FOUR_VIEWS)
    assert spec["badge_status"] == "DRAFT CONCEPT"
    assert spec["badge_outline"] == "Measured room outline"
    assert "Measured room outline" in spec["source_rule"]
    assert "furniture and zones approximate" in spec["source_rule"]
    assert "not a measured plan" not in zone_map_text(spec).lower()
    _png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable, images=FOUR_VIEWS)
    assert "not a measured plan" not in glyphs.lower()
    assert "Measured room outline" in glyphs
    assert "Based on the four source views" in glyphs
    assert "Measured room outline; furniture and zones approximate" in glyphs


def test_map_carries_camilas_facts(monkeypatch):
    lead, deliverable = _load()
    _png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable, images=FOUR_VIEWS)
    for text in (
        "FlowSpace",
        "CLEAR SPACE. CREATE FLOW. LIVE BETTER.",
        "NICHOLAS'S NURSERY",
        "A CALMER FLOW FOR SLEEP, CHANGE, COMFORT & PLAY",
        "DRAFT CONCEPT",
        "WINDOW \u2022 2.26 m WALL",
        "2.05 m",
        "2.76 m",
        "1.70 m",
        "01 ROOM FLOW + FUNCTIONAL ZONES",
        "Measured outline supplied by Camila; furniture and zones remain approximate.",
        "02 THE ZONES",
        "Each zone has one job.",
        "SLEEP",
        "CHANGE",
        "COMFORT",
        "PLAY + STORAGE",
        "DRESSER",
        "CRIB",
        "ROCKER",
        "RUG + BASKET",
        "CLEAR PATH",
        "Less visual noise.",
        "Fewer decisions.",
        "Easier resets.",
        "03 WHY THIS HELPS",
        "DRAFT CONCEPT FOR REVIEW",
    ):
        assert text in glyphs, text
    # Camila's sheet marks the door with the diagonal opening only, no label.
    assert "DOOR" not in glyphs
    spec = zone_map_spec(lead, deliverable, FOUR_VIEWS)
    assert spec["flow_note"] == "A clear route supports calmer bedtime transitions for both parent and child."
    assert spec["why_headline"] == "The room becomes easier to read, easier to reset, and easier to live in."
    jobs = {z["title"]: z["job"] for z in spec["zones"]}
    assert jobs["Sleep"] == "Crib as the quiet anchor of the room."
    assert jobs["Change"] == "Everyday care kept within easy reach."
    assert jobs["Play + Storage"] == "Open floor space and one easy-reset basket."


def test_customer_sheet_has_no_codes_lead_id_or_ready_claim(monkeypatch):
    lead, deliverable = _load()
    png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable, images=FOUR_VIEWS)
    assert "SOURCE_" not in glyphs and "AFTER_" not in glyphs
    assert LEAD_ID not in glyphs
    assert not re.search(r"\bQA\b", glyphs)
    assert not re.search(r"\bready\b", glyphs, re.I)
    assert LEAD_ID.encode() not in png
    img = Image.open(io.BytesIO(png))
    assert img.size == (1434, 2048)


def test_review_banner_names_the_lead_and_status(monkeypatch):
    lead, deliverable = _load()
    png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable, review=True)
    assert "DRAFT. Review version. Not yet approved. Customer release held." in glyphs
    assert LEAD_ID in glyphs
    assert Image.open(io.BytesIO(png)).size[1] > 2048


def test_record_on_the_deliverable_wins_and_drives_the_wording():
    lead, deliverable = _load()
    flow = resolve_room_flow(lead, deliverable)
    flow["outline_source"] = "approximate"
    for wall in flow["walls"]:
        wall.pop("length_m", None)
        wall.pop("label", None)
    spec = zone_map_spec(lead, {**deliverable, "room_flow": flow})
    assert spec["badge_outline"] == "Approximate room outline"
    assert "Approximate room outline" in spec["source_rule"]
    assert "Measured" not in zone_map_text(spec)


def test_validation_catches_a_label_that_disagrees_with_the_outline():
    lead, deliverable = _load()
    flow = resolve_room_flow(lead, deliverable)
    flow["walls"][1]["length_m"] = 3.10
    assert any("wall 1" in issue for issue in validate_room_flow(flow))
    flow = resolve_room_flow(lead, deliverable)
    flow["furniture"][0]["rect"] = [-0.5, 0.3, 0.2, 1.0]
    assert any("outside" in issue for issue in validate_room_flow(flow))


def test_standard_default_for_other_projects_is_labelled_approximate(monkeypatch):
    lead, deliverable = _load(GARAGE)
    flow = default_room_flow(lead, deliverable)
    assert flow["outline_source"] == "approximate"
    assert validate_room_flow(flow) == []
    assert "Circulation" not in [z["title"] for z in flow["zones"]]
    assert 1 <= len(flow["zones"]) <= 4
    assert outline_phrases(flow)["badge"] == "Approximate room outline"
    _png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable)
    assert "Approximate room outline" in glyphs
    assert "Measured" not in glyphs
    assert " m WALL" not in glyphs
    assert "CLEAR PATH" in glyphs


def test_final_sheet_drops_draft_status(monkeypatch):
    lead, deliverable = _load()
    _png, glyphs, _lines = _drawn(monkeypatch, lead=lead, deliverable=deliverable, final=True)
    assert "DRAFT" not in glyphs
    assert "Measured room outline" in glyphs
