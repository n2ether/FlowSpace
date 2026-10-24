"""One room inventory drives every view and document; mismatches block instead of shipping.

Regression cases from the rejected Living Room Version 2: the TV console must
keep its glass doors in every view, the shoe bench stays without baskets, no
basket on Sam's bed, the artwork, playpen, and wall color stay, the open budget
reaches every surface, and a view that drifts from the others is caught by the
system (not fixed by hand). Image edits and vision checks are mocked; the
pipeline, prompts, documents, and the consistency report run for real.
"""
import asyncio
import os
from typing import Any, Dict, List

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "flowspace_inventory_test")

from render_qa import CrossViewResult, RenderQAResult  # noqa: E402
from tests.test_automation import _FakeDB, _FakeFS, _jpeg  # noqa: E402

V3_BRIEF = (
    "Keep the TV console's exact structure and original glass doors in every angle. "
    "Preserve the existing shoe bench without baskets, keep shoes directly accessible, and leave the seat usable. "
    "Remove any basket placed on Sam's bed. "
    "Retain the original artwork above that bed, the playpen, existing wall color, and the other furniture identified in the brief. "
    "Add a larger artwork on the dining wall that connects visually to the kitchen, a living area rug, warmth and texture, "
    "and a well styled dining table. Open budget, no cap."
)

PLAN = {
    "intro": "A living and dining room that works for everyday life and for guests.",
    "zones": [
        {"title": "Living", "desc": "Sofa with chaise facing the TV console."},
        {"title": "Dining", "desc": "Folding table for two that opens to four."},
        {"title": "Entry", "desc": "Shoe bench by the door."},
    ],
    "needs": ["A clear path from the door to the dining table"],
    "strategy": [
        "Lay a living area rug under the coffee table.",
        "Hang a larger artwork on the dining wall facing the kitchen.",
        "Add warm textured throws to the sofa.",
        "Set the dining table with placemats and a runner.",
    ],
    "action_plan": ["Measure the dining wall before buying the artwork."],
    "fixed_items": [
        {"name": "TV console", "details": "low wood console"},
        {"name": "Shoe bench", "details": "entry bench with an open shoe shelf under the seat"},
    ],
    "additions": [
        {"name": "Large framed abstract print", "placement": "dining wall facing the kitchen"},
        {"name": "Round jute area rug", "placement": "under the coffee table"},
    ],
    "shopping_list": [
        {"name": "Large framed abstract print", "qty": 1, "price": 180},
        {"name": "Round jute area rug", "qty": 1, "price": 220},
        {"name": "Linen throw pillow covers", "qty": 2, "price": 24},
        {"name": "Linen placemats and table runner", "qty": 1, "price": 40},
    ],
}

PHOTO_IDS = [f"{i:024x}" for i in range(1, 4)]


def _living_lead(**extra) -> Dict[str, Any]:
    lead = {
        "id": "lead-v3-living",
        "name": "Camila Sales",
        "email": "camila@example.com",
        "space_type": "living_room",
        "budget": "100_300",
        "photos": [f"/api/uploads/photo/{key}" for key in PHOTO_IDS],
        "brief": {"notes": V3_BRIEF},
    }
    lead.update(extra)
    return lead


def _good_qa(**kwargs) -> RenderQAResult:
    return RenderQAResult(
        ok=True,
        visible_additions=list(kwargs.get("additions") or []),
        unlisted_additions=[],
        fixed_items_altered=[],
        fixed_items_missing=[],
        avoid_seen=[],
    )


def _pipeline(monkeypatch, *, qa, cross, lead=None, plan=None):
    """Run the real pipeline with mocked drafting, image edits, and vision calls."""
    from automation import run_automation

    sources = {key: _jpeg((40 * i, 90, 60)) for i, key in enumerate(PHOTO_IDS, start=1)}
    lead = lead or _living_lead()
    generated: List[Dict[str, Any]] = []

    async def draft(_lead, **_kwargs):
        from blueprint_consistency import prepare_deliverable

        return prepare_deliverable(_lead, dict(plan or PLAN))

    async def generate(**kwargs):
        generated.append(kwargs)
        return _jpeg((200, (17 * len(generated)) % 255, 30)), "image/jpeg"

    monkeypatch.setattr("automation.draft_deliverable", draft)
    monkeypatch.setattr("automation.generate_front_view", generate)
    monkeypatch.setattr("automation.review_organized_render", qa)
    monkeypatch.setattr("automation.review_cross_view", cross)
    db = _FakeDB()
    db.leads.docs[lead["id"]] = dict(lead)
    held = asyncio.run(run_automation(lead=lead, db=db, fs_bucket=_FakeFS(store=dict(sources))))
    doc = db.deliverables.docs[lead["id"]]
    return held, doc, generated, sources, db


def _codes(report, severity="block"):
    return [i["code"] for i in report["issues"] if i["severity"] == severity]


# ──────────────────────────── The brief becomes the inventory ─────────────────────────────


def test_v3_brief_becomes_retained_pieces_avoid_rules_and_changes():
    from package_items import avoid_rules, brief_requests, fixed_items, keep_existing_items, room_inventory

    lead = _living_lead()
    kept = {row["name"]: row["details"] for row in keep_existing_items(lead)}
    assert kept["TV console"] == "exact structure and original glass doors"
    assert kept["shoe bench"] == "without baskets"
    assert "artwork above that bed" in kept and "playpen" in kept
    assert not any("wall" in name or "furniture" in name for name in kept)
    assert avoid_rules(lead) == ["basket on Sam's bed", "baskets on or under the shoe bench"]
    assert [d["kind"] for d in brief_requests(lead)["decor"]] == ["art", "rug", "cozy", "table_setting"]

    # The photo read ("low wood console") and the brief's glass doors are locked together.
    console = next(row for row in fixed_items(lead, PLAN) if row["name"] == "TV console")
    assert "low wood console" in console["details"] and "original glass doors" in console["details"]

    inventory = room_inventory(lead, PLAN)
    assert {r["name"] for r in inventory["retained"]} >= {"TV console", "Shoe bench", "artwork above that bed", "playpen"}
    assert {c["kind"] for c in inventory["changes"]} >= {"art", "rug", "cozy", "table_setting"}
    assert inventory["walls"] == {"keep": True, "paint": ""}
    assert inventory["budget"] == {"id": "open", "label": "Open budget (no cap)", "open": True}


def test_customer_sentences_that_are_not_kept_pieces_stay_out():
    from package_items import keep_existing_items

    lead = {"goals": "Keep shoes directly accessible. Keep everything tidy and move the table to the window. Keep all current furniture."}
    assert keep_existing_items(lead) == []


def test_every_view_prompt_carries_the_same_locks_and_never_show_rules():
    from ai_image_generator import _build_edit_prompt, _supporting_prompt
    from package_items import brief_prompt_lines

    lead = _living_lead()
    for prompt in (_build_edit_prompt(lead, PLAN), _supporting_prompt(lead, PLAN, "Focus on the TV wall.")):
        assert "TV console — low wood console; brief: exact structure and original glass doors" in prompt
        assert "playpen" in prompt and "artwork above that bed" in prompt
        assert "NEVER SHOW, IN ANY VIEW: basket on Sam's bed; baskets on or under the shoe bench." in prompt
        assert "never remove, hide, or crop out a fixed piece" in prompt
        assert "WALL PAINT LOCK" in prompt
    lines = brief_prompt_lines(lead)
    assert any(line.startswith("KEEP EXISTING — the customer's existing TV console (exact structure and original glass doors)") for line in lines)
    assert "NEVER SHOW — basket on Sam's bed. Do not plan, buy, or describe it." in lines


# ──────────────────────────── Per-view check, per piece ─────────────────────────────


def test_qa_reports_which_piece_changed_or_disappeared_and_what_it_should_not_show():
    from render_qa import _from_payload, qa_prompt

    prompt = qa_prompt(fixed_items=["TV console (two glass doors)"], additions=["Area rug"], avoid=["basket on Sam's bed"])
    assert "fixed_items_check" in prompt and "NEVER SHOW: basket on Sam's bed" in prompt
    result = _from_payload(
        {
            "ok": True,
            "fixed_items_check": [
                {"name": "TV console (two glass doors)", "in_before": True, "in_after": True, "same": False},
                {"name": "artwork above that bed", "in_before": True, "in_after": False, "same": False},
                {"name": "playpen", "in_before": False, "in_after": False, "same": True},
            ],
            "avoid_seen": ["basket on Sam's bed"],
            "visible_additions": [],
        }
    )
    assert result.failed and result.fixed_items_changed
    assert result.fixed_items_altered == ["TV console (two glass doors)"]
    assert result.fixed_items_missing == ["artwork above that bed"]
    assert result.avoid_seen == ["basket on Sam's bed"]


def test_a_view_that_turns_the_glass_doors_into_shelves_is_retried_with_the_piece_named(monkeypatch):
    calls: List[Dict[str, Any]] = []

    def qa(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:  # AFTER_02, first attempt
            return RenderQAResult(
                ok=False,
                fixed_items_changed=True,
                fixed_items_altered=["TV console"],
                visible_additions=[],
                unlisted_additions=[],
            )
        return _good_qa(**kwargs)

    held, doc, generated, _sources, _db = _pipeline(monkeypatch, qa=qa, cross=lambda **_k: CrossViewResult(ok=True))
    assert held is True and len(generated) == 4
    retry = generated[2]
    assert retry["stronger_rails"] is True
    assert "These pieces changed and must match the source photo exactly: TV console." in retry["extra_constraint"]
    assert [row["status"] for row in doc["source_afters"]] == ["approved"] * 3
    for kwargs in calls:
        assert any("original glass doors" in name for name in kwargs["fixed_items"])
        assert kwargs["avoid"] == ["basket on Sam's bed", "baskets on or under the shoe bench"]


def test_a_basket_on_sams_bed_in_both_attempts_drops_the_view_and_holds_the_package(monkeypatch):
    def qa(**kwargs):
        if kwargs["before_bytes"] == sources_ref["third"]:
            return RenderQAResult(ok=False, avoid_seen=["basket on Sam's bed"], visible_additions=[], unlisted_additions=[])
        return _good_qa(**kwargs)

    sources_ref = {"third": _jpeg((120, 90, 60))}
    held, doc, generated, _sources, db = _pipeline(monkeypatch, qa=qa, cross=lambda **_k: CrossViewResult(ok=True))
    assert held is False
    assert [row["status"] for row in doc["source_afters"]] == ["approved", "approved", "failed"]
    assert "Remove it." in generated[3]["extra_constraint"] and "basket on Sam's bed" in generated[3]["extra_constraint"]
    assert db.leads.docs["lead-v3-living"]["package_status"] == "incomplete"
    from source_photos import final_email_block_reason

    assert final_email_block_reason(doc)


# ──────────────────────────── Views compared with each other ─────────────────────────────


def test_a_view_that_drifts_from_the_others_is_re_edited_against_the_reference(monkeypatch):
    rounds: List[Dict[str, Any]] = []

    def cross(**kwargs):
        rounds.append(kwargs)
        if len(rounds) == 1:
            return CrossViewResult(
                ok=False,
                mismatches=[
                    {
                        "name": "TV console",
                        "views": ["AFTER_01", "AFTER_03"],
                        "consistent": False,
                        "difference": "open shelves instead of glass doors",
                    }
                ],
            )
        return CrossViewResult(ok=True)

    held, doc, generated, sources, _db = _pipeline(monkeypatch, qa=_good_qa, cross=cross)
    assert held is True and len(rounds) == 2 and len(generated) == 4
    repair = generated[3]
    assert repair["reference_photo_bytes"] == sources[PHOTO_IDS[2]]
    first_after = rounds[0]["views"][0][1]
    assert repair["consistency_reference"] == first_after
    assert "FAILED CROSS-VIEW CHECK" in repair["extra_constraint"]
    assert "TV console (open shelves instead of glass doors)" in repair["extra_constraint"]
    assert [label for label, _ in rounds[0]["views"]] == ["AFTER_01", "AFTER_02", "AFTER_03"]
    assert any("original glass doors" in name for name in rounds[0]["fixed_items"])

    assert doc["cross_view"]["ok"] is True and doc["cross_view"]["repaired"] == ["AFTER_03"]
    third = doc["source_afters"][2]
    assert third["qa"]["checked_after_url"] == third["after_url"]
    assert doc["cross_view"]["after_urls"][2] == third["after_url"]
    assert doc["room_inventory"]["hash"] == third["qa"]["inventory_hash"]
    codes = _codes(doc["consistency"])
    for code in ("cross_view_mismatch", "cross_view_not_verified", "cross_view_stale", "view_not_verified", "view_inventory_stale"):
        assert code not in codes


def test_a_drift_the_repair_cannot_fix_blocks_and_cannot_be_overridden(monkeypatch):
    import importlib

    importlib.import_module("server")  # its Mongo client needs a live event loop at import

    mismatch = {"name": "TV console", "views": ["AFTER_01", "AFTER_02"], "consistent": False, "difference": "solid doors"}
    held, doc, _generated, _sources, _db = _pipeline(
        monkeypatch, qa=_good_qa, cross=lambda **_k: CrossViewResult(ok=False, mismatches=[mismatch])
    )
    assert held is True
    report = doc["consistency"]
    blocking = [i for i in report["issues"] if i["code"] == "cross_view_mismatch"]
    assert blocking and "TV console does not look the same across AFTER_01, AFTER_02: solid doors." == blocking[0]["message"]

    from fastapi import HTTPException
    from tests.test_review_system_rules import LIVING_ID, _final_server

    server, saved, sends = _final_server(monkeypatch, report)

    class _Request:
        query_params: dict = {}

    with pytest.raises(HTTPException) as err:
        asyncio.run(
            server.send_final_package(
                LIVING_ID,
                _Request(),
                override_consistency=True,
                override_reason="Looks close enough to me, send it.",
                _=True,
            )
        )
    assert err.value.status_code == 409 and "cannot be overridden" in err.value.detail
    assert not sends and "consistency_override" not in saved


def test_when_vision_checks_are_unavailable_views_are_unverified_not_passed(monkeypatch):
    held, doc, _generated, _sources, _db = _pipeline(
        monkeypatch,
        qa=lambda **_k: RenderQAResult(ok=True, skipped=True, error="no_api_key"),
        cross=lambda **_k: CrossViewResult(ok=True, skipped=True, error="no_api_key"),
    )
    assert held is True
    codes = _codes(doc["consistency"])
    assert codes.count("view_not_verified") == 3
    assert "cross_view_not_verified" in codes
    from package_items import final_send_block_reason

    assert final_send_block_reason(doc["consistency"])


# ──────────────────────────── Drift after generation ─────────────────────────────


def _verified_package(lead):
    from package_items import room_inventory

    inventory = room_inventory(lead, PLAN)
    entries = []
    for n in range(1, 4):
        url = f"/api/uploads/photo/{'a' * 23}{n}"
        entries.append(
            {
                "source_photo_id": PHOTO_IDS[n - 1],
                "source_url": f"/api/uploads/photo/{PHOTO_IDS[n - 1]}",
                "label": f"SOURCE_0{n}",
                "after_label": f"AFTER_0{n}",
                "after_url": url,
                "status": "approved",
                "edit_kind": "own_source",
                "derived_from_photo_id": PHOTO_IDS[n - 1],
                "qa": {
                    **_good_qa(additions=[c["name"] for c in inventory["changes"]]).as_dict(),
                    "inventory_hash": inventory["hash"],
                    "checked_after_url": url,
                },
            }
        )
    return {
        **PLAN,
        "lead_id": lead["id"],
        "source_afters": entries,
        "required_source_ids": list(PHOTO_IDS),
        "package_status": "review",
        "room_inventory": inventory,
        "cross_view": {
            "ok": True,
            "skipped": False,
            "error": None,
            "items": [],
            "mismatches": [],
            "inventory_hash": inventory["hash"],
            "after_urls": [e["after_url"] for e in entries],
            "repaired": [],
        },
    }


def test_a_brief_change_after_generation_marks_every_view_stale():
    from package_items import consistency_report

    lead = _living_lead()
    package = _verified_package(lead)
    codes = _codes(consistency_report(lead, package))
    assert "view_inventory_stale" not in codes and "cross_view_stale" not in codes

    lead["brief"]["notes"] += " No basket on the chaise."
    codes = _codes(consistency_report(lead, package))
    assert codes.count("view_inventory_stale") == 3 and "cross_view_stale" in codes


def test_an_after_swapped_after_its_check_is_flagged():
    from package_items import consistency_report

    lead = _living_lead()
    package = _verified_package(lead)
    package["source_afters"][1]["after_url"] = "/api/uploads/photo/" + "f" * 24
    codes = _codes(consistency_report(lead, package))
    assert "view_changed_after_check" in codes and "cross_view_stale" in codes


def test_a_kept_piece_missing_from_a_view_blocks_by_name():
    from package_items import consistency_report

    lead = _living_lead()
    package = _verified_package(lead)
    package["source_afters"][2]["qa"]["fixed_items_missing"] = ["playpen"]
    issues = consistency_report(lead, package)["issues"]
    missing = [i for i in issues if i["code"] == "fixed_item_missing"]
    assert missing and missing[0]["message"] == "AFTER_03: playpen is missing from the organized view."


def test_brief_update_rebuilds_the_record_and_verify_clears_stale_views(monkeypatch):
    from fastapi.testclient import TestClient

    import server
    from tests.test_member_auth import FakeDB

    lead = _living_lead(intake={"budget": "100_300", "space_type": "living_room"})
    lead["fact_sheet"] = server.build_fact_sheet({**lead, "brief": {}})
    assert lead["fact_sheet"]["budget"]["id"] == "100_300"
    fake = FakeDB()
    fake.leads.docs.append(dict(lead))
    fake.deliverables.docs.append(_verified_package(lead))
    monkeypatch.setattr(server, "db", fake)

    async def no_seed():
        return None

    async def resolve(url, _request):
        return _jpeg((10, 20, 30)) if url else None

    checks: List[Dict[str, Any]] = []

    def verify_qa(**kwargs):
        checks.append(kwargs)
        return _good_qa(**kwargs)

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    monkeypatch.setattr(server, "_resolve_image_bytes", resolve)
    monkeypatch.setattr("view_verification.review_organized_render", verify_qa)
    monkeypatch.setattr("view_verification.review_cross_view", lambda **_k: CrossViewResult(ok=True))
    headers = {"X-Admin-Token": server.ADMIN_PASSWORD}
    with TestClient(server.app) as client:
        brief = client.put(
            f"/api/admin/leads/{lead['id']}/brief",
            json={"notes": V3_BRIEF, "budget": "open", "avoid": ["basket on the chaise"]},
            headers=headers,
        )
        assert brief.status_code == 200, brief.text
        assert brief.json()["views_need_verification"] is True
        saved = fake.leads.docs[0]
        assert saved["budget"] == "open" and saved["fact_sheet"]["budget"]["id"] == "open"

        stale = client.get(f"/api/admin/leads/{lead['id']}/deliverable/consistency", headers=headers).json()
        assert "view_inventory_stale" in _codes(stale)

        anon = client.post(f"/api/admin/leads/{lead['id']}/deliverable/verify")
        assert anon.status_code in (401, 403)
        verified = client.post(f"/api/admin/leads/{lead['id']}/deliverable/verify", headers=headers)
        assert verified.status_code == 200, verified.text
        body = verified.json()
    assert len(checks) == 3 and all("basket on the chaise" in kwargs["avoid"] for kwargs in checks)
    codes = _codes(body)
    for code in ("view_inventory_stale", "cross_view_stale", "view_not_verified", "view_changed_after_check"):
        assert code not in codes
    assert body["emailed"] is False


# ──────────────────────────── Text and documents agree ─────────────────────────────


def test_plan_text_that_promises_a_change_needs_it_in_the_item_list():
    from package_items import consistency_report

    lead = {"id": "x", "space_type": "living_room"}
    plan = {"strategy": ["Hang a round mirror above the console to bounce light."]}
    issues = consistency_report(lead, plan)["issues"]
    assert any(i["code"] == "change_not_in_inventory" and "mirror" in i["message"] for i in issues)
    plan["shopping_list"] = [{"name": "Round wall mirror", "qty": 1, "price": 90}]
    issues = consistency_report(lead, plan)["issues"]
    assert not any(i["code"] == "change_not_in_inventory" for i in issues)


def test_open_budget_from_the_brief_reaches_every_surface():
    from ai_drafter import _summarize_lead
    from blueprint_consistency import prepare_deliverable
    from blueprint_layers import _band_status
    from intake import build_fact_sheet
    from pdf_generator import _budget_range

    lead = _living_lead(intake={"budget": "100_300"})
    assert "Budget: Open budget (no cap)" in _summarize_lead(lead)
    assert "$100" not in _summarize_lead(lead).split("Budget:")[1].splitlines()[0]
    assert build_fact_sheet(lead)["budget"] == {"id": "open", "label": "Open budget (no cap)"}
    assert prepare_deliverable(lead, PLAN)["stated_budget"] == "Open budget (no cap)"
    assert _band_status(lead, 500)[1] == "Kit totals $500. The budget is open, with no cap."
    assert _budget_range(lead, {}, {}) == "Open budget (no cap)"


def test_a_document_that_still_states_the_old_band_blocks():
    from package_items import consistency_report

    lead = _living_lead()
    report = consistency_report(lead, PLAN, texts={"Companion Guide": "Your budget: $100 – $300.", "Design Plan": "Open budget (no cap)"})
    flagged = [i for i in report["issues"] if i["code"] == "budget_mismatch"]
    assert len(flagged) == 1 and flagged[0]["surface"] == "Companion Guide"


def test_customer_text_mentioning_no_limit_does_not_open_the_budget():
    from package_items import effective_budget

    assert effective_budget({"budget": "100_300", "goals": "There is no limit to how many toys we own."}) == "100_300"


def test_real_documents_for_the_v3_brief_state_one_budget(monkeypatch):
    from package_items import consistency_report, customer_texts
    from pdf_generator import build_pdf

    lead = _living_lead()
    pdf = build_pdf(lead=lead, deliverable=PLAN, images={})
    texts = customer_texts(lead, PLAN, {}, companion_pdf=pdf)
    assert set(texts) == {"Design Plan", "Room Flow", "Companion Guide"}
    report = consistency_report(lead, PLAN, texts=texts)
    assert not [i for i in report["issues"] if i["code"] == "budget_mismatch"]


# ──────────────────────────── Override for customer sends ─────────────────────────────


def test_override_needs_a_written_reason_and_is_logged(monkeypatch, caplog):
    from fastapi import HTTPException
    from tests.test_review_system_rules import LIVING_ID, _final_server

    report = {"issues": [{"code": "product_link_not_direct", "severity": "block", "message": "Rug has no tested direct product link yet."}]}
    server, saved, sends = _final_server(monkeypatch, report)

    class _Request:
        query_params: dict = {}

    with pytest.raises(HTTPException) as err:
        asyncio.run(server.send_final_package(LIVING_ID, _Request(), override_consistency=True, override_reason="ok", _=True))
    assert err.value.status_code == 422 and not sends
    with caplog.at_level("WARNING"):
        out = asyncio.run(
            server.send_final_package(
                LIVING_ID,
                _Request(),
                override_consistency=True,
                override_reason="Retailer page is down; search link approved by Camila.",
                _=True,
            )
        )
    assert out["final"] is True and len(sends) == 1
    record = saved["consistency_override"]
    assert record["override_reason"] == "Retailer page is down; search link approved by Camila."
    assert record["issues"] == [{"code": "product_link_not_direct", "message": "Rug has no tested direct product link yet."}]
    assert saved["consistency_override_log"] == [record]
    assert any("Consistency override on final send" in r.getMessage() for r in caplog.records)


def test_override_is_admin_only(monkeypatch):
    from fastapi.testclient import TestClient

    import server
    from tests.test_member_auth import FakeDB

    fake = FakeDB()
    fake.leads.docs.append({"id": "lead-x", "email": "c@example.com"})
    monkeypatch.setattr(server, "db", fake)

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as client:
        r = client.post(
            "/api/admin/leads/lead-x/deliverable/send-final?override_consistency=true&override_reason=please+send+it+now"
        )
    assert r.status_code in (401, 403)
