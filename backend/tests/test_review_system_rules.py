"""System rules from the Living Room Version 2 review, applied to every project.

Fixed furniture keeps its structure in every view; baskets stay off seats, beds,
and a shoe bench's shoe area; brief notes (open budget, requested decor, "keep
existing X") reach generation and documents; the Room Flow map connects living
and dining, shows seating and a two-configuration table, says it is approximate,
and keeps labels off zone borders; documents and views share one item list; an
admin photo override allows up to six photos; and a package carries clearly
named files with exactly one Companion Guide.
"""
import asyncio
import base64
import io
import os
from typing import Any, Dict

import pytest
from PIL import Image

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "flowspace_review_rules_test")

LIVING_ID = "4a2f3284-6628-4bda-9952-6f5de13ec936"
NURSERY_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"

BRIEF = (
    "Open budget. Add larger art on the wall linking dining and kitchen. "
    "Add a rug, cozy touches, and a set table. Keep the existing art above the sofa."
)
FIXED = [
    {"name": "TV console", "details": "low console with two glass doors, closed cabinets, no open cubbies"},
    {"name": "Shoe bench", "details": "entry bench with an open shoe shelf under the seat"},
]


def _living(**extra):
    lead = {
        "id": "test-living-0001",
        "name": "Camila Sales",
        "space_type": "living_room",
        "must_stay": "Keep all current furniture",
        "brief": {"notes": BRIEF},
    }
    lead.update(extra)
    return lead


def _png(size=(120, 90), color=(31, 61, 44)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


# ──────────────────────────── 1. Fixed furniture, every view ─────────────────────────────


def test_fixed_items_are_described_once_and_locked_in_every_edit_prompt():
    from ai_image_generator import _build_edit_prompt, _supporting_prompt
    from package_items import CROSS_VIEW_RAILS, fixed_items

    lead, plan = _living(), {"fixed_items": FIXED}
    items = fixed_items(lead, plan)
    assert [i["name"] for i in items][:2] == ["TV console", "Shoe bench"]
    # "keep the existing art above the sofa" joins the shared list.
    assert any(i["name"] == "art above the sofa" for i in items)
    for prompt in (_build_edit_prompt(lead, plan), _supporting_prompt(lead, plan, "Focus on the TV wall.")):
        assert "FIXED FURNITURE LOCK" in prompt
        assert "TV console — low console with two glass doors, closed cabinets, no open cubbies" in prompt
        assert "Never turn doors into open cubbies, baskets, or bins" in prompt
        assert CROSS_VIEW_RAILS in prompt
    # The same description goes to every photo of the room.
    assert _build_edit_prompt(lead, plan) == _build_edit_prompt(lead, plan)


def test_fixed_lock_applies_to_rooms_without_a_drafted_list():
    from ai_image_generator import _build_edit_prompt

    prompt = _build_edit_prompt({"space_type": "garage"}, {})
    assert "glass doors stay glass doors" in prompt
    assert "CROSS-VIEW CONSISTENCY" in prompt


def test_qa_checks_fixed_structure_baskets_and_planned_items():
    from render_qa import _from_payload, qa_prompt

    prompt = qa_prompt(fixed_items=["TV console (two glass doors)"], additions=["Area rug"])
    assert "fixed_items_changed" in prompt and "TV console (two glass doors)" in prompt
    assert "baskets_misplaced" in prompt and "visible_additions" in prompt and "Area rug" in prompt
    changed = _from_payload({"ok": True, "fixed_items_changed": True, "visible_additions": ["Area rug"]})
    assert changed.failed and changed.fixed_items_changed
    assert changed.as_dict()["visible_additions"] == ["Area rug"]
    basket = _from_payload({"ok": True, "baskets_misplaced": True})
    assert basket.failed
    plain = _from_payload({"ok": True})
    assert not plain.failed and "visible_additions" not in plain.as_dict()


def test_later_views_are_edited_against_the_first_approved_after(monkeypatch):
    from render_qa import RenderQAResult
    from tests.test_automation import _FakeFS, _jpeg, _lead, _run

    photos = {c * 24: _jpeg((20 * i, 90, 60)) for i, c in enumerate("abc", start=1)}
    lead = _lead()
    lead["photos"] = [f"/api/uploads/photo/{key}" for key in photos]
    lead["brief"] = {"notes": BRIEF}
    calls = []
    afters = [_jpeg((200, 10 * i, 10)) for i in range(1, 4)]

    def generate(**kwargs):
        calls.append(kwargs)
        return afters[len(calls) - 1], "image/jpeg"

    reviews = []

    def review(**kwargs):
        reviews.append(kwargs)
        return RenderQAResult(ok=True, visible_additions=["Area rug"], unlisted_additions=[])

    monkeypatch.setattr("automation.review_organized_render", review)
    sent, captured, db, _fs = _run(monkeypatch, generate=generate, fs=_FakeFS(store=dict(photos)), lead=lead)
    assert sent is True
    assert "consistency_reference" not in calls[0]
    assert calls[1]["consistency_reference"] == afters[0]
    assert calls[2]["consistency_reference"] == afters[0]
    assert "SECOND IMAGE = REFERENCE ONLY" in calls[1]["extra_constraint"]
    for kwargs in reviews:
        assert "fixed_items" in kwargs and "additions" in kwargs
        assert "Larger wall art" in kwargs["additions"]
    doc = db.deliverables.docs["lead-img-1"]
    assert doc["consistency"]["issues"]
    assert all(row["qa"]["visible_additions"] == ["Area rug"] for row in doc["source_afters"])
    assert [p["visible_additions"] for p in captured["images"]["source_pairs"]] == [["Area rug"]] * 3


def test_drafter_sees_every_room_photo_and_returns_the_shared_lists():
    from ai_drafter import SYSTEM_PROMPT, _coerce, _user_content

    assert '"fixed_items"' in SYSTEM_PROMPT and '"additions"' in SYSTEM_PROMPT
    blocks = _user_content("answers", ["a", "b", "c"])
    assert [b["type"] for b in blocks].count("image") == 3
    assert blocks[-1] == {"type": "text", "text": "answers"}
    plan = _coerce({"intro": "x", "fixed_items": FIXED, "additions": [{"name": "Round rug", "placement": "under the coffee table"}]})
    assert plan["fixed_items"][0] == {"name": "TV console", "details": FIXED[0]["details"]}
    assert plan["additions"] == [{"name": "Round rug", "placement": "under the coffee table"}]


# ──────────────────────────── 2. Baskets ─────────────────────────────


@pytest.mark.parametrize("space", ["living_room", "kids_room", "garage", "mudroom"])
def test_basket_rule_is_in_every_room_prompt(space):
    from ai_image_generator import _build_edit_prompt, _build_text_to_image_prompt
    from package_items import BASKET_PLACEMENT_RAILS

    assert BASKET_PLACEMENT_RAILS in _build_edit_prompt({"space_type": space}, {})
    assert BASKET_PLACEMENT_RAILS in _build_text_to_image_prompt({"space_type": space}, {})


def test_basket_rule_is_in_the_drafter_rules():
    from ai_drafter import SYSTEM_PROMPT

    assert "Never put a basket, bin, or box on a seating surface" in SYSTEM_PROMPT
    assert "shoe bench" in SYSTEM_PROMPT


def test_plan_text_with_baskets_on_seats_beds_or_shoe_bench_is_flagged():
    from package_items import basket_placement_issues

    plan = {
        "strategy": [
            "Add two baskets under the shoe bench for shoes.",
            "Put a basket on the bed for toys.",
            "Set a lidded basket on the sofa for throws.",
            "Place a basket beside the sofa for throws.",
            "Keep a basket on the console shelf.",
        ]
    }
    flagged = basket_placement_issues({}, plan)
    assert flagged == [
        "Add two baskets under the shoe bench for shoes.",
        "Put a basket on the bed for toys.",
        "Set a lidded basket on the sofa for throws.",
    ]


def test_customer_request_lifts_the_basket_rule():
    from package_items import basket_placement_issues, basket_rails

    lead = {"goals": "Please put a basket under the shoe bench for slippers."}
    assert "Exception the customer asked for" in basket_rails(lead)
    assert basket_placement_issues(lead, {"strategy": ["Add a basket under the shoe bench."]}) == []


def test_basket_on_a_bench_blocks_the_consistency_check():
    from package_items import consistency_report

    report = consistency_report({"id": "x", "space_type": "mudroom"}, {"strategy": ["Add baskets under the shoe bench."]})
    assert any(i["code"] == "basket_on_seat_or_bed" and i["severity"] == "block" for i in report["issues"])


# Preview garage draft of 23 Oct 2026: the customer chose "No drilling".
_GARAGE_DRAFT = {
    "strategy": [
        "Mount bike hooks on the right wall so bikes stand upright and clear the car path.",
        "Consolidate paint cans on one shelf with labels so every color is visible.",
    ],
    "zones": [
        {"title": "Bike & Tool Storage", "desc": "Wall-mounted bike hooks and the existing tool rack keep bikes upright."},
        {"title": "Parking Zone", "desc": "Central open floor for the car to pull in and park without obstacles."},
    ],
    "shopping_list": [
        {"name": "Heavy-duty wall-mounted bike hooks (set of 3)", "qty": 1, "price": 35},
        {"name": "Over-door hook rack (6 hooks)", "qty": 1, "price": 15},
    ],
}


def _garage(limits):
    return {"id": "g", "space_type": "garage", "intake": {"limits": limits}}


def test_no_drilling_blocks_wall_mounting_in_plan_and_shopping():
    from package_items import consistency_report, no_drilling_conflicts

    hits = no_drilling_conflicts(_garage(["no_drilling"]), _GARAGE_DRAFT)
    assert any(h.startswith("Mount bike hooks on the right wall") for h in hits)
    assert any("Heavy-duty wall-mounted bike hooks" in h for h in hits)
    assert not any("Over-door" in h or "Parking" in h for h in hits)

    report = consistency_report(_garage(["no_drilling"]), _GARAGE_DRAFT)
    blocks = [i for i in report["issues"] if i["code"] == "limit_no_drilling_contradicted"]
    assert blocks and all(i["severity"] == "block" for i in blocks)
    assert report["ok"] is False


def test_no_drilling_rule_only_applies_when_chosen_and_respects_negation():
    from package_items import no_drilling_conflicts

    assert no_drilling_conflicts(_garage(["none"]), _GARAGE_DRAFT) == []
    assert no_drilling_conflicts({"space_type": "garage"}, _GARAGE_DRAFT) == []
    renter = {"strategy": ["Use over-door hooks so nothing needs to be drilled into the wall.", "Add a freestanding bike stand."]}
    assert no_drilling_conflicts(_garage(["no_drilling"]), renter) == []
    for sentence in ("Drill pilot holes for the shelf.", "Screw the rail into the studs.", "Anchor the cabinet to the wall."):
        assert no_drilling_conflicts(_garage(["no_drilling"]), {"strategy": [sentence]}) == [sentence]


def test_no_drilling_ignores_an_existing_wall_mounted_fixture():
    """Preview mudroom of 24 Oct 2026: the room already has a wall-mounted coat rack."""
    from package_items import no_drilling_conflicts

    mudroom = {
        "zones": [{"title": "Coat & Bag Zone", "desc": "Wall-mounted coat rack holds jackets, backpacks, and scarves within easy reach."}],
        "strategy": ["Use removable adhesive hooks for extra bags or hats without drilling into walls."],
        "shopping_list": [{"name": "Set of removable adhesive hooks for bags or hats", "qty": 1, "price": 12}],
    }
    assert no_drilling_conflicts(_garage(["no_drilling"]), mudroom) == []
    for sentence in ("Keep the existing wall-mounted shelf above the bench.", "The current wall-mounted rack stays."):
        assert no_drilling_conflicts(_garage(["no_drilling"]), {"strategy": [sentence]}) == []
    added = "Add a wall-mounted shelf above the bench."
    assert no_drilling_conflicts(_garage(["no_drilling"]), {"strategy": [added]}) == [added]


def test_no_drilling_swaps_the_generic_wall_anchor_safety_line():
    from blueprint_consistency import NO_DRILL_STABILITY_LINE, safety_essentials

    drill_ok = safety_essentials(_garage(["none"]), {})
    no_drill = safety_essentials(_garage(["no_drilling"]), {})
    assert any("Anchor tall or heavy furniture to the wall" in line for line in drill_ok)
    assert NO_DRILL_STABILITY_LINE in no_drill
    assert not any("to the wall" in line.lower() for line in no_drill)


# ──────────────────────────── 3. Brief notes ─────────────────────────────


def test_brief_requests_open_budget_decor_and_keep_existing():
    from package_items import brief_requests

    req = brief_requests(_living())
    assert req["open_budget"] is True
    assert [d["kind"] for d in req["decor"]] == ["art", "rug", "cozy", "table_setting"]
    assert "linking dining and kitchen" in req["decor"][0]["note"]
    assert [k["name"] for k in req["keep_existing"]] == ["art above the sofa"]


def test_negated_decor_is_not_a_request():
    from package_items import brief_requests

    req = brief_requests({"brief": {"notes": "No rug please. Don't add plants."}})
    assert [d["kind"] for d in req["decor"]] == []


def test_brief_reaches_the_drafter_and_the_image_prompt():
    from ai_drafter import BUDGET, _summarize_lead
    from ai_image_generator import _build_edit_prompt

    lead = _living(budget="open")
    summary = _summarize_lead(lead)
    assert "Budget: Open budget (no cap)" in summary
    assert "Project brief notes (authoritative)" in summary
    assert "BRIEF REQUEST — include larger wall art" in summary
    assert "KEEP EXISTING — the customer's existing art above the sofa stays" in summary
    assert BUDGET["open"] == "Open budget (no cap)"
    prompt = _build_edit_prompt(lead, {"shopping_list": [{"name": "Round jute rug", "qty": 1, "price": 150}]})
    assert "PLANNED ADDITIONS" in prompt and "Round jute rug" in prompt and "Set dining table" in prompt
    assert "RUG ADDITION" in prompt


def test_open_budget_is_an_intake_choice_and_a_band():
    from blueprint_layers import BUDGET_LABELS, _band_status
    from intake import BUDGETS, build_fact_sheet

    assert BUDGETS["open"] == "Open budget (no cap)"
    assert BUDGET_LABELS["open"] == "Open budget (no cap)"
    assert _band_status({"budget": "open"}, 900)[0] == "pass"
    sheet = build_fact_sheet({"id": "x", "photos": [], "intake": {"budget": "open"}})
    assert sheet["budget"]["label"] == "Open budget (no cap)"


def test_frontend_offers_the_open_budget():
    from pathlib import Path

    model = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "intake" / "model.js").read_text()
    assert '{ id: "open", label: "Open budget (no cap)" }' in model


def test_requested_decor_missing_from_the_plan_blocks_and_is_satisfied_by_the_list():
    from package_items import consistency_report

    missing = consistency_report(_living(), {"shopping_list": []})
    codes = [i["code"] for i in missing["issues"] if i["severity"] == "block"]
    assert codes.count("brief_request_missing") == 4
    plan = {
        "shopping_list": [
            {"name": "Large framed abstract print", "qty": 1, "price": 120},
            {"name": "Round jute area rug", "qty": 1, "price": 150},
            {"name": "Linen throw pillow covers", "qty": 2, "price": 20},
            {"name": "Linen placemats and table runner", "qty": 1, "price": 30},
        ]
    }
    done = consistency_report(_living(), plan)
    assert not [i for i in done["issues"] if i["code"] == "brief_request_missing"]


def test_replacing_art_the_customer_keeps_is_flagged():
    from package_items import consistency_report

    plan = {"strategy": ["Replace the art above the sofa with a larger canvas."]}
    report = consistency_report(_living(), plan)
    assert any(i["code"] == "keep_existing_contradicted" for i in report["issues"])


def test_kept_items_show_on_the_board_and_room_flow_copy():
    from image_board import board_spec
    from package_facts import what_stays

    spec = board_spec(_living(), {"lead_id": "test-living-0001"}, {})
    assert "Existing art above the sofa" in spec["kept"]
    assert what_stays(_living(), {}) == (
        "Keep the original wall color and all current furniture, and the existing art above the sofa."
    )


def test_admin_brief_endpoint_saves_notes_and_open_budget(monkeypatch):
    from fastapi.testclient import TestClient

    import server
    from tests.test_member_auth import FakeDB

    fake = FakeDB()
    fake.leads.docs.append({"id": LIVING_ID, "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"})
    monkeypatch.setattr(server, "db", fake)

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as c:
        r = c.put(
            f"/api/admin/leads/{LIVING_ID}/brief",
            json={"notes": BRIEF, "budget": "open"},
            headers={"X-Admin-Token": server.ADMIN_PASSWORD},
        )
        anon = c.put(f"/api/admin/leads/{LIVING_ID}/brief", json={"notes": "x"})
    assert r.status_code == 200, r.text
    assert anon.status_code in (401, 403)
    saved = fake.leads.docs[0]
    assert saved["brief"]["notes"] == BRIEF and saved["budget"] == "open"
    assert [d["kind"] for d in r.json()["requests"]["decor"]] == ["art", "rug", "cozy", "table_setting"]


# ──────────────────────────── 4. Room Flow ─────────────────────────────


def test_room_flow_says_approximate_and_unconfirmed():
    from room_flow import guide_outline_sentence, outline_phrases, zone_map_spec, zone_map_text

    phrases = outline_phrases({"outline_source": "approximate"})
    for key in ("map_note", "rule", "board_caption"):
        assert "approximate" in phrases[key].lower()
        assert "not confirmed" in phrases[key].lower()
    assert "not confirmed" in guide_outline_sentence({})
    text = zone_map_text(zone_map_spec({"id": LIVING_ID, "space_type": "living_room"}, {"lead_id": LIVING_ID}))
    assert "Measurements are not confirmed" in text


def test_living_room_record_shows_seating_and_both_table_configurations():
    from room_flow import _config_line, furniture_footprints, load_record, table_chairs, validate_room_flow

    flow = load_record(LIVING_ID)
    assert validate_room_flow(flow) == []
    by_id = {f["id"]: f for f in flow["furniture"]}
    sofa, table = by_id["sofa"], by_id["dining"]
    assert sofa["kind"] == "sofa" and sofa["chaise"] and "CHAISE" in sofa["label"]
    assert table["kind"] == "table" and table["seats"] == 2 and table["extended"]["seats"] == 4
    assert _config_line(table) == "2 SEATS \u00b7 OPENS TO 4"
    assert len(table_chairs(table["rect"], 2)) == 2
    assert len(table_chairs(table["extended"]["rect"], 4)) == 4
    assert len(furniture_footprints(table)) == 1 + 2 + 1 + 4


def test_living_and_dining_must_be_connected_by_the_clear_path():
    import copy

    from room_flow import default_room_flow, load_record, validate_room_flow

    flow = copy.deepcopy(load_record(LIVING_ID))
    flow["path"] = [[1.08, 0.04], [1.1, 0.5]]
    assert "the clear path must connect the living and dining zones" in validate_room_flow(flow)
    # The default layout for any living room connects them on its own.
    default = default_room_flow(
        {"space_type": "living_room"},
        {"zones": [{"title": "Living", "desc": "Sofa"}, {"title": "Dining", "desc": "Table"}, {"title": "Entry", "desc": ""}]},
    )
    assert validate_room_flow(default) == []


def test_extended_table_must_contain_the_compact_one():
    import copy

    from room_flow import load_record, validate_room_flow

    flow = copy.deepcopy(load_record(LIVING_ID))
    table = next(f for f in flow["furniture"] if f["id"] == "dining")
    table["extended"]["rect"] = [0.3, 0.87, 0.5, 0.97]
    assert any("must contain the compact one" in i for i in validate_room_flow(flow))


def _geometry(flow):
    from room_flow import H, W, _s, draw_floor_plan

    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    return draw_floor_plan(base, (_s(118), _s(300), _s(445), _s(637)), flow, markers=True)


@pytest.mark.parametrize("lead_id", [LIVING_ID, NURSERY_ID])
def test_map_labels_keep_clear_of_zone_borders_and_walls(lead_id):
    from room_flow import LABEL_PAD, box_segment_gap, resolve_room_flow

    flow = resolve_room_flow({"id": lead_id, "space_type": "living_room" if lead_id == LIVING_ID else "nursery"}, {})
    geom = _geometry(flow)
    pad = LABEL_PAD * geom["unit"]
    edges = geom["zone_edges"] + geom["wall_edges"]
    assert geom["text_boxes"]
    for box in geom["text_boxes"]:
        gaps = [box_segment_gap(box, seg) for seg in edges]
        assert min(gaps) >= pad - 0.5, (box, min(gaps))
    for i, a in enumerate(geom["text_boxes"]):
        for b in geom["text_boxes"][i + 1 :]:
            assert not (a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]), (a, b)


def test_tv_console_and_bench_labels_no_longer_touch_their_zone_borders(monkeypatch):
    """The two labels Camila flagged, measured on the drawn map."""
    import room_flow
    from room_flow import LABEL_PAD, box_segment_gap, load_record

    painted: Dict[str, Any] = {}
    real = room_flow._label_block

    def spy(draw, cx, top, lines):
        box = real(draw, cx, top, lines)
        painted[lines[0][0]] = box
        return box

    monkeypatch.setattr(room_flow, "_label_block", spy)
    geom = _geometry(load_record(LIVING_ID))
    pad = LABEL_PAD * geom["unit"]
    for label in ("TV CONSOLE", "BENCH + MIRROR"):
        box = painted[label]
        assert min(box_segment_gap(box, seg) for seg in geom["zone_edges"]) >= pad - 0.5, label


def test_default_maps_keep_labels_off_borders_for_other_rooms():
    from room_flow import LABEL_PAD, box_segment_gap, default_room_flow

    flow = default_room_flow(
        {"space_type": "garage"},
        {"zones": [{"title": "Parking"}, {"title": "Tool wall"}, {"title": "Sports gear storage"}, {"title": "Recycling"}]},
    )
    geom = _geometry(flow)
    pad = LABEL_PAD * geom["unit"]
    for box in geom["text_boxes"]:
        assert min(box_segment_gap(box, seg) for seg in geom["zone_edges"] + geom["wall_edges"]) >= pad - 0.5


# ──────────────────────────── 5. Consistency ─────────────────────────────


def _views(*qas):
    return [
        {"label": f"SOURCE_0{i}", "after_label": f"AFTER_0{i}", "after_url": f"/api/uploads/photo/{i:024x}", "status": "approved", "qa": qa}
        for i, qa in enumerate(qas, start=1)
    ]


def test_text_that_adds_a_rug_needs_a_view_that_shows_it():
    from package_items import consistency_report

    plan = {
        "shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}],
        "source_afters": _views({"ok": True, "visible_additions": [], "unlisted_additions": []}),
    }
    report = consistency_report({"id": "x", "space_type": "living_room"}, plan)
    shown = [i for i in report["issues"] if i["code"] == "addition_not_shown"]
    assert shown and shown[0]["severity"] == "block"
    plan["source_afters"] = _views({"ok": True, "visible_additions": ["Round jute area rug"], "unlisted_additions": []})
    report = consistency_report({"id": "x", "space_type": "living_room"}, plan)
    assert not [i for i in report["issues"] if i["code"] == "addition_not_shown"]


def test_a_view_that_shows_something_the_text_never_mentions_is_flagged():
    from package_items import consistency_report

    plan = {"source_afters": _views({"ok": True, "visible_additions": [], "unlisted_additions": ["striped rug", "two baskets"]})}
    report = consistency_report({"id": "x", "space_type": "living_room"}, plan)
    flagged = [i for i in report["issues"] if i["code"] == "view_shows_unplanned_item"]
    assert len(flagged) == 2 and all(i["severity"] == "block" for i in flagged)


def test_a_changed_fixed_piece_in_any_view_blocks():
    from package_items import consistency_report, final_send_block_reason

    plan = {"source_afters": _views({"ok": True}, {"ok": False, "fixed_items_changed": True})}
    report = consistency_report({"id": "x", "space_type": "living_room"}, plan)
    assert any(i["code"] == "fixed_item_changed" and i["view"] == "AFTER_02" for i in report["issues"])
    assert final_send_block_reason(report).startswith("Consistency check failed")
    assert final_send_block_reason({"issues": [{"severity": "warn", "message": "x"}]}) is None


def test_chosen_products_need_direct_links_and_unverified_prices_say_estimate():
    from package_facts import package_facts
    from package_items import consistency_report

    plan = {
        "shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}],
        "shopping_links": [{"name": "Round jute area rug", "url": "https://www.target.com/s?searchTerm=rug", "link_type": "search"}],
    }
    lead = {"id": "x", "space_type": "living_room"}
    assert any(i["code"] == "product_link_not_direct" for i in consistency_report(lead, plan)["issues"])
    row = package_facts(lead, plan)["items"][0]
    assert row["price_estimate"] and row["price_display"] == "$150 est."

    plan["shopping_links"] = [
        {"name": "Round jute area rug", "url": "https://www.target.com/p/rug/-/A-1", "link_type": "product", "verified": True}
    ]
    facts = package_facts(lead, plan)
    assert not any(i["code"] == "product_link_not_direct" for i in consistency_report(lead, plan)["issues"])
    assert facts["items"][0]["price_display"] == "$150 est."  # link tested, price still unconfirmed
    plan["shopping_links"][0]["price_verified"] = True
    facts = package_facts(lead, plan)
    assert facts["items"][0]["price_display"] == "$150" and not facts["estimate_note"]


def test_board_snapshot_names_no_retailer_and_labels_estimates():
    from image_board import board_spec

    plan = {
        "lead_id": "test-living-0001",
        "shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}],
        "shopping_links": [{"name": "Round jute area rug", "url": "https://www.target.com/p/rug/-/A-1", "link_type": "product", "verified": True}],
    }
    spec = board_spec({"id": "test-living-0001", "space_type": "living_room"}, plan, {})
    row = spec["snapshot"]["items"][0]
    assert row["price"] == "$150 est."
    assert "Target" not in row["short"] and "target" not in row["name"].lower()
    assert "est. = estimated price" in spec["total_note"]


def test_guide_names_only_the_planned_items_a_view_shows():
    from pdf_generator import _shown_additions

    lead = _living()
    plan = {"shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}]}
    assert _shown_additions(lead, plan, {"visible_additions": ["round jute area rug", "lamp"]}) == ["round jute area rug"]
    assert _shown_additions(lead, plan, {"visible_additions": []}) == []


def test_customer_copy_must_be_evergreen_and_english():
    from package_items import customer_text_issues

    issues = customer_text_issues({"Design Plan": "Versão 2 para sua revisão", "Companion Guide": "Week 1: clear the floor."})
    assert {i["code"] for i in issues} == {"not_english", "not_evergreen"}
    assert customer_text_issues({"Room Flow": "A calmer flow through the living and dining areas. Version 2 for your review"}) == []


def _final_server(monkeypatch, report):
    import server

    lead = {"id": LIVING_ID, "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"}
    saved: Dict[str, Any] = {}

    class _Coll:
        async def update_one(self, query, update, upsert=False):
            saved.update(update.get("$set") or {})

    class _DB:
        leads = _Coll()
        deliverables = _Coll()

    async def inputs(_lead_id, _request):
        return lead, {"lead_id": LIVING_ID}, {}

    async def consistency(*_a, **_k):
        return report

    sends = []

    async def sent(**kwargs):
        sends.append(kwargs)
        return True, None

    monkeypatch.setattr(server, "db", _DB())
    monkeypatch.setattr(server, "_blueprint_render_inputs", inputs)
    monkeypatch.setattr(server, "_consistency", consistency)
    monkeypatch.setattr(server, "build_pdf", lambda **_kw: b"%PDF")
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: _png())
    monkeypatch.setattr(server, "build_zone_map", lambda **_kw: _png())
    monkeypatch.setattr(server, "final_email_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "send_blueprint", sent)
    return server, saved, sends


def test_send_final_refuses_an_inconsistent_package_unless_overridden(monkeypatch):
    from fastapi import HTTPException

    report = {"issues": [{"code": "addition_not_shown", "severity": "block", "message": "The plan adds area rug but no organized view shows it."}]}
    server, saved, sends = _final_server(monkeypatch, report)

    class _Request:
        query_params: dict = {}

    with pytest.raises(HTTPException) as err:
        asyncio.run(server.send_final_package(LIVING_ID, _Request(), _=True))
    assert err.value.status_code == 409 and "no organized view shows it" in err.value.detail
    assert not sends and saved.get("package_status") != "final"
    with pytest.raises(HTTPException) as silent:
        asyncio.run(server.send_final_package(LIVING_ID, _Request(), override_consistency=True, _=True))
    assert silent.value.status_code == 422 and not sends
    out = asyncio.run(
        server.send_final_package(
            LIVING_ID,
            _Request(),
            override_consistency=True,
            override_reason="Camila approved the rug as a future purchase.",
            _=True,
        )
    )
    assert out["final"] is True and len(sends) == 1
    assert "no organized view" in saved["consistency_override"]["reason"]
    assert saved["consistency_override"]["override_reason"] == "Camila approved the rug as a future purchase."
    assert saved["consistency_override_log"][-1]["issues"][0]["code"] == "addition_not_shown"


def test_consistency_report_lists_the_shared_item_list():
    from package_items import consistency_report

    report = consistency_report(_living(), {"fixed_items": FIXED, "shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}]})
    assert [i["name"] for i in report["fixed_items"]][:2] == ["TV console", "Shoe bench"]
    assert [a["kind"] for a in report["additions"]] == ["art", "rug", "cozy", "table_setting"]
    assert report["additions"][1]["name"] == "Round jute area rug"
    assert report["brief"]["open_budget"] is True


# ──────────────────────────── 6. Photo override ─────────────────────────────


def test_plan_caps_are_unchanged_and_an_override_never_exceeds_six():
    import server
    from intake import PHOTO_OVERRIDE_MAX, max_photos_for

    assert [server.PACKAGES[k]["max_photos"] for k in ("free", "plus", "premium")] == [2, 3, 4]
    premium = server.PACKAGES["premium"]
    assert max_photos_for(premium) == 4
    assert max_photos_for(premium, {"photo_limit_override": 6}) == 6
    assert max_photos_for(premium, {"photo_limit_override": 12}) == PHOTO_OVERRIDE_MAX == 6
    assert max_photos_for(premium, {"photo_limit_override": 2}) == 4


@pytest.mark.parametrize(
    "env,enabled",
    [
        ({}, False),
        ({"ENVIRONMENT": "production"}, False),
        ({"RAILWAY_ENVIRONMENT_NAME": "production"}, False),
        ({"RAILWAY_ENVIRONMENT_NAME": "preview"}, True),
        ({"RAILWAY_ENVIRONMENT_NAME": "flowspace-pr-preview"}, True),
        ({"ENVIRONMENT": "development"}, True),
        ({"ADMIN_PHOTO_OVERRIDE": "1", "RAILWAY_ENVIRONMENT_NAME": "production"}, True),
        ({"ADMIN_PHOTO_OVERRIDE": "0", "RAILWAY_ENVIRONMENT_NAME": "preview"}, False),
    ],
)
def test_photo_override_is_env_gated(env, enabled):
    from intake import photo_override_enabled

    assert photo_override_enabled(env) is enabled


def test_customers_still_cannot_submit_more_than_their_plan(monkeypatch):
    from fastapi import HTTPException

    import server

    data = {"package_id": "premium", "photos": [f"/api/uploads/photo/{i:024x}" for i in range(5)], "photo_limit_override": 6}
    with pytest.raises(HTTPException) as err:
        server.check_lead_intake(data)
    assert err.value.status_code == 422
    assert "photo_limit_override" not in server.LeadCreate.model_fields


def test_intake_and_checkout_honor_a_stored_override():
    import server
    from intake import chargeable_block_reason, validate_intake

    photos = [f"/api/uploads/photo/{i:024x}" for i in range(6)]
    intake = {"version": "beta-4screen-v1", "photos": [{"url": u, "shot": "wide"} for u in photos]}
    premium = server.PACKAGES["premium"]
    over = [e for e in validate_intake(intake, package=premium, photos=photos) if "includes up to" in e["message"]]
    assert over
    allowed = validate_intake(intake, package=premium, photos=photos, lead={"photo_limit_override": 6})
    assert not [e for e in allowed if "includes up to" in e["message"]]
    lead = {"photos": photos, "photo_limit_override": 6}
    assert chargeable_block_reason(lead, premium) is None
    assert "includes up to 4" in chargeable_block_reason({"photos": photos}, premium)


def _admin_client(monkeypatch, lead):
    from fastapi.testclient import TestClient

    import server
    from tests.test_member_auth import FakeDB

    fake = FakeDB()
    fake.leads.docs.append(lead)
    monkeypatch.setattr(server, "db", fake)

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    return TestClient(server.app), fake, server


def test_admin_override_sets_six_photos_for_one_lead(monkeypatch):
    photos = [f"/api/uploads/photo/{i:024x}" for i in range(6)]
    lead = {
        "id": LIVING_ID,
        "name": "Camila Sales",
        "email": "c@example.com",
        "space_type": "living_room",
        "package_id": "premium",
        "photos": photos[:4],
        "intake": {"version": "beta-4screen-v1", "photos": [{"url": u, "shot": "wide", "custom_label": "TV wall" if i == 0 else ""} for i, u in enumerate(photos[:4])]},
    }
    monkeypatch.setenv("ADMIN_PHOTO_OVERRIDE", "1")
    client, fake, server = _admin_client(monkeypatch, lead)
    headers = {"X-Admin-Token": server.ADMIN_PASSWORD}
    with client as c:
        r = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 6, "photos": photos}, headers=headers)
        too_many = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 6, "photos": photos + [f"/api/uploads/photo/{9:024x}"]}, headers=headers)
        over_cap = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 7}, headers=headers)
        foreign = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 6, "photos": ["https://example.com/x.jpg"]}, headers=headers)
        anon = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 6})
    assert r.status_code == 200, r.text
    assert r.json() == {"lead_id": LIVING_ID, "max_photos": 6, "plan_max_photos": 4, "photos": 6, "automation_started": False}
    saved = fake.leads.docs[0]
    assert saved["photos"] == photos and saved["photo_limit_override"] == 6
    assert [p["ref"] for p in saved["intake"]["photos"]] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert saved["intake"]["photos"][0]["custom_label"] == "TV wall"
    assert len(saved["fact_sheet"]["photos"]) == 6
    assert too_many.status_code == 422 and over_cap.status_code == 422 and foreign.status_code == 422
    assert anon.status_code in (401, 403)


def test_admin_override_is_refused_where_the_flag_is_off(monkeypatch):
    lead = {"id": LIVING_ID, "name": "C", "email": "c@example.com", "space_type": "living_room", "package_id": "premium", "photos": []}
    monkeypatch.setenv("ADMIN_PHOTO_OVERRIDE", "0")
    client, _fake, server = _admin_client(monkeypatch, lead)
    with client as c:
        r = c.put(f"/api/admin/leads/{LIVING_ID}/photos", json={"max_photos": 6}, headers={"X-Admin-Token": server.ADMIN_PASSWORD})
    assert r.status_code == 403


def test_six_photos_become_six_views_on_every_document(monkeypatch):
    from render_qa import RenderQAResult
    from tests.test_automation import _FakeFS, _jpeg, _lead, _run

    photos = {f"{i:024x}": _jpeg((30 * i, 80, 60)) for i in range(1, 7)}
    lead = _lead()
    lead["photos"] = [f"/api/uploads/photo/{key}" for key in photos]
    lead["photo_limit_override"] = 6
    drafted = {}

    async def draft(lead_doc, **kwargs):
        drafted.update(kwargs)
        from tests.test_automation import PLAN

        return dict(PLAN)

    monkeypatch.setattr("automation.review_organized_render", lambda **k: RenderQAResult(ok=True))
    counter = {"n": 0}

    def generate(**kwargs):
        counter["n"] += 1
        return _jpeg((10, 10 * counter["n"], 200)), "image/jpeg"

    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(monkeypatch, generate=generate, fs=_FakeFS(store=dict(photos)), lead=lead, capture=captured)
    assert sent is True and counter["n"] == 6
    doc = db.deliverables.docs["lead-img-1"]
    assert [row["status"] for row in doc["source_afters"]] == ["approved"] * 6
    pairs = captured["images"]["source_pairs"]
    assert len(pairs) == 6 and all(p["after"] for p in pairs)

    from image_board import board_layout, board_spec

    spec = board_spec(lead, doc, captured["images"])
    assert len(spec["detail_sources"]) == 6
    assert len(spec["detail_chips"]) == 5
    assert len(board_layout(spec)["sources"]) == 5

    import pdf_generator

    seen = []
    real = pdf_generator._ComparePage

    def spy(text, before, after, *a, **k):
        seen.append(after)
        return real(text, before, after, *a, **k)

    monkeypatch.setattr(pdf_generator, "_ComparePage", spy)
    pdf_generator.build_pdf(lead=lead, deliverable=doc, images=captured["images"])
    assert len([a for a in seen if a]) == 6


def test_drafter_receives_every_room_photo(monkeypatch):
    from automation import run_automation
    from render_qa import RenderQAResult
    from tests.test_automation import PLAN, _FakeDB, _FakeFS, _jpeg, _lead

    photos = {f"{i:024x}": _jpeg((30 * i, 80, 60)) for i in range(1, 4)}
    lead = _lead()
    lead["photos"] = [f"/api/uploads/photo/{key}" for key in photos]
    seen: Dict[str, Any] = {}

    async def draft(lead_doc, **kwargs):
        seen.update(kwargs)
        return dict(PLAN)

    async def generate(**_kwargs):
        return _jpeg((1, 2, 3)), "image/jpeg"

    monkeypatch.setattr("automation.draft_deliverable", draft)
    monkeypatch.setattr("automation.generate_front_view", generate)
    monkeypatch.setattr("automation.review_organized_render", lambda **k: RenderQAResult(ok=True))
    db = _FakeDB()
    db.leads.docs[lead["id"]] = dict(lead)
    assert asyncio.run(run_automation(lead=lead, db=db, fs_bucket=_FakeFS(store=dict(photos)))) is True
    assert seen["reference_photo_bytes"]
    assert len(seen["extra_photo_bytes"]) == 2


# ──────────────────────────── 7. Package output ─────────────────────────────


def test_package_file_names_are_clear_and_consistent():
    from package_files import package_filename

    assert package_filename("Living Room", "design_plan", "pdf") == "FlowSpace_Living_Room_Design_Plan.pdf"
    assert package_filename("Living Room", "design_plan", "png") == "FlowSpace_Living_Room_Design_Plan.png"
    assert package_filename("Living Room", "room_flow", "pdf") == "FlowSpace_Living_Room_Room_Flow.pdf"
    assert package_filename("Living Room", "companion_guide", "pdf") == "FlowSpace_Living_Room_Companion_Guide.pdf"
    assert package_filename("Living Room", "view", "jpg", index=1) == "FlowSpace_Living_Room_View_01.jpg"
    assert package_filename("Living Room", "view", "jpg", index=6, draft=True) == "FlowSpace_Living_Room_View_06_DRAFT.jpg"
    assert package_filename("Nicholas's Nursery", "design_plan", "png") == "FlowSpace_Nicholas_Nursery_Design_Plan.png"


def test_email_package_has_both_board_formats_and_exactly_one_companion_guide():
    from email_service import package_attachments

    views = [{"label": "View-1", "bytes": _png((60, 40))}, {"label": "View-2", "bytes": _png((60, 40))}]
    for draft in (False, True):
        attachments = package_attachments(
            title="Living Room",
            html="<html></html>",
            pdf_bytes=b"%PDF-1.4 guide",
            board_bytes=_png(),
            zone_map_bytes=_png(),
            extra_visuals=views,
            draft=draft,
        )
        files = [a for a in attachments if not a.get("content_id")]
        names = [a["filename"] for a in files]
        s = "_DRAFT" if draft else ""
        assert names == [
            f"FlowSpace_Living_Room_Design_Plan{s}.png",
            f"FlowSpace_Living_Room_Design_Plan{s}.pdf",
            f"FlowSpace_Living_Room_Room_Flow{s}.png",
            f"FlowSpace_Living_Room_Room_Flow{s}.pdf",
            f"FlowSpace_Living_Room_View_01{s}.jpg",
            f"FlowSpace_Living_Room_View_02{s}.jpg",
            f"FlowSpace_Living_Room_Companion_Guide{s}.pdf",
        ]
        assert sum("Companion_Guide" in n for n in names) == 1
        assert sum("Companion" in a["filename"] for a in attachments) == 1
        for att in files:
            if att["filename"].endswith(".pdf") and "Companion" not in att["filename"]:
                assert base64.b64decode(att["content"]).startswith(b"%PDF")


def test_a_second_companion_guide_is_rejected():
    from package_files import PackageFileError, assert_single_companion

    one = [{"filename": "FlowSpace_X_Companion_Guide.pdf"}, {"filename": "FlowSpace_X_Design_Plan.pdf"}]
    assert assert_single_companion(one) == one
    with pytest.raises(PackageFileError):
        assert_single_companion(one + [{"filename": "FlowSpace_X_Companion_Guide_DRAFT.pdf"}])
    with pytest.raises(PackageFileError):
        assert_single_companion([{"filename": "FlowSpace_X_Design_Plan.pdf"}])


def test_board_pdf_is_one_page_of_the_png():
    from pypdf import PdfReader

    from package_files import png_to_pdf

    pdf = png_to_pdf(_png((1434, 2048)))
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (717, 1024)


def test_admin_zip_carries_the_same_file_set(monkeypatch):
    import zipfile

    import server

    lead = {"id": LIVING_ID, "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"}

    async def inputs(_lead_id, _request):
        return lead, {"lead_id": LIVING_ID, "package_version": 2}, {"source_pairs": [{"after": _png()}, {"after": _png()}]}

    monkeypatch.setattr(server, "_blueprint_render_inputs", inputs)
    monkeypatch.setattr(server, "build_pdf", lambda **_kw: b"%PDF guide")
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: _png())
    monkeypatch.setattr(server, "build_zone_map", lambda **_kw: _png())
    response = asyncio.run(server.render_deliverable_package(LIVING_ID, None, _=True))
    names = zipfile.ZipFile(io.BytesIO(response.body)).namelist()
    assert names == [
        "FlowSpace_Living_Room_Design_Plan_DRAFT.png",
        "FlowSpace_Living_Room_Design_Plan_DRAFT.pdf",
        "FlowSpace_Living_Room_Room_Flow_DRAFT.png",
        "FlowSpace_Living_Room_Room_Flow_DRAFT.pdf",
        "FlowSpace_Living_Room_View_01_DRAFT.jpg",
        "FlowSpace_Living_Room_View_02_DRAFT.jpg",
        "FlowSpace_Living_Room_Companion_Guide_DRAFT.pdf",
    ]
    assert 'filename="FlowSpace_Living_Room_Package_DRAFT_V2.zip"' in response.headers["content-disposition"]


def test_board_endpoint_serves_a_pdf_on_request(monkeypatch):
    import server

    lead = {"id": LIVING_ID, "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"}

    async def inputs(_lead_id, _request):
        return lead, {"lead_id": LIVING_ID, "package_status": "final"}, {}

    monkeypatch.setattr(server, "_blueprint_render_inputs", inputs)
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: _png())
    pdf = asyncio.run(server.render_deliverable_board(LIVING_ID, None, format="pdf", _=True))
    assert pdf.media_type == "application/pdf" and pdf.body.startswith(b"%PDF")
    assert 'filename="FlowSpace_Living_Room_Design_Plan.pdf"' in pdf.headers["content-disposition"]
    png = asyncio.run(server.render_deliverable_board(LIVING_ID, None, _=True))
    assert 'filename="FlowSpace_Living_Room_Design_Plan.png"' in png.headers["content-disposition"]


def test_draft_send_is_never_blocked_by_missing_links_and_flags_them(monkeypatch):
    """Review sends go out with "est." prices; missing direct links are reported, not enforced."""
    import server

    lead = {"id": LIVING_ID, "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"}
    deliverable = {
        "lead_id": LIVING_ID,
        "package_version": 2,
        "shopping_list": [{"name": "Round jute area rug", "qty": 1, "price": 150}],
    }

    class _Coll:
        async def update_one(self, *_a, **_k):
            return None

    class _DB:
        leads = _Coll()
        deliverables = _Coll()

    async def inputs(_lead_id, _request):
        return lead, deliverable, {}

    sends = []

    async def sent(**kwargs):
        sends.append(kwargs)
        return True, None

    monkeypatch.setattr(server, "db", _DB())
    monkeypatch.setattr(server, "_blueprint_render_inputs", inputs)
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: _png())
    monkeypatch.setattr(server, "build_zone_map", lambda **_kw: _png())
    monkeypatch.setattr(server, "draft_send_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "send_draft_package", sent)

    class _Request:
        query_params: dict = {}

    out = asyncio.run(server.send_draft_package_endpoint(LIVING_ID, _Request(), to=None, _=True))
    assert out["sent"] is True and out["final"] is False and len(sends) == 1
    links = [i for i in out["consistency"]["issues"] if i["code"] == "product_link_not_direct"]
    assert links and out["consistency"]["blocks_final"] >= 1

    from image_board import board_spec

    assert board_spec(lead, deliverable, {})["snapshot"]["items"][0]["price"] == "$150 est."

    # The same package is refused as a FINAL send.
    from fastapi import HTTPException

    monkeypatch.setattr(server, "final_email_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "send_blueprint", sent)
    with pytest.raises(HTTPException) as err:
        asyncio.run(server.send_final_package(LIVING_ID, _Request(), _=True))
    assert err.value.status_code == 409 and "tested direct product link" in err.value.detail
    assert len(sends) == 1
