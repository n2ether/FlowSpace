"""Backend tests for POST /api/admin/leads/{lead_id}/deliverable/draft (Claude Sonnet 4.5 via Emergent LLM)."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://flowspace-preview-1.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = "garage2025"
HEADERS = {"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"}
TIMEOUT = 90


def _pick_rich_lead():
    r = requests.get(f"{BASE_URL}/api/admin/leads", headers=HEADERS, timeout=30)
    r.raise_for_status()
    leads = r.json()
    # Pick one with desired_feeling AND color_prefs populated
    for l in leads:
        if l.get("desired_feeling") and l.get("color_prefs") and l.get("bothers_about"):
            return l
    # Fallback
    for l in leads:
        if l.get("desired_feeling"):
            return l
    return leads[0]


@pytest.fixture(scope="module")
def rich_lead():
    return _pick_rich_lead()


@pytest.fixture(scope="module")
def draft(rich_lead):
    url = f"{BASE_URL}/api/admin/leads/{rich_lead['id']}/deliverable/draft"
    r = requests.post(url, headers=HEADERS, json={}, timeout=TIMEOUT)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:400]}"
    body = r.json()
    assert "draft" in body
    return body["draft"]


# ---------------- Auth tests ----------------
class TestAuth:
    def test_missing_token_returns_401(self, rich_lead):
        url = f"{BASE_URL}/api/admin/leads/{rich_lead['id']}/deliverable/draft"
        r = requests.post(url, timeout=30)
        assert r.status_code == 401

    def test_wrong_token_returns_401(self, rich_lead):
        url = f"{BASE_URL}/api/admin/leads/{rich_lead['id']}/deliverable/draft"
        r = requests.post(url, headers={"X-Admin-Token": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_nonexistent_lead_returns_404(self):
        url = f"{BASE_URL}/api/admin/leads/nonexistent-id-xxx/deliverable/draft"
        r = requests.post(url, headers=HEADERS, timeout=TIMEOUT)
        assert r.status_code == 404


# ---------------- Draft schema tests ----------------
class TestDraftSchema:
    def test_intro_is_string(self, draft):
        assert isinstance(draft.get("intro"), str)
        assert len(draft["intro"]) > 0

    def test_needs_is_string_list(self, draft):
        needs = draft.get("needs")
        assert isinstance(needs, list) and len(needs) >= 3
        for n in needs:
            assert isinstance(n, str) and n.strip()

    def test_zones_structure(self, draft):
        zones = draft.get("zones")
        assert isinstance(zones, list) and len(zones) >= 3
        for z in zones:
            assert isinstance(z, dict)
            assert "title" in z and "desc" in z
            assert isinstance(z["title"], str)
            assert isinstance(z["desc"], str)

    def test_wall_color_fields(self, draft):
        assert isinstance(draft.get("wall_color_name"), str) and draft["wall_color_name"]
        assert isinstance(draft.get("wall_color_code"), str)
        assert isinstance(draft.get("wall_color_note"), str)

    def test_wall_color_hex_is_valid(self, draft):
        hx = draft.get("wall_color_hex")
        assert isinstance(hx, str)
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", hx), f"Invalid hex: {hx}"

    def test_shopping_list_structure(self, draft):
        sl = draft.get("shopping_list")
        assert isinstance(sl, list) and len(sl) >= 4, f"Expected 4+ items, got {len(sl) if sl else 0}"
        for item in sl:
            assert isinstance(item, dict)
            assert isinstance(item.get("name"), str) and item["name"].strip()
            assert isinstance(item.get("qty"), (int, float))
            assert isinstance(item.get("price"), (int, float))
            assert item["price"] > 0, f"Item price must be > 0: {item}"

    def test_budget_note_string(self, draft):
        assert isinstance(draft.get("budget_note"), str)

    def test_strategy_list(self, draft):
        s = draft.get("strategy")
        assert isinstance(s, list) and len(s) >= 3
        for x in s:
            assert isinstance(x, str) and x.strip()

    def test_action_plan_list(self, draft):
        a = draft.get("action_plan")
        assert isinstance(a, list) and len(a) >= 3
        for x in a:
            assert isinstance(x, str) and x.strip()

    def test_benefits_list(self, draft):
        b = draft.get("benefits")
        assert isinstance(b, list) and len(b) >= 3
        for x in b:
            assert isinstance(x, str) and x.strip()

    def test_notes_summary_attachment(self, draft):
        assert isinstance(draft.get("notes"), str) and draft["notes"]
        assert isinstance(draft.get("summary"), str) and draft["summary"]
        assert isinstance(draft.get("attachment_note"), str)


# ---------------- Semantic relevance ----------------
class TestSemanticRelevance:
    def test_content_reflects_questionnaire(self, rich_lead, draft):
        """Loosely verify the LLM output references the lead's desired feeling / colors / space."""
        text = " ".join([
            draft.get("intro", ""),
            draft.get("summary", ""),
            draft.get("wall_color_name", ""),
            draft.get("wall_color_note", ""),
            " ".join(draft.get("strategy", [])),
            " ".join(draft.get("needs", [])),
            " ".join(z.get("desc", "") + " " + z.get("title", "") for z in draft.get("zones", [])),
        ]).lower()

        feelings = [f.lower() for f in (rich_lead.get("desired_feeling") or [])]
        # At least one feeling-ish keyword should appear
        feeling_synonyms = {
            "calm": ["calm", "serene", "peaceful", "tranquil", "relaxed"],
            "minimal": ["minimal", "clean", "uncluttered", "simple", "spare"],
            "airy": ["airy", "open", "light", "breath"],
            "cozy": ["cozy", "warm", "inviting"],
            "warm": ["warm", "inviting"],
            "functional": ["function", "practical", "efficien"],
            "modern": ["modern", "contemporary"],
            "elegant": ["elegant", "refined"],
            "luxurious": ["luxur", "elevated"],
            "practical": ["practical", "function"],
        }
        hits = 0
        for f in feelings:
            for kw in feeling_synonyms.get(f, [f]):
                if kw in text:
                    hits += 1
                    break
        assert hits >= 1, f"Output should reflect at least one desired feeling {feelings}. Text sample: {text[:300]}"
