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

    async def fake_draft(lead_doc):
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
