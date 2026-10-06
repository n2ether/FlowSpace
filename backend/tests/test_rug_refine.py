"""One round rug in every after: prompt rails, the refine pass, and the admin endpoint."""
import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ai_image_generator import _build_edit_prompt, _build_text_to_image_prompt, _supporting_prompt
from render_qa import RenderQAResult
from rug_refine import RugCheckResult, build_refine_prompt, refine_one, resolve_refine_rug
from space_rails import RUG_PRESERVE_RAILS, customer_requested_rug_change, rug_prompt_rails, rug_spec

LEAD_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"
LEAD = {
    "id": LEAD_ID,
    "name": "Camila Sales",
    "email": "camila@example.com",
    "space_type": "kids_room",
    "goals": "Keep the space theme and make the nursery safer and calmer.",
    "must_stay": "Six-drawer dresser, crib, rocker, space-themed wall decor",
}
RUG = {"color": "warm cream with a soft gray border", "texture": "low flat pile", "pattern": "solid center, thin gray ring near the edge"}


def _jpeg(color, size=(320, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_nursery_plan_carries_a_structured_round_rug():
    spec = rug_spec(LEAD, {})
    assert spec["shape"] == "round"
    assert spec["diameter_ft"] == 5
    assert spec["diameter_m"] == 1.5


def test_every_after_prompt_locks_the_existing_rug():
    for prompt in (
        _build_edit_prompt(LEAD, {}),
        _build_text_to_image_prompt(LEAD, {}),
        _supporting_prompt(LEAD, {}, "Focal point: the rocker."),
    ):
        assert RUG_PRESERVE_RAILS in prompt
        assert "single round rug, about 5 ft (1.5 m) across" in prompt
        assert "every view" in prompt


def test_rug_rail_is_general_and_follows_the_plan_spec():
    garage = {"space_type": "garage", "goals": "Park the car again."}
    assert rug_prompt_rails(garage, {}) == RUG_PRESERVE_RAILS
    assert RUG_PRESERVE_RAILS in _build_edit_prompt(garage, {})
    described = rug_prompt_rails(LEAD, {"rug": RUG})
    for value in RUG.values():
        assert value in described


def test_rug_rail_steps_aside_when_the_customer_asked_for_a_new_rug():
    lead = {**LEAD, "goals": "We want to replace the rug with something bigger."}
    assert customer_requested_rug_change(lead)
    assert rug_prompt_rails(lead, {}) == ""
    assert RUG_PRESERVE_RAILS not in _build_edit_prompt(lead, {})
    assert not customer_requested_rug_change(LEAD)


def test_refine_prompt_changes_only_the_rug():
    rug = resolve_refine_rug(LEAD, {}, RUG)
    prompt = build_refine_prompt(LEAD, {"strategy": ["Keep the space theme with planets."]}, rug, has_reference=True)
    low = prompt.lower()
    assert "rug only" in low
    assert "single round rug, about 5 ft (1.5 m) across, warm cream with a soft gray border" in prompt
    for kept in (
        "six-drawer dresser keeps all six drawers",
        "fitted sheet only",
        "rocker",
        "basket",
        "wall color",
        "windows",
        "space-themed decor",
        "orientation",
        "framing",
        "image 2 is a reference for the rug only",
    ):
        assert kept in low, kept


def _qa(ok=True, skipped=False, reasons=None):
    def run(*, after_bytes, before_bytes=None, attempt=1):
        return RenderQAResult(ok=ok, skipped=skipped, reasons=list(reasons or []), attempt=attempt)

    return run


def _rug_check(ok=True, skipped=False):
    def run(*, refined, previous, rug):
        return RugCheckResult(ok=ok, rug_matches=ok, skipped=skipped, reasons=[] if ok else ["rug is oval"])

    return run


def _refine(**kwargs):
    calls = []

    async def edit(prompt, after, reference):
        calls.append({"prompt": prompt, "after": after, "reference": reference})
        return _jpeg((10 * len(calls), 120, 90))

    outcome = asyncio.run(
        refine_one(
            lead=LEAD,
            deliverable={},
            rug=resolve_refine_rug(LEAD, {}, RUG),
            label="SOURCE_02",
            after_label="AFTER_02",
            source=_jpeg((1, 2, 3)),
            after=_jpeg((4, 5, 6)),
            reference=_jpeg((7, 8, 9)),
            edit=edit,
            **kwargs,
        )
    )
    return outcome, calls


def test_refined_after_replaces_only_when_both_checks_pass():
    outcome, calls = _refine(qa=_qa(), rug_check=_rug_check())
    assert outcome.replaced and outcome.after_bytes
    assert len(calls) == 1 and calls[0]["reference"] is not None

    outcome, calls = _refine(qa=_qa(ok=False, reasons=["window covered"]), rug_check=_rug_check())
    assert not outcome.replaced and outcome.after_bytes is None
    assert len(calls) == 2
    assert "window covered" in calls[1]["prompt"]

    outcome, _calls = _refine(qa=_qa(), rug_check=_rug_check(ok=False))
    assert not outcome.replaced


def test_skipped_vision_review_keeps_the_existing_after():
    outcome, _calls = _refine(qa=_qa(skipped=True), rug_check=_rug_check())
    assert not outcome.replaced
    outcome, _calls = _refine(qa=_qa(), rug_check=_rug_check(skipped=True))
    assert not outcome.replaced


# ──────────────────────────── Endpoint ─────────────────────────────


class _FakeBucket:
    def __init__(self):
        self.files = {}

    async def upload_from_stream(self, filename, source, metadata=None):
        from bson import ObjectId

        oid = ObjectId()
        data = source.read() if hasattr(source, "read") else bytes(source)
        self.files[str(oid)] = {"filename": filename, "data": data, "metadata": metadata or {}}
        return oid


def _deliverable():
    entries = []
    for n in range(1, 5):
        entries.append(
            {
                "source_photo_id": f"src{n}",
                "source_url": f"/api/uploads/photo/src{n}",
                "label": f"SOURCE_{n:02d}",
                "after_label": f"AFTER_{n:02d}",
                "after_url": f"/api/uploads/photo/after{n}",
                "status": "approved",
                "kind": "room",
                "edit_kind": "own_source",
                "derived_from_photo_id": f"src{n}",
                "qa": {},
            }
        )
    return {
        "lead_id": LEAD_ID,
        "source_afters": entries,
        "required_source_ids": [f"src{n}" for n in range(1, 5)],
        "front_view_url": "/api/uploads/photo/after1",
        "package_status": "review",
        "shopping_list": [],
    }


@pytest.fixture
def api(monkeypatch):
    import server
    from tests.test_member_auth import FakeDB

    fake = FakeDB()
    fake.leads.docs.append({**LEAD, "status": "review", "package_status": "review"})
    fake.deliverables.docs.append(_deliverable())
    bucket = _FakeBucket()
    images = {f"/api/uploads/photo/{key}": _jpeg((n * 20, 90, 60)) for n, key in enumerate(
        ["src1", "src2", "src3", "src4", "after1", "after2", "after3", "after4"]
    )}

    async def resolve(url, _request):
        if url in images:
            return images[url]
        file_id = str(url or "").rsplit("/", 1)[-1]
        stored = bucket.files.get(file_id)
        return stored["data"] if stored else None

    edits = []

    async def edit(prompt, after, reference=None):
        edits.append({"prompt": prompt, "after": after, "reference": reference})
        return _jpeg((200, 10 * len(edits), 30))

    def qa(*, after_bytes, before_bytes=None, attempt=1):
        # AFTER_03's refined view fails QA both times; every other view passes.
        failing = images["/api/uploads/photo/after3"]
        return RenderQAResult(ok=edits[-1]["after"] != failing, reasons=["wall repainted"], attempt=attempt)

    def no_email(*_args, **_kwargs):
        raise AssertionError("refine must not send email")

    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "fs_bucket", bucket)
    monkeypatch.setattr(server, "_resolve_image_bytes", resolve)
    monkeypatch.setattr(server, "refine_after_image", edit)
    monkeypatch.setattr(server, "describe_rug", lambda sources, after, base: {**base, **RUG})
    monkeypatch.setattr(server, "send_blueprint", no_email)
    monkeypatch.setattr(server, "send_draft_package", no_email)
    monkeypatch.setattr(server, "send_contact_sheet", no_email)
    monkeypatch.setattr("rug_refine.review_organized_render", qa)
    monkeypatch.setattr("rug_refine.review_rug_edit", lambda **_kw: RugCheckResult(ok=True))

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as client:
        yield client, fake, bucket, edits, server.ADMIN_PASSWORD


def test_refine_requires_the_admin_token(api):
    client, _fake, _bucket, edits, _token = api
    assert client.post(f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine?wait=true").status_code == 401
    assert client.post(
        f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine?wait=true", headers={"X-Admin-Token": "nope"}
    ).status_code == 401
    assert edits == []


def test_refine_replaces_passing_afters_and_keeps_every_mapping(api):
    client, fake, bucket, edits, token = api
    before = _deliverable()
    res = client.post(
        f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine?wait=true",
        headers={"X-Admin-Token": token},
        json={"rug": {"placement": "centered between the crib and the dresser"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["emailed"] is False
    assert body["package_status"] == "review"
    assert body["replaced"] == 3
    assert [row["replaced"] for row in body["views"]] == [True, True, False, True]
    assert body["rug"]["shape"] == "round" and body["rug"]["diameter_ft"] == 5
    assert body["rug"]["placement"] == "centered between the crib and the dresser"

    # AFTER_01 is edited alone; every other view gets AFTER_01's refined rug as its reference.
    assert edits[0]["reference"] is None
    first_refined = bucket.files[body["views"][0]["after_url"].rsplit("/", 1)[-1]]["data"]
    assert all(call["reference"] == first_refined for call in edits[1:])
    assert all("warm cream with a soft gray border" in call["prompt"] for call in edits)

    doc = fake.deliverables.docs[0]
    assert doc["package_status"] == "review"
    assert fake.leads.docs[0]["package_status"] == "review"
    for old, new in zip(before["source_afters"], doc["source_afters"]):
        for key in ("source_photo_id", "source_url", "label", "after_label", "status", "edit_kind", "derived_from_photo_id"):
            assert new[key] == old[key]
    changed = [new["after_url"] != old["after_url"] for old, new in zip(before["source_afters"], doc["source_afters"])]
    assert changed == [True, True, False, True]
    assert doc["source_afters"][2]["after_url"] == "/api/uploads/photo/after3"
    assert doc["source_afters"][0]["after_history"][0]["after_url"] == "/api/uploads/photo/after1"
    assert doc["front_view_url"] == doc["source_afters"][0]["after_url"]
    assert doc["rug"]["color"] == RUG["color"]
    assert doc["after_refine"]["status"] == "done"
    assert doc["contact_sheet_url"].startswith("/api/uploads/photo/")

    from source_photos import final_email_block_reason, mapping_is_own_source

    assert all(mapping_is_own_source(entry) for entry in doc["source_afters"])
    assert final_email_block_reason(doc) is None

    status = client.get(f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine", headers={"X-Admin-Token": token})
    assert status.json()["status"] == "done"


def test_refined_afters_reach_the_board_pdf_and_zone_map(api, monkeypatch):
    client, fake, bucket, _edits, token = api
    import server

    client.post(
        f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine?wait=true",
        headers={"X-Admin-Token": token},
        json={"labels": ["AFTER_02"]},
    )
    doc = fake.deliverables.docs[0]
    new_url = doc["source_afters"][1]["after_url"]
    assert new_url != "/api/uploads/photo/after2"
    assert doc["source_afters"][0]["after_url"] == "/api/uploads/photo/after1"
    _lead, _d, images = asyncio.run(server._blueprint_render_inputs(LEAD_ID, None))
    refined = bucket.files[new_url.rsplit("/", 1)[-1]]["data"]
    assert images["source_pairs"][1]["after"] == refined
    assert [pair["label"] for pair in images["source_pairs"]] == ["SOURCE_01", "SOURCE_02", "SOURCE_03", "SOURCE_04"]


def test_refine_refuses_a_lead_without_approved_afters(api):
    client, fake, _bucket, edits, token = api
    fake.deliverables.docs[0]["source_afters"] = []
    res = client.post(f"/api/admin/leads/{LEAD_ID}/deliverable/afters/refine", headers={"X-Admin-Token": token})
    assert res.status_code == 409
    assert edits == []
