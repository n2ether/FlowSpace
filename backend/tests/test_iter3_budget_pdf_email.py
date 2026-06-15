"""Iteration 3 tests: budget field, portrait multi-page PDF with photos page, and email attachments."""
import asyncio
import base64
import os
import sys
from unittest.mock import patch

import pytest
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNiAAIAAAUAAeImBZsAAAAASUVORK5CYII="
)


# ---- Budget field accepted & persisted; PDF total respects budget cap ----
class TestBudgetSubmission:
    sub_id = None

    def test_plus_submission_accepts_budget(self):
        r = requests.post(
            f"{API}/submissions",
            json={
                "name": "TEST_iter3",
                "email": "TEST_iter3_budget@example.com",
                "plan_id": "plus",
                "room_type": "bedroom",
                "budget": "$100 – $300",
                "photos_base64": [TINY_PNG],
            },
            timeout=240,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan_id"] == "plus"
        assert data["pdf_available"] is True
        TestBudgetSubmission.sub_id = data["id"]

    def test_pdf_reflects_budget_and_respects_cap(self):
        if not TestBudgetSubmission.sub_id:
            pytest.skip("submission missing")
        r = requests.get(f"{API}/submissions/{TestBudgetSubmission.sub_id}/pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        doc = fitz.open(stream=r.content, filetype="pdf")
        # Portrait: width < height
        page0 = doc.load_page(0)
        assert page0.rect.width < page0.rect.height, f"Not portrait: {page0.rect}"
        # Multi-page
        assert doc.page_count >= 2, f"Only {doc.page_count} pages"
        # All text combined
        all_text = "\n".join(p.get_text() for p in doc)
        assert "YOUR ORGANIZED SPACE" in all_text, "Photos page heading missing"
        assert "$100" in all_text and "300" in all_text, "Budget not reflected in PDF"
        # Shopping total should not exceed cap (300)
        # Estimated total appears next to "ESTIMATED TOTAL"
        # Extract a $NUMBER following 'ESTIMATED TOTAL'
        import re as _re
        m = _re.search(r"ESTIMATED TOTAL[^\$]*\$(\d+)", all_text, _re.DOTALL)
        assert m, f"No estimated total found in PDF text:\n{all_text[:500]}"
        total = int(m.group(1))
        assert total <= 300, f"Total ${total} exceeds budget cap $300"
        doc.close()


# ---- Direct PDF rendering test (avoid Gemini cost) ----
class TestPdfDirectRender:
    def test_render_portrait_multipage_with_photos(self):
        from pdf_generator import render_design_plan_pdf
        from design_plan import DEFAULT_PLANS, ROOM_LABEL, ROOM_TITLE_SUFFIX

        base = DEFAULT_PLANS["bedroom"]
        plan = {
            "room_key": "bedroom",
            "room_label": ROOM_LABEL["bedroom"],
            "title": f"{ROOM_LABEL['bedroom']} {ROOM_TITLE_SUFFIX['bedroom']}",
            **base,
            "budget_range": "$300 – $500",
        }
        pdf_bytes = render_design_plan_pdf(
            plan=plan,
            main_image_b64=TINY_PNG,
            additional_images=[TINY_PNG, TINY_PNG],
            user_name="TEST user",
        )
        assert pdf_bytes[:4] == b"%PDF"
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count >= 2
        p0 = doc.load_page(0)
        # Letter portrait is ~612 x 792 pt
        assert p0.rect.width < p0.rect.height
        assert 580 < p0.rect.width < 640
        assert 760 < p0.rect.height < 820
        # Photos page heading
        has_photos_page = any(
            "YOUR ORGANIZED SPACE" in doc.load_page(i).get_text()
            for i in range(doc.page_count)
        )
        assert has_photos_page
        # VIEW labels present
        all_text = "\n".join(p.get_text() for p in doc)
        assert "VIEW 1" in all_text and "VIEW 2" in all_text
        doc.close()


# ---- Email attachments via monkey-patched resend.Emails.send ----
class TestEmailAttachments:
    def _build_submission(self, plan_id, with_pdf):
        results = [
            {"before": TINY_PNG, "after": TINY_PNG},
            {"before": TINY_PNG, "after": TINY_PNG},
            {"before": TINY_PNG, "after": TINY_PNG},
        ]
        sub = {
            "id": "test-sub-iter3",
            "plan_id": plan_id,
            "name": "TEST",
            "email": "TEST_iter3_email@example.com",
            "room_type": "bedroom",
            "notes": None,
            "budget": "$100 – $300",
            "results": results,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        if with_pdf:
            sub["pdf_base64"] = base64.b64encode(b"%PDF-FAKE").decode("ascii")
        return sub

    def test_plus_admin_email_includes_pdf_and_three_pngs(self):
        import server
        sub = self._build_submission("plus", with_pdf=True)
        captured = {}
        def fake_send(params): captured.update(params); return {"id": "fake"}
        with patch.object(server.resend.Emails, "send", side_effect=fake_send):
            server.send_admin_email_sync(sub)
        atts = captured.get("attachments", [])
        assert len(atts) == 4, f"Expected 4 attachments (1 PDF + 3 PNGs), got {len(atts)}"
        assert atts[0]["filename"].endswith(".pdf")
        png_names = [a["filename"] for a in atts[1:]]
        assert all("Organized-Photo" in n and n.endswith(".png") for n in png_names), png_names
        assert all("Bedroom" in n for n in png_names)

    def test_plus_customer_email_includes_pdf_and_three_pngs(self):
        import server
        sub = self._build_submission("plus", with_pdf=True)
        captured = {}
        def fake_send(params): captured.update(params); return {"id": "fake"}
        with patch.object(server.resend.Emails, "send", side_effect=fake_send):
            server.send_customer_email_sync(sub, "https://example.com/result/test-sub-iter3")
        atts = captured.get("attachments", [])
        assert len(atts) == 4
        assert atts[0]["filename"].endswith(".pdf")
        assert captured["to"] == ["TEST_iter3_email@example.com"]

    def test_free_admin_email_has_only_pngs_no_pdf(self):
        import server
        sub = self._build_submission("free", with_pdf=False)
        sub["results"] = sub["results"][:2]  # free plan max 2
        captured = {}
        def fake_send(params): captured.update(params); return {"id": "fake"}
        with patch.object(server.resend.Emails, "send", side_effect=fake_send):
            server.send_admin_email_sync(sub)
        atts = captured.get("attachments", [])
        assert len(atts) == 2, f"Expected 2 PNGs only, got {len(atts)}"
        assert all(a["filename"].endswith(".png") for a in atts)
        assert not any(a["filename"].endswith(".pdf") for a in atts)


# ---- Regression: plans, checkout, free submission, pdf endpoints ----
class TestRegression:
    def test_plans_unchanged(self):
        r = requests.get(f"{API}/plans", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["plus"]["pdf"] is True and d["free"]["pdf"] is False

    def test_checkout_plus(self):
        r = requests.post(
            f"{API}/checkout/session",
            json={"plan_id": "plus", "origin_url": "https://example.com"},
            timeout=30,
        )
        assert r.status_code == 200
        assert "stripe.com" in r.json()["url"]

    def test_free_pdf_endpoint_402(self):
        # create free submission first
        r = requests.post(
            f"{API}/submissions",
            json={
                "email": "TEST_iter3_freeReg@example.com",
                "plan_id": "free",
                "room_type": "bedroom",
                "photos_base64": [TINY_PNG],
            },
            timeout=180,
        )
        assert r.status_code == 200
        sid = r.json()["id"]
        p = requests.get(f"{API}/submissions/{sid}/pdf", timeout=30)
        assert p.status_code == 402

    def test_pdf_404_for_missing(self):
        r = requests.get(f"{API}/submissions/nonexistent-xxx/pdf", timeout=30)
        assert r.status_code == 404
