"""Unit tests for blueprint_layers schema, coerce, derive, and Ryan answers."""
import json
from pathlib import Path

from ai_drafter import _coerce
from blueprint_layers import (
    LAYER_KEYS,
    SCHEMA_PATH,
    coerce_layers,
    derive_layers,
    layers_complete,
    load_json_schema,
    resolve_layers,
    ryan_answers,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "bakeoff" / "garage_org_space.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_json_schema_lists_six_layers():
    schema = load_json_schema()
    assert SCHEMA_PATH.is_file()
    assert schema["title"] == "blueprint_layers"
    required = schema["required"]
    for key in LAYER_KEYS:
        assert key in required
        assert key in schema["properties"]


def test_coerce_fills_defaults_and_normalizes_checks():
    layers = coerce_layers(
        {
            "human_need": {"routine": "Park nightly", "desired_feeling": ["calm", "practical"]},
            "validation": {"fit": "Shelves on existing wall"},
        }
    )
    assert layers["schema_version"] == "1.0"
    assert layers["human_need"]["routine"] == "Park nightly"
    assert "calm" in layers["human_need"]["desired_feeling"]
    assert layers["spatial_constraint"]["preserve_shell"] is True
    assert layers["spatial_constraint"]["no_invented_floor_plan"] is True
    assert layers["validation"]["fit"]["note"] == "Shelves on existing wall"
    assert layers["validation"]["fit"]["status"] in {"pass", "watch", "fail"}


def test_derive_from_garage_lead_answers_ryan_questions():
    lead = {
        "space_type": "garage",
        "must_stay": "Workbench, bikes",
        "daily_improvement": "Park and find the bag",
        "budget": "100_300",
        "storage_needs": ["tools", "sports"],
        "bothers_about": ["clutter"],
        "desired_feeling": ["practical"],
        "biggest_challenge": "Can't park",
    }
    plan = {
        "intro": "Same walls, calmer system.",
        "needs": ["Clear stall"],
        "zones": [{"title": "Parking Zone", "desc": "Keep the stall"}],
        "shopping_list": [{"name": "Bins", "qty": 4, "price": 12}],
        "action_plan": ["Declutter"],
        "benefits": ["Easier to park"],
        "budget_note": "$100 – $300 typical",
    }
    layers = derive_layers(lead, plan)
    assert layers_complete(layers)
    answers = ryan_answers(layers)
    assert "park" in answers["routine"].lower()
    assert "workbench" in answers["possessions"].lower()
    assert "95%" in answers["physical_fit"]
    assert "100" in answers["budget"] or "$" in answers["budget"]
    assert answers["why_it_should_work"]
    assert "15 ft" not in json.dumps(layers)
    assert layers["spatial_constraint"]["paint_optional"] is True


def test_resolve_prefers_stored_then_backfills():
    lead = {"space_type": "laundry", "daily_improvement": "Sort wash nightly", "budget": "under_100"}
    deliverable = {
        "zones": [{"title": "Fold", "desc": "Existing counter"}],
        "blueprint_layers": {
            "human_need": {"routine": "Wash, hang, fold before bed"},
            "recommendation": {"why_it_should_work": "Machines stay put; only bins move."},
        },
    }
    layers = resolve_layers(lead, deliverable)
    assert layers["human_need"]["routine"] == "Wash, hang, fold before bed"
    assert layers["recommendation"]["why_it_should_work"].startswith("Machines stay")
    assert layers["spatial_constraint"]["windows_dims_fidelity"] == "~95%"
    assert layers_complete(layers)


def test_ai_coerce_persists_merged_layers():
    lead = {
        "space_type": "closet",
        "must_stay": "Winter coats",
        "daily_improvement": "Grab a coat in 20 seconds",
        "budget": "100_300",
    }
    plan = {
        "intro": "A closet you can use in the dark.",
        "needs": ["Hanging by frequency"],
        "zones": [{"title": "Daily rod", "desc": "Keep the existing rod"}],
        "shopping_list": [{"name": "Velvet hangers", "qty": 20, "price": 1.5}],
        "action_plan": ["Empty the rod"],
        "benefits": ["Faster mornings"],
        "blueprint_layers": {
            "observation": {"possessions": ["Winter coats"]},
            "human_need": {"routine": "Grab a coat in 20 seconds on school mornings"},
            "validation": {
                "budget_band": {"status": "pass", "note": "Hangers fit the band", "band": "$100 – $300"}
            },
            "recommendation": {"why_it_should_work": "Frequency zoning on the rod they already have."},
        },
    }
    out = _coerce(plan, lead=lead)
    assert "blueprint_layers" in out
    layers = out["blueprint_layers"]
    assert layers["observation"]["possessions"] == ["Winter coats"]
    assert "20 seconds" in layers["human_need"]["routine"]
    assert layers_complete(layers)


def test_bakeoff_fixture_is_complete_org_space_not_bedroom():
    doc = _fixture()
    assert doc["space_type"] == "garage"
    assert "bedroom" not in json.dumps(doc).lower() or doc["lead"]["space_type"] != "bedroom"
    lead = doc["lead"]
    deliverable = doc["deliverable"]
    assert lead["space_type"] == "garage"
    layers = deliverable["blueprint_layers"]
    assert layers_complete(layers)
    answers = ryan_answers(layers)
    assert "park" in answers["routine"].lower()
    assert "workbench" in answers["possessions"].lower()
    assert "95%" in answers["physical_fit"]
    assert "227" in answers["budget"] or "100" in answers["budget"]
    assert "routine" in answers["why_it_should_work"].lower() or "zoning" in answers["why_it_should_work"].lower()
    dump = json.dumps(layers)
    assert "15 ft" not in dump and "15ft" not in dump
    assert layers["spatial_constraint"]["no_invented_floor_plan"] is True
    assert layers["spatial_constraint"]["paint_optional"] is True
    assert layers["validation"]["fit"]["status"] == "pass"
    assert layers["validation"]["conflicts"]
    assert layers["validation"]["assumptions"]
