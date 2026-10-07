"""Beta intake: validation, chargeability, the shared fact sheet, and API enforcement."""
import copy

import pytest

from intake import (
    INTAKE_VERSION,
    build_fact_sheet,
    chargeable_block_reason,
    fact_sheet_prompt,
    measurements_needed,
    room_flow_mode,
    unresolved_contradictions,
    validate_intake,
)
from tests.test_member_auth import FakeDB, _signup  # noqa: F401  (fixture helpers)

FREE = {"id": "free", "name": "Free", "price": 0.0, "max_photos": 2}
PLUS = {"id": "plus", "name": "Plus", "price": 10.0, "max_photos": 3}
PREMIUM = {"id": "premium", "name": "Premium", "price": 20.0, "max_photos": 4}

P1 = "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa"
P2 = "/api/uploads/photo/bbbbbbbbbbbbbbbbbbbbbbbb"


def _intake(**over):
    base = {
        "version": INTAKE_VERSION,
        "plan": "plus",
        "space_type": "kids_room",
        "other_label": "",
        "priority": "storage",
        "specifics": "Toys everywhere",
        "photo_mode": "photos",
        "coverage": "whole",
        "photos": [{"ref": "P1", "label": "Photo 1", "custom_label": "Crib wall", "shot": "wide", "url": P1}],
        "keep": "keep_selected",
        "keep_items": "six-drawer dresser; round 5 ft rug",
        "limits": ["no_drilling"],
        "limit_other": "",
        "layout_within_current": False,
        "change_avoid": "avoid large open cubes",
        "budget": "100_300",
        "visual": {"mode": "match_current", "style": "", "palette": ""},
        "space_answers": {"activities": ["sleep", "changing"]},
        "needs_exact_fit": False,
        "measurements_needed": False,
        "measure_mode": "",
        "measurements": None,
        "climate": "",
        "shop_country": "",
        "shop_postal": "",
        "room_flow_mode": "not_to_scale",
    }
    base.update(over)
    return base


def _fields(errors):
    return {e["field"] for e in errors}


class TestValidateIntake:
    def test_valid_plus_intake(self):
        assert validate_intake(_intake(), package=PLUS, photos=[P1]) == []

    def test_paid_without_photos_is_rejected(self):
        errs = validate_intake(_intake(photos=[]), package=PLUS, photos=[])
        assert "photos" in _fields(errs)

    def test_paid_conceptual_is_rejected(self):
        errs = validate_intake(_intake(photo_mode="conceptual", photos=[], coverage=""), package=PLUS, photos=[])
        assert "photos" in _fields(errs)

    def test_free_conceptual_is_allowed(self):
        intake = _intake(plan="free", photo_mode="conceptual", photos=[], coverage="")
        assert validate_intake(intake, package=FREE, photos=[]) == []

    def test_closeups_only_are_not_enough(self):
        intake = _intake(photos=[{"url": P1, "shot": "detail"}])
        assert "photos" in _fields(validate_intake(intake, package=PLUS, photos=[P1]))

    def test_photo_cap_enforced(self):
        urls = [P1, P2, P1 + "c"]
        intake = _intake(plan="free", photos=[{"url": u, "shot": "wide"} for u in urls])
        assert "photos" in _fields(validate_intake(intake, package=FREE, photos=urls))

    def test_photo_list_must_match_intake(self):
        assert "photos" in _fields(validate_intake(_intake(), package=PLUS, photos=[P2]))

    def test_coverage_required(self):
        assert "coverage" in _fields(validate_intake(_intake(coverage=""), package=PLUS, photos=[P1]))

    def test_explicit_answers_required(self):
        errs = validate_intake(_intake(keep="", limits=[], budget=""), package=PLUS, photos=[P1])
        assert {"keep", "limits", "budget"} <= _fields(errs)

    def test_selected_items_required(self):
        assert "keep_items" in _fields(validate_intake(_intake(keep_items=""), package=PLUS, photos=[P1]))

    def test_other_space_out_of_scope(self):
        errs = validate_intake(_intake(space_type="other", other_label="whole house"), package=PLUS, photos=[P1])
        assert "other_label" in _fields(errs)

    def test_none_with_limit_is_contradiction(self):
        intake = _intake(limits=["none", "no_painting"])
        assert unresolved_contradictions(intake)
        assert "limits" in _fields(validate_intake(intake, package=PLUS, photos=[P1]))

    def test_layout_conflict_resolved_by_within_current(self):
        intake = _intake(priority="better_layout", limits=["keep_layout"])
        assert unresolved_contradictions(intake)
        intake["layout_within_current"] = True
        assert unresolved_contradictions(intake) == []
        assert measurements_needed(intake) is False

    def test_layout_change_requires_measure_decision(self):
        intake = _intake(priority="better_layout", limits=["none"])
        assert "measure_mode" in _fields(validate_intake(intake, package=PLUS, photos=[P1]))
        intake["measure_mode"] = "not_to_scale"
        assert validate_intake(intake, package=PLUS, photos=[P1]) == []
        assert room_flow_mode(intake) == "not_to_scale"

    def test_provided_measurements_must_be_numbers(self):
        intake = _intake(
            priority="better_layout",
            limits=["none"],
            measure_mode="provided",
            measurements={"unit": "ft", "width": 0, "length": "x"},
        )
        errs = validate_intake(intake, package=PLUS, photos=[P1])
        assert {"measure_width", "measure_length"} <= _fields(errs)

    def test_garage_vehicle_needs_measurements(self):
        intake = _intake(space_type="garage", space_answers={"vehicle": "yes"})
        assert measurements_needed(intake)

    def test_premium_shopping_needs_country(self):
        intake = _intake(plan="premium")
        assert "shop_country" in _fields(validate_intake(intake, package=PREMIUM, photos=[P1]))
        intake["shop_country"] = "US"
        assert validate_intake(intake, package=PREMIUM, photos=[P1]) == []

    def test_stale_version_rejected(self):
        assert "submit" in _fields(validate_intake(_intake(version="old"), package=PLUS, photos=[P1]))


class TestChargeable:
    def test_free_always_ok(self):
        assert chargeable_block_reason({"photos": []}, FREE) is None

    def test_paid_without_photos_blocked_even_without_intake(self):
        assert chargeable_block_reason({"photos": []}, PLUS)

    def test_paid_with_wide_photo_ok(self):
        assert chargeable_block_reason({"photos": [P1], "intake": _intake()}, PLUS) is None

    def test_paid_with_only_closeups_blocked(self):
        lead = {"photos": [P1], "intake": _intake(photos=[{"url": P1, "shot": "detail"}])}
        assert chargeable_block_reason(lead, PLUS)


class TestFactSheet:
    def _lead(self, **intake_over):
        return {
            "id": "lead-1",
            "package_id": "plus",
            "space_type": "kids_room",
            "photos": [P1, P2],
            "intake": _intake(
                photos=[
                    {"url": P1, "shot": "wide", "custom_label": "Crib wall"},
                    {"url": P2, "shot": "detail", "custom_label": ""},
                ],
                **intake_over,
            ),
        }

    def test_ids_are_stable_and_map_one_after_per_source(self):
        fs = build_fact_sheet(self._lead())
        assert [p["id"] for p in fs["photos"]] == ["P1", "P2"]
        assert [p["source_label"] for p in fs["photos"]] == ["SOURCE_01", "SOURCE_02"]
        assert [p["after_label"] for p in fs["photos"]] == ["AFTER_01", "AFTER_02"]
        assert fs["photos"][0]["photo_id"] == "aaaaaaaaaaaaaaaaaaaaaaaa"
        assert fs["photos"][1]["shot"] == "detail"

    def test_keep_items_get_ids(self):
        fs = build_fact_sheet(self._lead())
        assert [k["id"] for k in fs["keep"]["items"]] == ["K1", "K2"]
        assert fs["keep"]["items"][1]["text"] == "round 5 ft rug"

    def test_measurements_get_ids_and_mode(self):
        fs = build_fact_sheet(
            self._lead(
                priority="better_layout",
                limits=["none"],
                measure_mode="provided",
                measurements={"unit": "ft", "width": 10, "length": 12, "fixed": "door left wall", "items": ""},
            )
        )
        assert [m["id"] for m in fs["measurements"]] == ["M1", "M2", "M3"]
        assert fs["room_flow"]["mode"] == "measured"
        assert "Room dimensions" not in " ".join(fs["unknowns"])

    def test_unknowns_recorded_not_guessed(self):
        fs = build_fact_sheet(self._lead(coverage="partial", budget="not_sure"))
        text = " ".join(fs["unknowns"])
        assert "not confirmed" in text
        assert "outside the photos" in text
        assert "Budget not set" in text

    def test_conceptual_sheet(self):
        lead = {
            "id": "c1",
            "package_id": "free",
            "photos": [],
            "intake": _intake(plan="free", photo_mode="conceptual", photos=[], coverage=""),
        }
        fs = build_fact_sheet(lead)
        assert fs["conceptual"] is True
        assert fs["room_flow"]["mode"] == "conceptual"
        assert "CONCEPTUAL PLAN" in fact_sheet_prompt(fs)

    def test_prompt_carries_ids_and_limits(self):
        prompt = fact_sheet_prompt(build_fact_sheet(self._lead(limits=["no_drilling", "other"], limit_other="rental")))
        assert "P1 (Photo 1 — Crib wall, wide)" in prompt
        assert "K1 six-drawer dresser" in prompt
        assert "No drilling, Other: rental" in prompt
        assert "not to scale" in prompt

    def test_drafter_summary_includes_fact_sheet(self):
        from ai_drafter import _summarize_lead

        lead = self._lead()
        lead["fact_sheet"] = build_fact_sheet(lead)
        summary = _summarize_lead(lead)
        assert "PROJECT FACT SHEET" in summary
        assert "K2 round 5 ft rug" in summary

    def test_legacy_lead_has_no_fact_sheet_prompt(self):
        assert fact_sheet_prompt(None) == ""


# ──────────────────────────── API ─────────────────────────────
@pytest.fixture
def api_client(monkeypatch):
    from fastapi.testclient import TestClient

    import server

    fake = FakeDB()
    monkeypatch.setattr(server, "db", fake)

    async def no_automation(*args, **kwargs):
        return True

    async def no_seed():
        return None

    monkeypatch.setattr(server, "_start_automation_for_lead", no_automation)
    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as c:
        token = _signup(c).json()["token"]
        yield c, fake, {"Authorization": f"Bearer {token}"}


def _payload(intake=None, **over):
    body = {
        "name": "Camila",
        "email": "camila@example.com",
        "space_type": "kids_room",
        "package_id": "plus",
        "photos": [P1],
        "language": "en",
        "intake": intake if intake is not None else _intake(),
    }
    body.update(over)
    return body


class TestLeadApi:
    def test_valid_intake_creates_lead_with_fact_sheet(self, api_client):
        c, fake, headers = api_client
        r = c.post("/api/leads", json=_payload(), headers=headers)
        assert r.status_code == 200, r.text
        stored = fake.leads.docs[-1]
        assert stored["fact_sheet"]["photos"][0]["id"] == "P1"
        assert stored["intake"]["version"] == INTAKE_VERSION

    def test_paid_intake_without_photo_is_photo_required(self, api_client):
        c, _fake, headers = api_client
        r = c.post("/api/leads", json=_payload(intake=_intake(photos=[]), photos=[]), headers=headers)
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "PHOTO_REQUIRED"

    def test_invalid_answers_are_field_errors(self, api_client):
        c, _fake, headers = api_client
        r = c.post("/api/leads", json=_payload(intake=_intake(limits=["none", "no_drilling"])), headers=headers)
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["code"] == "INTAKE_INVALID"
        assert any(e["field"] == "limits" for e in detail["errors"])

    def test_photo_cap_enforced_without_intake(self, api_client):
        c, _fake, headers = api_client
        body = _payload(package_id="free", photos=[P1, P2, P1 + "x"])
        body.pop("intake")
        r = c.post("/api/leads", json=body, headers=headers)
        assert r.status_code == 422

    def test_checkout_refuses_lead_without_photo(self, api_client, monkeypatch):
        c, fake, headers = api_client
        import server

        monkeypatch.setattr(server, "STRIPE_API_KEY", "sk_test_dummy")
        fake.leads.docs.append({"id": "legacy-1", "package_id": "plus", "photos": [], "email": "camila@example.com"})
        r = c.post(
            "/api/checkout/session",
            json={"package_id": "plus", "origin_url": "http://localhost:3000", "metadata": {"lead_id": "legacy-1"}},
            headers=headers,
        )
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "PHOTO_REQUIRED"

    def test_checkout_unknown_lead_404(self, api_client):
        c, _fake, headers = api_client
        r = c.post(
            "/api/checkout/session",
            json={"package_id": "plus", "origin_url": "http://localhost:3000", "metadata": {"lead_id": "nope"}},
            headers=headers,
        )
        assert r.status_code == 404


def test_conceptual_intake_lead_is_held_for_review(monkeypatch):
    from tests.test_automation import _run, _lead

    lead = _lead()
    lead["intake"] = _intake(plan="free", photo_mode="conceptual", photos=[], coverage="")
    lead["fact_sheet"] = build_fact_sheet({**lead, "photos": []})
    sent, captured, db, _fs = _run(monkeypatch, generate=lambda **k: (None, None), lead=copy.deepcopy(lead))
    stored = db.leads.docs[lead["id"]]
    assert stored["status"] == "review"
    assert stored["email_sent"] is False
    assert not captured.get("send_calls")
    assert db.deliverables.docs[lead["id"]]["fact_sheet"]["conceptual"] is True
