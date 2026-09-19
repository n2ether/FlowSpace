"""Automation pipeline: FLUX bytes must reach build_pdf (no live APIs)."""
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


def _run(monkeypatch, *, generate, send=(True, None), fs=None, lead=None, capture=None):
    from automation import run_automation

    async def fake_draft(lead_doc, **kwargs):
        captured["draft_photo"] = kwargs.get("reference_photo_bytes")
        return dict(PLAN)

    async def _gen(**kwargs):
        return generate(**kwargs)

    async def fake_send(**kwargs):
        return send

    captured = capture if capture is not None else {}

    def fake_build_pdf(*, lead, deliverable, images):
        captured["images"] = images
        from pdf_generator import build_pdf as real_build

        return real_build(lead=lead, deliverable=deliverable, images=images)

    monkeypatch.setattr("automation.draft_deliverable", fake_draft)
    monkeypatch.setattr("automation.generate_front_view", _gen)
    monkeypatch.setattr("automation.send_blueprint", fake_send)
    monkeypatch.setattr("automation.build_pdf", fake_build_pdf)

    db = _FakeDB()
    fs = fs or _FakeFS()
    lead = lead or _lead()
    db.leads.docs[lead["id"]] = dict(lead)
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
    assert len(PdfReader(io.BytesIO(pdf)).pages[0].images) >= 1


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
    assert sent is True
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
    images = captured["images"]
    assert images["before"] == original
    assert images["after"] == flux
    assert images["front_view"] == flux
    assert images["front_view_kind"] == "organized"
    assert captured.get("draft_photo") == original


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
    assert sent is True
    images = captured["images"]
    assert images["after"] is None
    assert images["front_view"] == original
    assert images["front_view_kind"] == "original"
    qa = db.deliverables.docs["lead-img-1"].get("render_qa") or {}
    assert qa.get("ok") is False
    assert qa.get("windows_covered") is True
