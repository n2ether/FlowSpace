"""Restart safety: stale processing leads are reclaimed once, re-queued, and capped."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from render_recovery import (
    claim_stale_lead,
    heartbeat_loop,
    max_recoveries,
    stale_filter,
    sweep_stale_renders,
    touch_render_heartbeat,
)
from tests.test_member_auth import FakeDB

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _lead(lead_id, minutes_ago, **over):
    doc = {
        "id": lead_id,
        "status": "processing",
        "package_id": "plus",
        "render_heartbeat_at": _iso(NOW - timedelta(minutes=minutes_ago)),
        "updated_at": _iso(NOW - timedelta(minutes=minutes_ago)),
    }
    doc.update(over)
    return doc


def _run(coro):
    return asyncio.run(coro)


def _doc(db, lead_id):
    return next(d for d in db.leads.docs if d["id"] == lead_id)


class TestSweep:
    def test_stale_lead_is_requeued_fresh_lead_is_left_alone(self):
        db = FakeDB()
        db.leads.docs += [_lead("stale", 30), _lead("fresh", 3), _lead("done", 60, status="review")]
        queued = []

        async def requeue(lead):
            queued.append(lead["id"])

        report = _run(sweep_stale_renders(db, requeue, now=NOW, owner="a"))
        assert report == {"requeued": ["stale"], "failed": []}
        assert queued == ["stale"]
        doc = _doc(db, "stale")
        assert doc["render_recoveries"] == 1
        assert doc["render_lease_owner"] == "a"
        assert doc["render_heartbeat_at"] == _iso(NOW)
        assert _doc(db, "fresh").get("render_recoveries") is None

    def test_old_lead_without_heartbeat_uses_updated_at(self):
        db = FakeDB()
        old = _lead("legacy", 40)
        old.pop("render_heartbeat_at")
        db.leads.docs.append(old)
        queued = []

        async def requeue(lead):
            queued.append(lead["id"])

        _run(sweep_stale_renders(db, requeue, now=NOW))
        assert queued == ["legacy"]

    def test_two_instances_cannot_both_claim(self):
        db = FakeDB()
        lead = _lead("race", 30)
        db.leads.docs.append(lead)
        snapshot = dict(lead)
        first = _run(claim_stale_lead(db, snapshot, now=NOW, owner="a"))
        second = _run(claim_stale_lead(db, snapshot, now=NOW, owner="b"))
        assert (first, second) == ("requeue", "")
        assert _doc(db, "race")["render_lease_owner"] == "a"

    def test_active_lease_blocks_a_second_claim_even_if_heartbeat_is_stale(self):
        db = FakeDB()
        db.leads.docs.append(_lead("leased", 30, render_lease_until=_iso(NOW + timedelta(minutes=5))))
        assert _run(claim_stale_lead(db, _doc(db, "leased"), now=NOW, owner="b")) == ""

    def test_retries_are_capped_then_the_lead_is_marked_failed(self):
        db = FakeDB()
        db.leads.docs.append(_lead("stuck", 30))
        queued = []

        async def requeue(lead):
            queued.append(lead["id"])

        now = NOW
        for _ in range(max_recoveries()):
            assert _run(sweep_stale_renders(db, requeue, now=now))["requeued"] == ["stuck"]
            # The re-queued run dies too: heartbeat and lease go stale.
            now = now + timedelta(minutes=30)
        report = _run(sweep_stale_renders(db, requeue, now=now))
        assert report == {"requeued": [], "failed": ["stuck"]}
        assert len(queued) == max_recoveries() == 2
        doc = _doc(db, "stuck")
        assert doc["status"] == "review"
        assert doc["automation_failed"] is True
        assert "automatic restart" in doc["automation_error"]
        assert doc["render_recovery_status"] == "gave_up"
        assert _run(sweep_stale_renders(db, requeue, now=now + timedelta(hours=1))) == {"requeued": [], "failed": []}

    def test_stale_filter_targets_processing_only(self):
        assert stale_filter(NOW)["status"] == "processing"


class TestHeartbeat:
    def test_touch_updates_processing_leads(self):
        db = FakeDB()
        db.leads.docs.append(_lead("hb", 30))
        _run(touch_render_heartbeat(db, "hb"))
        assert _doc(db, "hb")["render_heartbeat_at"] > _iso(NOW)

    def test_loop_ticks_until_cancelled(self):
        db = FakeDB()
        db.leads.docs.append(_lead("tick", 30))

        async def go():
            task = asyncio.create_task(heartbeat_loop(db, "tick", interval=0.01))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        _run(go())
        assert _doc(db, "tick")["render_heartbeat_at"] > _iso(NOW)

    def test_pipeline_touches_heartbeat_during_render_stages(self, monkeypatch):
        import automation

        touched = []

        async def fake_touch(_db, lead_id):
            touched.append(lead_id)

        monkeypatch.setattr(automation, "touch_render_heartbeat", fake_touch)
        from tests.test_automation import _FakeFS, _lead as auto_lead, _run as auto_run, _jpeg

        fs = _FakeFS(store={"aaaaaaaaaaaaaaaaaaaaaaaa": _jpeg()})
        auto_run(monkeypatch, generate=lambda **k: (_jpeg(), "image/jpeg"), fs=fs, lead=auto_lead(with_photo=True), capture={})
        # load, draft, each photo, before the board/PDF
        assert len(touched) >= 4


class TestServerWiring:
    def test_requeue_uses_the_forced_admin_path_behind_the_semaphore(self, monkeypatch):
        import server

        db = FakeDB()
        db.leads.docs.append(_lead("stale", 30))
        monkeypatch.setattr(server, "db", db)
        started = []

        async def fake_run(*, lead, db, fs_bucket):
            started.append(lead["id"])

        monkeypatch.setattr(server, "run_automation", fake_run)

        async def go():
            report = await sweep_stale_renders(db, server._requeue_stale_render, now=NOW)
            await asyncio.sleep(0)
            await asyncio.gather(*list(server._RECOVERY_TASKS))
            return report

        report = _run(go())
        assert report["requeued"] == ["stale"]
        assert started == ["stale"]
        assert _doc(db, "stale")["status"] == "processing"

    def test_admin_retry_resets_the_recovery_budget(self, monkeypatch):
        from fastapi.testclient import TestClient

        import server

        db = FakeDB()
        db.leads.docs.append(_lead("gave-up", 60, status="review", render_recoveries=2, render_recovery_status="gave_up"))
        monkeypatch.setattr(server, "db", db)

        async def fake_run(**_kw):
            return True

        async def no_seed():
            return None

        monkeypatch.setattr(server, "run_automation", fake_run)
        monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
        with TestClient(server.app) as c:
            r = c.post("/api/admin/leads/gave-up/retry-automation", headers={"X-Admin-Token": server.ADMIN_PASSWORD})
        assert r.status_code == 200
        doc = _doc(db, "gave-up")
        assert doc["render_recoveries"] == 0
        assert doc["status"] == "processing"

    def test_startup_starts_the_sweep_when_enabled(self, monkeypatch):
        from fastapi.testclient import TestClient

        import server

        calls = []

        async def fake_sweep(db, requeue, interval=300):
            calls.append(requeue)

        async def no_seed():
            return None

        monkeypatch.setenv("RENDER_RECOVERY_SWEEP", "1")
        monkeypatch.setattr(server, "sweep_forever", fake_sweep)
        monkeypatch.setattr(server, "db", FakeDB())
        monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
        with TestClient(server.app):
            pass
        assert calls == [server._requeue_stale_render]
