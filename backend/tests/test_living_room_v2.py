"""Living room Versão 2: the lead's Room Flow record, the board caption, and measure-first rows."""
from design_plan_standards import BOARD_SHOPPING_CAPTION, SHOPPING_DISCLAIMER
from image_board import board_spec
from package_facts import apply_measurement_rule
from room_flow import load_record, record_view_names, resolve_room_flow, validate_room_flow

LEAD = {"id": "4a2f3284-6628-4bda-9952-6f5de13ec936", "name": "Camila Sales", "space_type": "living_room"}
NURSERY = {"id": "9dbedfba-81fc-45e0-b99d-36e0a1de01bb", "name": "Camila Sales", "space_type": "nursery"}


def test_record_draws_the_real_fixed_points():
    flow = load_record(LEAD["id"])
    assert flow and validate_room_flow(flow) == []
    assert flow["outline_source"] == "approximate"  # nothing measured yet
    assert flow["window"]["wall"] == flow["door"]["wall"] == 0  # front door shares the window wall
    assert [z["title"] for z in flow["zones"]] == ["Living", "Dining", "Entry Path", "Play"]
    labels = {item["label"] for item in flow["furniture"]}
    assert {"TV CONSOLE", "SECTIONAL", "DINING TABLE", "PLAYPEN"} <= labels
    assert record_view_names(LEAD) == ["Whole area", "TV and dining", "Couch and front door"]
    assert resolve_room_flow(LEAD, {})["zones"][3]["title"] == "Play"


def test_board_caption_points_to_the_guide_except_nursery():
    assert board_spec(LEAD, {"lead_id": LEAD["id"]}, {})["shop_note"] == BOARD_SHOPPING_CAPTION
    assert BOARD_SHOPPING_CAPTION.startswith("Representative examples for reference. Full shopping detail")
    assert board_spec(NURSERY, {"lead_id": NURSERY["id"]}, {})["shop_note"] == SHOPPING_DISCLAIMER


def test_unmeasured_baskets_and_frames_stay_measure_first_without_a_size():
    doc = {"shopping_list": [
        {"name": "Natural jute storage basket, medium, handles", "qty": 2, "price": 18},
        {"name": "Three-piece framed botanical print set", "qty": 1, "price": 85},
        {"name": "Small ceramic catch-all dish", "qty": 1, "price": 12},
    ]}
    apply_measurement_rule({"id": "x", "space_type": "living_room"}, doc)
    flags = [bool(item.get("measure_first")) for item in doc["shopping_list"]]
    assert flags == [True, True, False]
