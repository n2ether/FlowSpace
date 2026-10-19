"""Uploads: HEIC conversion, unguessable ids, signed/private reads, admin session tokens."""
import io
import re
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.test_member_auth import FakeDB


class _Stream:
    def __init__(self, entry):
        self._entry = entry
        self.metadata = entry["metadata"]
        self.filename = entry["filename"]

    async def read(self):
        return self._entry["data"]


class _Bucket:
    def __init__(self):
        self.files = {}

    async def upload_from_stream_with_id(self, file_id, filename, source, metadata=None):
        data = source.read() if hasattr(source, "read") else bytes(source)
        self.files[str(file_id)] = {"filename": filename, "data": data, "metadata": metadata or {}}

    async def open_download_stream(self, key):
        from gridfs.errors import NoFile

        entry = self.files.get(str(key))
        if entry is None:
            raise NoFile()
        return _Stream(entry)


def _jpeg(size=(800, 600), color=(200, 170, 140)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _heic(size=(800, 600), color=(200, 170, 140)):
    import pillow_heif

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="HEIF")
    return buf.getvalue()


@pytest.fixture
def app(monkeypatch):
    import server

    fake = FakeDB()
    bucket = _Bucket()
    monkeypatch.setattr(server, "db", fake)
    monkeypatch.setattr(server, "fs_bucket", bucket)

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    with TestClient(server.app) as c:
        yield c, fake, bucket


def _upload(c, data, name="room.jpg", ct="image/jpeg", **kw):
    return c.post("/api/uploads/photo", files={"file": (name, data, ct)}, **kw)


# ──────────────────────────── HEIC ─────────────────────────────
class TestHeic:
    def test_heic_decodes_to_jpeg(self):
        from image_orientation import normalize_photo_bytes

        out, info = normalize_photo_bytes(_heic())
        assert out[:2] == b"\xff\xd8"
        assert info["content_type"] == "image/jpeg"
        assert (info["width"], info["height"]) == (800, 600)

    def test_is_heif_upload_by_type_or_extension(self):
        from image_orientation import is_heif_upload

        assert is_heif_upload("image/heic", "x")
        assert is_heif_upload("image/heif", "x")
        assert is_heif_upload("application/octet-stream", "IMG_0001.HEIC")
        assert not is_heif_upload("application/octet-stream", "notes.txt")
        assert not is_heif_upload("image/jpeg", "a.jpg")

    @pytest.mark.parametrize("ct", ["image/heic", "image/heif", "application/octet-stream", ""])
    def test_heic_upload_is_stored_as_jpeg(self, app, ct):
        c, _db, bucket = app
        r = _upload(c, _heic(), name="IMG_0420.HEIC", ct=ct or "application/octet-stream")
        assert r.status_code == 200, r.text
        entry = bucket.files[r.json()["id"]]
        assert entry["data"][:2] == b"\xff\xd8"
        assert entry["metadata"]["content_type"] == "image/jpeg"
        assert entry["metadata"]["converted_from_heif"] is True
        assert entry["filename"] == "IMG_0420.jpg"

    def test_non_image_is_still_rejected(self, app):
        c, _db, _bucket = app
        r = _upload(c, b"hello", name="notes.txt", ct="text/plain")
        assert r.status_code == 400

    def test_requirements_pin_pillow_heif(self):
        from pathlib import Path

        reqs = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
        assert re.search(r"^pillow-heif", reqs, re.M)


# ──────────────────────────── Ids + signed reads ─────────────────────────────
class TestPhotoAccess:
    def test_new_uploads_get_unguessable_ids(self, app):
        c, _db, _bucket = app
        ids = [_upload(c, _jpeg(color=(i, 10, 10))).json()["id"] for i in range(3)]
        assert all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids)
        assert len(set(ids)) == 3

    def test_upload_returns_signed_preview_and_canonical_url(self, app):
        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        assert body["stored_url"] == f"/api/uploads/photo/{body['id']}"
        assert body["url"].startswith(body["stored_url"] + "?exp=")
        assert "sig=" in body["url"]
        assert body["upload_token"]

    def test_unsigned_read_is_refused(self, app):
        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        r = c.get(body["stored_url"])
        assert r.status_code == 404

    def test_signed_read_is_private_cache(self, app):
        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        r = c.get(body["url"])
        assert r.status_code == 200
        assert r.content[:2] == b"\xff\xd8"
        cache = r.headers["cache-control"]
        assert cache.startswith("private")
        assert "public" not in cache and "immutable" not in cache

    def test_tampered_or_expired_signature_is_refused(self, app):
        from photo_access import signature

        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        pid = body["id"]
        assert c.get(body["url"].replace("sig=", "sig=x")).status_code == 404
        past = int(time.time()) - 10
        assert c.get(f"/api/uploads/photo/{pid}?exp={past}&sig={signature(pid, past)}").status_code == 404
        other = _upload(c, _jpeg(color=(1, 2, 3))).json()
        exp, sig = body["url"].split("?exp=")[1].split("&sig=")
        assert c.get(f"/api/uploads/photo/{other['id']}?exp={exp}&sig={sig}").status_code == 404

    def test_signed_url_lasts_about_an_hour(self):
        from photo_access import signature_from_url, signed_photo_url, verify_signature

        now = 1_800_000_000
        url = signed_photo_url("/api/uploads/photo/" + "a" * 32, now=now)
        exp, sig = signature_from_url(url)
        assert 3600 <= int(exp) - now <= 3600 + 300
        assert verify_signature("a" * 32, exp, sig, now=now + 3500)
        assert not verify_signature("a" * 32, exp, sig, now=now + 4000)

    def test_upload_token_refreshes_the_preview(self, app):
        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        fresh = c.post(f"/api/uploads/photo/{body['id']}/preview", json={"upload_token": body["upload_token"]})
        assert fresh.status_code == 200
        assert c.get(fresh.json()["url"]).status_code == 200
        wrong = c.post(f"/api/uploads/photo/{body['id']}/preview", json={"upload_token": "nope"})
        assert wrong.status_code == 404

    def test_admin_header_can_read(self, app):
        import server

        c, _db, _bucket = app
        body = _upload(c, _jpeg()).json()
        token = c.post("/api/admin/login", json={"password": server.ADMIN_PASSWORD}).json()["token"]
        assert c.get(body["stored_url"], headers={"X-Admin-Token": token}).status_code == 200
        assert c.get(body["stored_url"], headers={"X-Admin-Token": "guess"}).status_code == 404

    def test_owning_member_can_read_and_others_cannot(self, app):
        c, db, bucket = app
        ada = c.post("/api/auth/signup", json={"name": "Ada", "email": "ada@example.com", "password": "password12"}).json()
        body = _upload(c, _jpeg(), headers={"Authorization": f"Bearer {ada['token']}"}).json()
        assert bucket.files[body["id"]]["metadata"]["member_id"] == ada["member"]["id"]
        assert c.get(body["stored_url"]).status_code == 200  # session cookie
        c.cookies.clear()
        grace = c.post("/api/auth/signup", json={"name": "Grace", "email": "grace@example.com", "password": "password12"}).json()
        c.cookies.clear()
        r = c.get(body["stored_url"], headers={"Authorization": f"Bearer {grace['token']}"})
        assert r.status_code == 404

    def test_member_reads_automation_outputs_through_lead(self, app):
        c, db, bucket = app
        ada = c.post("/api/auth/signup", json={"name": "Ada", "email": "ada@example.com", "password": "password12"}).json()
        c.cookies.clear()
        pid = "b" * 32
        bucket.files[pid] = {"filename": "ai.jpg", "data": _jpeg(), "metadata": {"lead_id": "lead-1", "content_type": "image/jpeg"}}
        db.leads.docs.append({"id": "lead-1", "member_id": ada["member"]["id"]})
        headers = {"Authorization": f"Bearer {ada['token']}"}
        assert c.get(f"/api/uploads/photo/{pid}", headers=headers).status_code == 200

    def test_legacy_object_id_photos_still_resolve_but_not_publicly(self, app):
        from photo_access import signed_photo_url

        c, _db, bucket = app
        legacy = "65f0c0ffee0000000000abcd"
        bucket.files[legacy] = {"filename": "old.jpg", "data": _jpeg(), "metadata": {"content_type": "image/jpeg"}}
        assert c.get(f"/api/uploads/photo/{legacy}").status_code == 404
        assert c.get(signed_photo_url(f"/api/uploads/photo/{legacy}")).status_code == 200

    def test_stored_references_are_canonicalized(self):
        from photo_access import canonicalize_photo_urls, signed_photo_url

        url = "/api/uploads/photo/" + "c" * 32
        signed = signed_photo_url(url)
        doc = {"photos": [signed, {"url": signed}], "front_view_url": signed, "other": "https://x.test/a?b=1"}
        out = canonicalize_photo_urls(doc)
        assert out == {"photos": [url, {"url": url}], "front_view_url": url, "other": "https://x.test/a?b=1"}

    def test_lead_create_stores_unsigned_urls(self, app, monkeypatch):
        import server

        c, db, _bucket = app

        async def no_automation(*a, **k):
            return True

        monkeypatch.setattr(server, "_start_automation_for_lead", no_automation)
        body = _upload(c, _jpeg()).json()
        r = c.post(
            "/api/leads",
            json={
                "name": "Ada",
                "email": "ada@example.com",
                "space_type": "closet",
                "package_id": "free",
                "photos": [body["url"]],
                "password": "password12",
            },
        )
        assert r.status_code == 200, r.text
        assert db.leads.docs[0]["photos"] == [body["stored_url"]]
        assert "sig=" in r.json()["photos"][0]

    def test_admin_deliverable_put_canonicalizes_and_get_signs(self, app):
        import server

        c, db, _bucket = app
        db.leads.docs.append({"id": "lead-9", "name": "A", "email": "a@example.com", "space_type": "closet"})
        token = c.post("/api/admin/login", json={"password": server.ADMIN_PASSWORD}).json()["token"]
        signed = _upload(c, _jpeg()).json()["url"]
        headers = {"X-Admin-Token": token}
        r = c.put("/api/admin/leads/lead-9/deliverable", json={"lead_id": "lead-9", "front_view_url": signed}, headers=headers)
        assert r.status_code == 200, r.text
        assert "sig=" not in db.deliverables.docs[0]["front_view_url"]
        got = c.get("/api/admin/leads/lead-9/deliverable", headers=headers).json()
        assert "sig=" in got["deliverable"]["front_view_url"]


# ──────────────────────────── Admin login ─────────────────────────────
class TestAdminLogin:
    def test_login_returns_a_session_token_not_the_password(self, app):
        import server

        c, _db, _bucket = app
        r = c.post("/api/admin/login", json={"password": server.ADMIN_PASSWORD})
        assert r.status_code == 200
        token = r.json()["token"]
        assert token != server.ADMIN_PASSWORD
        assert server.ADMIN_PASSWORD not in token
        assert c.get("/api/admin/transactions", headers={"X-Admin-Token": token}).status_code == 200
        second = c.post("/api/admin/login", json={"password": server.ADMIN_PASSWORD}).json()["token"]
        assert second != token

    def test_wrong_password_and_forged_tokens_are_refused(self, app):
        import jwt

        c, _db, _bucket = app
        assert c.post("/api/admin/login", json={"password": "nope"}).status_code == 401
        forged = jwt.encode({"sub": "admin", "aud": "flowspace-admin", "exp": int(time.time()) + 60}, "wrong", algorithm="HS256")
        assert c.get("/api/admin/transactions", headers={"X-Admin-Token": forged}).status_code == 401

    def test_expired_session_token_is_refused(self):
        from admin_session import create_admin_token, verify_admin_token

        assert verify_admin_token(create_admin_token())
        assert not verify_admin_token(create_admin_token(now=time.time() - 10, ttl=1))
