"""Automation pipeline: organized-render bytes must reach the board and PDF (no live APIs)."""
import asyncio
import io
from typing import Any, Dict, Optional

from PIL import Image

from pdf_images import HERO_PLACEHOLDER_LABEL


def _jpeg(color=(20, 110, 70), size=(240, 160)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


class _FakeColl:
    def __init__(self) -> None:
        self.docs: Dict[str, Dict[str, Any]] = {}

    async def update_one(self, query, update, upsert: bool = False):
        key = query.get("id") or query.get("lead_id") or "default"
        doc = self.docs.get(key, {})
        doc.update(update.get("$set") or {})
        if "id" in query:
            doc.setdefault("id", query["id"])
        if "lead_id" in query:
            doc.setdefault("lead_id", query["lead_id"])
        self.docs[key] = doc
        return None

    async def find_one(self, query, proj=None):
        key = query.get("id") or query.get("lead_id")
        if key and key in self.docs:
            return dict(self.docs[key])
        if self.docs:
            return dict(next(iter(self.docs.values())))
        return None


class _FakeDB:
    def __init__(self) -> None:
        self.leads = _FakeColl()
        self.deliverables = _FakeColl()


class _FakeStream:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _FakeFS:
    def __init__(self, store: Optional[Dict[str, bytes]] = None, fail_upload: bool = False):
        self.store = store or {}
        self.fail_upload = fail_upload
        self.uploads = 0

    async def upload_from_stream(self, filename, source, metadata=None):
        if self.fail_upload:
            raise RuntimeError("gridfs unavailable")
        data = source.read() if hasattr(source, "read") else source
        oid = f"{self.uploads:024x}"
        self.uploads += 1
        self.store[oid] = data if isinstance(data, bytes) else bytes(data)
        return oid

    async def open_download_stream(self, oid):
        key = str(oid)
        if key not in self.store:
            from gridfs.errors import NoFile

            raise NoFile()
        return _FakeStream(self.store[key])


PLAN = {
    "intro": "A calmer garage.",
    "zones": [{"title": "Parking", "desc": "Keep the stall clear"}],
    "needs": ["Clear floor"],
    "shopping_list": [],
    "strategy": [],
    "action_plan": ["Declutter"],
}


def _lead(*, with_photo: bool = False) -> Dict[str, Any]:
    lead = {
        "id": "lead-img-1",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "space_type": "garage",
        "photos": [],
    }
    if with_photo:
        lead["photos"] = ["/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa"]
    return lead


def _run(
    monkeypatch,
    *,
    generate,
    send=(True, None),
    fs=None,
    lead=None,
    capture=None,
    seed_deliverable=None,
):
    from automation import run_automation

    async def fake_draft(lead_doc, **kwargs):
        captured["draft_photo"] = kwargs.get("reference_photo_bytes")
        return dict(PLAN)

    async def _gen(**kwargs):
        return generate(**kwargs)

    async def fake_send(**kwargs):
        captured.setdefault("send_calls", []).append(kwargs.get("customer_email"))
        return send

    captured = capture if capture is not None else {}

    def fake_build_pdf(*, lead, deliverable, images):
        captured["images"] = images
        captured["deliverable"] = dict(deliverable or {})
        from pdf_generator import build_pdf as real_build

        return real_build(lead=lead, deliverable=deliverable, images=images)

    async def _views(**kwargs):
        captured.setdefault("supporting_calls", []).append(kwargs)
        return dict(captured.get("supporting_result") or {})

    monkeypatch.setattr("automation.draft_deliverable", fake_draft)
    monkeypatch.setattr("automation.generate_front_view", _gen)
    monkeypatch.setattr("automation.generate_supporting_views", _views)
    monkeypatch.setattr("automation.send_blueprint", fake_send)
    monkeypatch.setattr("automation.build_pdf", fake_build_pdf)

    db = _FakeDB()
    fs = fs or _FakeFS()
    lead = lead or _lead()
    db.leads.docs[lead["id"]] = dict(lead)
    if seed_deliverable:
        db.deliverables.docs[lead["id"]] = dict(seed_deliverable)
    sent = asyncio.run(run_automation(lead=lead, db=db, fs_bucket=fs))
    return sent, captured, db, fs


def test_automation_passes_flux_bytes_even_when_gridfs_upload_fails(monkeypatch):
    flux = _jpeg((10, 90, 50))
    captured: Dict[str, Any] = {}
    sent, captured, db, fs = _run(
        monkeypatch,
        generate=lambda **k: (flux, "image/jpeg"),
        fs=_FakeFS(fail_upload=True),
        capture=captured,
    )
    assert sent is True
    images = captured["images"]
    assert images["front_view"] == flux
    assert images["front_view_kind"] == "organized"
    assert images["after"] == flux
    assert images["before"] is None
    from pypdf import PdfReader

    # The captured images were also rendered; re-check via a direct build
    from pdf_generator import build_pdf

    pdf = build_pdf(
        lead=_lead(),
        deliverable=PLAN,
        images=images,
    )
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
    assert HERO_PLACEHOLDER_LABEL not in text
    assert len(PdfReader(io.BytesIO(pdf)).pages[-1].images) >= 1


def test_automation_uses_labeled_original_when_flux_fails(monkeypatch):
    original = _jpeg((110, 90, 60))
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {}

    def boom(**kwargs):
        raise RuntimeError("replicate down")

    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=boom,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is False
    assert db.leads.docs["lead-img-1"]["status"] == "incomplete"
    assert not captured.get("send_calls")
    images = captured["images"]
    assert images["front_view"] == original
    assert images["front_view_kind"] == "original"
    assert images["before"] == original
    assert images["after"] is None


def test_automation_placeholder_when_flux_fails_and_no_photo(monkeypatch):
    captured: Dict[str, Any] = {}

    def boom(**kwargs):
        raise RuntimeError("replicate down")

    sent, captured, db, fs = _run(
        monkeypatch,
        generate=boom,
        capture=captured,
    )
    assert sent is True
    images = captured["images"]
    assert images["front_view"] is None
    assert images["front_view_kind"] == "placeholder"


def test_automation_does_not_crash_pipeline_on_flux_failure(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("flux exploded")

    sent, captured, db, fs = _run(monkeypatch, generate=boom)
    assert sent is True
    assert db.leads.docs["lead-img-1"]["status"] == "delivered"


def test_automation_passes_before_and_after_when_both_exist(monkeypatch):
    original = _jpeg((110, 90, 60))
    flux = _jpeg((10, 90, 50))
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=lambda **k: (flux, "image/jpeg"),
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is True
    assert db.leads.docs["lead-img-1"]["status"] == "review"
    assert db.leads.docs["lead-img-1"]["email_sent"] is False
    assert not captured.get("send_calls")
    images = captured["images"]
    assert images["before"] == original
    assert images["after"] == flux
    assert images["front_view"] == flux
    assert images["front_view_kind"] == "organized"
    assert captured.get("draft_photo") == original
    stored = db.deliverables.docs["lead-img-1"].get("source_afters") or []
    assert len(stored) == 1
    assert stored[0]["source_photo_id"] == "aaaaaaaaaaaaaaaaaaaaaaaa"
    assert stored[0]["status"] == "approved"
    assert stored[0]["after_url"]


def _exif_jpeg(*, size=(80, 40), color=(20, 80, 200), orientation=6) -> bytes:
    img = Image.new("RGB", size, color)
    exif = img.getexif()
    exif[274] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def test_automation_normalizes_exif_before_draft_and_flux(monkeypatch):
    from image_orientation import normalize_photo_bytes

    raw = _exif_jpeg(orientation=6)
    expected, info = normalize_photo_bytes(raw)
    assert info["applied"] is True
    calls: list = []

    def generate(**kwargs):
        calls.append(kwargs)
        return _jpeg((10, 90, 50)), "image/jpeg"

    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": raw})
    captured: Dict[str, Any] = {}
    sent, captured, db, fs_out = _run(
        monkeypatch,
        generate=generate,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is True
    assert calls and Image.open(io.BytesIO(calls[0]["reference_photo_bytes"])).size == (40, 80)
    assert captured.get("draft_photo") == calls[0]["reference_photo_bytes"]
    assert db.leads.docs["lead-img-1"]["photos"][0] != "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa"
    assert fs_out.uploads >= 2  # upright original + organized render


def test_automation_retries_once_after_qa_fail(monkeypatch):
    from render_qa import RenderQAResult

    original = _jpeg((110, 90, 60))
    first = _jpeg((200, 10, 10))
    second = _jpeg((10, 200, 10))
    calls: list = []

    def generate(**kwargs):
        calls.append(kwargs)
        return (first if len(calls) == 1 else second), "image/jpeg"

    qas = [
        RenderQAResult(
            ok=False,
            gravity_wrong=True,
            reasons=["Ceiling fan on the wall"],
            suggested_rotate_degrees=90,
        ),
        RenderQAResult(ok=True),
    ]

    def fake_review(**kwargs):
        return qas.pop(0)

    monkeypatch.setattr("automation.review_organized_render", fake_review)
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is True
    assert len(calls) == 2
    assert calls[1].get("stronger_rails") is True
    assert captured["images"]["after"] == second
    assert captured["images"]["front_view_kind"] == "organized"
    qa = db.deliverables.docs["lead-img-1"].get("render_qa") or {}
    assert qa.get("ok") is True


def test_qa_retry_extra_includes_wall_preserve_constraint():
    from ai_image_generator import WALL_RETRY_CONSTRAINT
    from automation import _qa_retry_extra
    from render_qa import RenderQAResult

    extra = _qa_retry_extra(
        RenderQAResult(
            ok=False,
            walls_repainted=True,
            reasons=["Walls went from light blue to taupe"],
        )
    )
    assert "original light wall color from the photo" in extra.lower()
    assert WALL_RETRY_CONSTRAINT in extra
    assert "taupe" in extra.lower()


def test_automation_retries_once_after_wall_repaint_qa(monkeypatch):
    from render_qa import RenderQAResult

    original = _jpeg((160, 190, 220))  # light blue
    first = _jpeg((200, 170, 140))  # warm taupe
    second = _jpeg((160, 190, 220))
    calls: list = []

    def generate(**kwargs):
        calls.append(kwargs)
        return (first if len(calls) == 1 else second), "image/jpeg"

    qas = [
        RenderQAResult(
            ok=False,
            walls_repainted=True,
            reasons=["Walls shifted from light blue to taupe"],
        ),
        RenderQAResult(ok=True),
    ]

    def fake_review(**kwargs):
        return qas.pop(0)

    monkeypatch.setattr("automation.review_organized_render", fake_review)
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is True
    assert len(calls) == 2
    assert calls[1].get("stronger_rails") is True
    extra = (calls[1].get("extra_constraint") or "").lower()
    assert "original light wall color from the photo" in extra
    assert captured["images"]["after"] == second
    qa = db.deliverables.docs["lead-img-1"].get("render_qa") or {}
    assert qa.get("ok") is True


def test_automation_discards_after_when_qa_fails_twice(monkeypatch):
    from render_qa import RenderQAResult

    original = _jpeg((110, 90, 60))
    flux = _jpeg((200, 10, 10))

    def generate(**kwargs):
        return flux, "image/jpeg"

    monkeypatch.setattr(
        "automation.review_organized_render",
        lambda **k: RenderQAResult(
            ok=False,
            windows_covered=True,
            reasons=["Shelves over the right window"],
            attempt=k.get("attempt", 1),
        ),
    )
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is False
    assert db.leads.docs["lead-img-1"]["status"] == "incomplete"
    assert not captured.get("send_calls")
    images = captured["images"]
    assert images["after"] is None
    assert images["front_view"] == original
    assert images["front_view_kind"] == "original"
    qa = db.deliverables.docs["lead-img-1"].get("render_qa") or {}
    assert qa.get("ok") is False
    assert qa.get("windows_covered") is True
    assert db.deliverables.docs["lead-img-1"].get("front_view_url") is None


def test_qa_discard_clears_stale_organized_hero(monkeypatch):
    """A previous organized GridFS image must not become the PDF hero after QA discard."""
    from render_qa import RenderQAResult

    original = _jpeg((160, 190, 220))  # light blue photo
    stale_organized = _jpeg((200, 170, 140), size=(320, 200))  # previous taupe after
    flux = _jpeg((210, 175, 145), size=(280, 180))  # this-run failed after

    def generate(**kwargs):
        return flux, "image/jpeg"

    monkeypatch.setattr(
        "automation.review_organized_render",
        lambda **k: RenderQAResult(
            ok=False,
            walls_repainted=True,
            reasons=["Walls shifted from light blue to taupe"],
            attempt=k.get("attempt", 1),
        ),
    )
    stale_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    fs = _FakeFS(
        store={
            "aaaaaaaaaaaaaaaaaaaaaaaa": original,
            stale_id: stale_organized,
        }
    )
    captured: Dict[str, Any] = {}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
        seed_deliverable={
            "lead_id": "lead-img-1",
            "front_view_url": f"/api/uploads/photo/{stale_id}",
            "front_view_kind": "organized",
        },
    )
    assert sent is False
    assert db.leads.docs["lead-img-1"]["status"] == "incomplete"
    assert not captured.get("send_calls")
    images = captured["images"]
    assert images["after"] is None
    assert images["front_view"] == original
    assert images["front_view_kind"] == "original"
    assert images["front_view"] != stale_organized
    assert images["front_view"] != flux
    doc = db.deliverables.docs["lead-img-1"]
    assert doc.get("front_view_url") is None
    assert doc.get("front_view_kind") == "original"
    qa = doc.get("render_qa") or {}
    assert qa.get("ok") is False
    assert qa.get("walls_repainted") is True
    assert doc.get("view_1_url") is None
    assert images["view_1"] is None
    assert not captured.get("supporting_calls")


def test_supporting_views_attach_only_after_qa_passes(monkeypatch):
    from render_qa import RenderQAResult

    original = _jpeg((110, 90, 60))
    organized = _jpeg((10, 90, 50))
    extra = _jpeg((30, 40, 50), size=(80, 60))
    fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": original})
    captured: Dict[str, Any] = {
        "supporting_result": {"view_1": extra, "view_2": extra, "view_3": extra}
    }
    monkeypatch.setattr(
        "automation.review_organized_render",
        lambda **k: RenderQAResult(ok=True),
    )
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=lambda **k: (organized, "image/jpeg"),
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
    )
    assert sent is True
    assert db.leads.docs["lead-img-1"]["status"] == "review"
    assert not captured.get("send_calls")
    images = captured["images"]
    assert images["after"] == organized
    assert images["front_view_kind"] == "organized"
    assert images["view_1"] == extra
    assert images["view_2"] == extra
    assert images["view_3"] == extra
    assert len(captured["supporting_calls"]) == 1


def test_discarded_after_does_not_keep_a_stale_extra_view(monkeypatch):
    from render_qa import RenderQAResult

    original = _jpeg((160, 190, 220))
    failed = _jpeg((200, 170, 140))
    stale_view = _jpeg((210, 175, 145), size=(90, 60))
    extra = _jpeg((1, 2, 3), size=(40, 40))
    view_id = "cccccccccccccccccccccccc"
    fs = _FakeFS(
        store={
            "aaaaaaaaaaaaaaaaaaaaaaaa": original,
            view_id: stale_view,
        }
    )
    captured: Dict[str, Any] = {"supporting_result": {"view_1": extra}}
    monkeypatch.setattr(
        "automation.review_organized_render",
        lambda **k: RenderQAResult(
            ok=False,
            walls_repainted=True,
            reasons=["Walls shifted from light blue to taupe"],
            attempt=k.get("attempt", 1),
        ),
    )
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=lambda **k: (failed, "image/jpeg"),
        fs=fs,
        lead=_lead(with_photo=True),
        capture=captured,
        seed_deliverable={
            "lead_id": "lead-img-1",
            "view_1_url": f"/api/uploads/photo/{view_id}",
            "front_view_kind": "organized",
        },
    )
    assert sent is False
    assert db.leads.docs["lead-img-1"]["status"] == "incomplete"
    images = captured["images"]
    assert images["after"] is None
    assert images["view_1"] is None
    assert images["view_1"] != stale_view
    assert images["view_1"] != extra
    assert images["front_view_kind"] == "original"
    assert not captured.get("supporting_calls")
    assert db.deliverables.docs["lead-img-1"].get("view_1_url") is None


def _ui_screenshot() -> bytes:
    img = Image.new("RGB", (400, 800), (255, 255, 255))
    draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
    for y in range(80, 700, 70):
        draw.rectangle((24, y, 376, y + 40), fill=(241, 243, 245))
    draw.rectangle((24, 720, 200, 770), fill=(31, 61, 44))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_each_room_photo_is_edited_and_a_failure_blocks_final_email(monkeypatch):
    """Four angles: edit each source. One QA miss marks the package incomplete."""
    from render_qa import RenderQAResult

    photos = {
        "aaaaaaaaaaaaaaaaaaaaaaaa": _jpeg((20, 40, 180)),
        "bbbbbbbbbbbbbbbbbbbbbbbb": _jpeg((180, 40, 40)),
        "cccccccccccccccccccccccc": _jpeg((40, 160, 70)),
        "dddddddddddddddddddddddd": _jpeg((200, 160, 40)),
    }
    photos["eeeeeeeeeeeeeeeeeeeeeeee"] = _ui_screenshot()
    lead = _lead()
    lead["photos"] = [
        {"url": "/api/uploads/photo/eeeeeeeeeeeeeeeeeeeeeeee", "filename": "intake-screenshot.png"},
        "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa",
        "/api/uploads/photo/bbbbbbbbbbbbbbbbbbbbbbbb",
        "/api/uploads/photo/cccccccccccccccccccccccc",
        "/api/uploads/photo/dddddddddddddddddddddddd",
    ]
    calls = []

    def generate(**kwargs):
        calls.append(kwargs.get("reference_photo_bytes"))
        # Third room photo (index 2 of the room calls) fails QA both attempts.
        color = (200, 30, 30) if len(calls) in (3, 4) else (10, 120, 80)
        return _jpeg(color, size=(80, 60)), "image/jpeg"

    qas = {"n": 0}

    def review(**kwargs):
        qas["n"] += 1
        # Calls 3 and 4 are the two attempts for the third source.
        if qas["n"] in (3, 4):
            return RenderQAResult(ok=False, walls_repainted=True, reasons=["Walls went taupe"], attempt=kwargs.get("attempt", 1))
        return RenderQAResult(ok=True)

    monkeypatch.setattr("automation.review_organized_render", review)
    captured: Dict[str, Any] = {"supporting_result": {"view_1": _jpeg((1, 2, 3), size=(20, 20))}}
    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=_FakeFS(store=photos),
        lead=lead,
        capture=captured,
        seed_deliverable={
            "lead_id": "lead-img-1",
            "view_1_url": "/api/uploads/photo/bbbbbbbbbbbbbbbbbbbbbbbb",
            "view_2_url": "/api/uploads/photo/cccccccccccccccccccccccc",
            "front_view_url": "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa",
        },
    )
    assert sent is False
    assert db.leads.docs["lead-img-1"]["status"] == "incomplete"
    assert not captured.get("send_calls")
    assert not captured.get("supporting_calls")
    # Screenshot is not edited. The failing source is retried once (4 sources → 5 edits).
    assert len(calls) == 5
    assert calls[0] == photos["aaaaaaaaaaaaaaaaaaaaaaaa"]
    assert calls[1] == photos["bbbbbbbbbbbbbbbbbbbbbbbb"]
    assert calls[2] == photos["cccccccccccccccccccccccc"]
    assert calls[4] == photos["dddddddddddddddddddddddd"]
    assert photos["eeeeeeeeeeeeeeeeeeeeeeee"] not in calls
    doc = db.deliverables.docs["lead-img-1"]
    mapping = {row["source_photo_id"]: row for row in doc["source_afters"]}
    assert set(mapping) == {
        "aaaaaaaaaaaaaaaaaaaaaaaa",
        "bbbbbbbbbbbbbbbbbbbbbbbb",
        "cccccccccccccccccccccccc",
        "dddddddddddddddddddddddd",
    }
    assert mapping["cccccccccccccccccccccccc"]["status"] == "failed"
    assert mapping["cccccccccccccccccccccccc"]["after_url"] is None
    assert mapping["aaaaaaaaaaaaaaaaaaaaaaaa"]["status"] == "approved"
    assert mapping["aaaaaaaaaaaaaaaaaaaaaaaa"]["after_url"]
    assert doc.get("view_1_url") is None
    assert doc.get("view_2_url") is None
    assert doc.get("package_status") == "incomplete"
    images = captured["images"]
    assert images["view_1"] is None
    assert [pair["label"] for pair in images["source_pairs"]] == [
        "SOURCE_01",
        "SOURCE_02",
        "SOURCE_03",
        "SOURCE_04",
    ]
    assert images["source_pairs"][2]["after"] is None
    assert images["source_pairs"][0]["after"]
    from image_board import board_spec

    spec = board_spec(lead, PLAN, images)
    assert spec["hero_mode"] == "source_grid"
    assert spec["claims_organized_photo"] is False
    assert "after_crop" not in spec["detail_sources"]
    assert spec["detail_sources"] == ["SOURCE_01", "SOURCE_02", "SOURCE_03", "SOURCE_04"]
    from pdf_generator import build_pdf
    from pypdf import PdfReader

    text = "\n".join(
        (page.extract_text() or "")
        for page in PdfReader(io.BytesIO(build_pdf(lead=lead, deliverable=PLAN, images=images))).pages
    )
    assert "SOURCE_01" in text and "AFTER_04" in text
    assert "SOURCE_03" in text
    assert "not replaced" in text.lower() or "incomplete" in text.lower()


def test_multi_photo_review_keeps_every_after_and_skips_hero_angles(monkeypatch):
    photos = {
        "aaaaaaaaaaaaaaaaaaaaaaaa": _jpeg((20, 40, 180)),
        "bbbbbbbbbbbbbbbbbbbbbbbb": _jpeg((180, 40, 40)),
    }
    lead = _lead()
    lead["photos"] = [
        "/api/uploads/photo/aaaaaaaaaaaaaaaaaaaaaaaa",
        "/api/uploads/photo/bbbbbbbbbbbbbbbbbbbbbbbb",
    ]
    seen = []

    def generate(**kwargs):
        seen.append(kwargs.get("reference_photo_bytes"))
        extra = kwargs.get("extra_constraint") or ""
        assert "SAME CAMERA" in extra
        return _jpeg((10, 90, 50) if len(seen) == 1 else (40, 160, 70)), "image/jpeg"

    sent, captured, db, _fs = _run(
        monkeypatch,
        generate=generate,
        fs=_FakeFS(store=photos),
        lead=lead,
    )
    assert sent is True
    assert db.leads.docs["lead-img-1"]["status"] == "review"
    assert not captured.get("send_calls")
    assert not captured.get("supporting_calls")
    assert seen == [photos["aaaaaaaaaaaaaaaaaaaaaaaa"], photos["bbbbbbbbbbbbbbbbbbbbbbbb"]]
    rows = db.deliverables.docs["lead-img-1"]["source_afters"]
    assert [row["label"] for row in rows] == ["SOURCE_01", "SOURCE_02"]
    assert all(row["status"] == "approved" and row["after_url"] for row in rows)
    assert db.deliverables.docs["lead-img-1"].get("contact_sheet_url")
    assert db.deliverables.docs["lead-img-1"].get("package_status") == "review"
    from image_board import board_spec

    spec = board_spec(lead, PLAN, captured["images"])
    assert spec["claims_organized_photo"] is True
    assert spec["detail_sources"] == ["SOURCE_01", "SOURCE_02"]
    assert "after_crop" not in spec["detail_sources"]
