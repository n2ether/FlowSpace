"""Budget and nursery storage must agree before a Blueprint is drawn."""
import io
import json
from pathlib import Path

from pypdf import PdfReader

from blueprint_consistency import (
    internal_record,
    item_forbidden,
    note_conflicts,
    prepare_deliverable,
    shopping_total,
)
from space_rails import is_nursery_space

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nursery_nico.json"


def test_note_conflict_is_a_kit_priced_below_the_lines():
    assert note_conflicts("Total ~$124–$154 for anchors.", 174)
    assert not note_conflicts("$100 – $300 typical for this starter kit", 227)
    assert not note_conflicts("$100 – $300 typical for this starter kit", 30)
    assert note_conflicts("Estimated total $154", 174)


def test_nursery_prepare_drops_cubbies_and_aligns_the_total():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw_total = shopping_total(doc["deliverable"])
    assert raw_total == 236
    prepared = prepare_deliverable(doc["lead"], doc["deliverable"])
    names = [item["name"].lower() for item in prepared["shopping_list"]]
    assert all("cubby" not in name and "replace dresser" not in name for name in names)
    assert shopping_total(prepared) == 174
    assert prepared["budget_display"] == "$174"
    assert "$124" not in prepared["budget_note"]
    assert "$154" not in prepared["budget_note"]
    assert "174" in prepared["budget_note"]
    blob = json.dumps(prepared).lower()
    assert "replace the dresser drawers with baskets" not in blob
    assert "six-drawer" in blob or "six drawer" in blob
    assert "do not replace dresser drawers with baskets" in blob
    assert "do not add large open cubbies" in blob
    assert any("one step" in line.lower() for line in prepared["strategy"])


def test_prepare_is_idempotent():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    once = prepare_deliverable(doc["lead"], doc["deliverable"])
    twice = prepare_deliverable(doc["lead"], once)
    assert twice["shopping_list"] == once["shopping_list"]
    assert twice["budget_note"] == once["budget_note"]
    assert twice["budget_display"] == once["budget_display"]
    assert twice["strategy"] == once["strategy"]


def test_garage_bins_are_not_treated_as_a_nursery():
    lead = {"space_type": "garage", "must_stay": "Existing workbench, kids' bikes"}
    assert is_nursery_space(lead) is False
    deliverable = {
        "shopping_list": [{"name": "Lidded bins", "qty": 6, "price": 12}],
        "budget_note": "$100 – $300 typical for this starter kit",
        "strategy": ["Hide clutter in matching bins"],
    }
    prepared = prepare_deliverable(lead, deliverable)
    assert prepared["shopping_list"][0]["name"] == "Lidded bins"
    assert "dresser" not in " ".join(prepared["strategy"]).lower()
    assert prepared["budget_display"] == "$72"
    assert prepared["budget_note"].startswith("$100")


def test_item_forbidden_targets_drawer_swaps_not_every_basket():
    assert item_forbidden("Large open cubby unit")
    assert item_forbidden("Basket set to replace dresser drawers")
    assert not item_forbidden("Felt frame bumpers")
    assert not item_forbidden("Lidded bins")


def test_blanket_sku_and_150_vs_230_cannot_disagree():
    """A $80 blanket made the list $230 while the prose still said $150."""
    from blueprint_consistency import companion_sections, safety_essentials, safety_guidance
    from image_board import board_spec
    from pdf_generator import build_pdf

    lead = {
        "name": "Camila Sales",
        "space_type": "kids_room",
        "budget": "100_300",
        "goals": "Keep the space theme",
        "must_stay": "Six-drawer dresser",
        "desired_feeling": ["calm"],
        "color_prefs": ["earth"],
    }
    deliverable = {
        "intro": "Shop this refresh for about $150.",
        "summary": "The kit total is $150.",
        "needs": ["Anchor the dresser"],
        "zones": [
            {"title": "Safe Sleep Zone", "desc": "Crib stays clear."},
            {"title": "Diaper & Dress Zone", "desc": "Six-drawer dresser stays."},
            {"title": "Play & Movement Zone", "desc": "Clear floor path to the door."},
            {"title": "Comfort & Feed Zone", "desc": "Rocker by the window."},
        ],
        "shopping_list": [
            {"name": "Furniture anchor kit", "qty": 1, "price": 30},
            {"name": "Blackout thermal curtain panels", "qty": 2, "price": 40},
            {"name": "Nursery blanket", "qty": 1, "price": 80},
            {"name": "Under-door draft sweep", "qty": 1, "price": 40},
        ],
        "budget_note": "Kit total about $150.",
        "strategy": [
            "Add a blanket layer over the window.",
            "Consider a wall-mounted heater if the room stays cold.",
            "Anchor the six-drawer dresser.",
        ],
        "action_plan": ["Anchor the dresser before anything else."],
        "notes": "Windows stay ~95% true to the photo.",
    }
    assert shopping_total(deliverable) == 230
    prepared = prepare_deliverable(lead, deliverable)
    names = [item["name"].lower() for item in prepared["shopping_list"]]
    assert all("blanket" not in name for name in names)
    assert shopping_total(prepared) == 150
    assert prepared["budget_display"] == "$150"
    blob = " ".join(
        [
            prepared["intro"],
            prepared["summary"],
            prepared["budget_note"],
            " ".join(prepared["strategy"]),
        ]
    ).lower()
    assert "$230" not in blob
    assert "150" in blob
    assert "blanket layer" not in blob
    assert "thermal window layer" in blob
    assert "wall-mounted heater" not in blob
    assert "six-drawer" in blob or "dresser" in blob

    sections, _doc = companion_sections(lead, deliverable)
    spec = board_spec(lead, deliverable, {})
    assert sections["list_total"] == "$150"
    assert spec["budget_display"] == "$150"
    assert sections["safety"] == spec["safety"]
    safety = " ".join(sections["safety"]).lower()
    assert "no loose blankets" in safety or "loose blankets" in safety
    assert "sleep sack" in safety
    assert "teddy" in safety
    assert "heater" in safety and "do not" in safety
    assert "window cords" in safety
    climate = " ".join(sections["climate"]).lower()
    assert "68" in climate
    assert "thermal window layer" in climate
    assert "blanket layer" not in climate

    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)
    low = text.lower()
    assert "nursery blanket" not in low
    assert "$230" not in text
    assert "$150" in text
    assert "blanket layer" not in low
    assert "list total" in low
    assert safety_essentials(lead, prepared)[0] in " ".join(text.split())


def test_prose_kit_price_follows_the_list_when_nothing_is_removed():
    lead = {"space_type": "kids_room", "budget": "100_300", "must_stay": "Six-drawer dresser"}
    deliverable = {
        "intro": "The refresh is about $150.",
        "shopping_list": [
            {"name": "Furniture anchor kit", "qty": 1, "price": 150},
            {"name": "Cord clips", "qty": 1, "price": 80},
        ],
        "budget_note": "Kit total $150.",
        "strategy": ["Anchor the six-drawer dresser."],
    }
    prepared = prepare_deliverable(lead, deliverable)
    assert shopping_total(prepared) == 230
    assert prepared["budget_display"] == "$230"
    assert "$150" not in prepared["intro"]
    assert "230" in prepared["intro"]
    assert "$150" not in prepared["budget_note"]
    assert "230" in prepared["budget_note"]


def test_nursery_safety_and_climate_are_each_written_once():
    from blueprint_consistency import companion_sections

    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sections, _prepared = companion_sections(doc["lead"], doc["deliverable"])
    safety = [line.lower() for line in sections["safety"]]
    climate = " ".join(sections["climate"]).lower()
    assert len(safety) == len(set(safety))
    assert "heater" not in climate
    assert "portable heater" not in climate
    assert "68" in climate
    assert "thermal window layer" in climate
    assert sections["reset_title"] == "Bedtime ritual"
    assert sections["maintenance"].lower().startswith("bedtime ritual")
    for line in sections["safety"]:
        assert line.lower() not in sections["maintenance"].lower()


def test_nursery_zone_locations_match_the_photos():
    """Live zone copy put the crib away from the window and the rocker beside it."""
    from pdf_generator import build_pdf

    lead = {"name": "Camila Sales", "space_type": "kids_room", "must_stay": "Six-drawer dresser, crib, rocker"}
    deliverable = {
        "zones": [
            {
                "title": "Safe Sleep Zone",
                "desc": (
                    "The crib stays in its current corner, away from the window and dresser. "
                    "The sleep surface stays clear except a fitted sheet."
                ),
            },
            {
                "title": "Calm Feeding & Rocking Zone",
                "desc": (
                    "The rocker stays where it is, close to the window. "
                    "Do not add a portable heater near the crib."
                ),
            },
        ],
    }
    prepared = prepare_deliverable(lead, deliverable)
    by_title = {zone["title"]: zone["desc"] for zone in prepared["zones"]}
    crib = by_title["Safe Sleep Zone"]
    rocker = by_title["Calm Feeding & Rocking Zone"]
    assert crib == (
        "The crib stays on the wall opposite the dresser, with its near end toward the window. "
        "The sleep surface stays clear except a fitted sheet."
    )
    assert rocker == (
        "The rocker stays on the crib wall, farther from the window than the crib. "
        "Do not add a portable heater near the crib."
    )
    assert "away from the window" not in crib.lower()
    assert "close to the window" not in rocker.lower()
    # Zone sentences live in the internal record; the customer guide keeps the short safety list.
    record = " ".join(zone["desc"] for zone in internal_record(lead, deliverable)["zones"])
    assert "near end toward the window" in record
    assert "farther from the window than the crib" in record
    assert "away from the window" not in record.lower()
    assert "close to the window" not in record.lower()
    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    text = " ".join(
        " ".join((page.extract_text() or "").split())
        for page in PdfReader(io.BytesIO(pdf)).pages
    )
    assert "away from the window" not in text.lower()
    assert "close to the window" not in text.lower()
    assert "fitted sheet" in text.lower()
    assert "portable heater" in text.lower()
