"""Budget and nursery storage must agree before a Blueprint is drawn."""
import json
from pathlib import Path

from blueprint_consistency import (
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
