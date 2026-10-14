"""Living-room package: one fact set, the next held version, English evergreen copy."""
import asyncio
import io

from PIL import Image, ImageDraw
from pypdf import PdfReader

from blueprint_consistency import prepare_deliverable
from copy_shape import whole_title
from design_plan_standards import (
    PROCESS_STEPS,
    WHAT_STAYS_TEXT,
    package_version,
    version_label,
)
from evergreen_copy import find_time_sensitive
from image_board import board_spec, build_image_board
from package_facts import apply_measurement_rule, next_release, package_facts
from pdf_generator import MIN_PAGE_FILL, build_pdf, companion_page_fill, customer_project_title
from room_flow import default_room_flow, resolve_room_flow, validate_room_flow, zone_map_spec, zone_map_text

LEAD_ID = "4a2f3284-6628-4bda-9952-6f5de13ec936"
NURSERY_ID = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"
TOTAL = "Illustrative reference total: $243, including the $12 catch-all, before tax and shipping."


def _jpeg(color=(180, 160, 140), size=(240, 320)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _lead(**extra):
    return {
        "id": LEAD_ID,
        "name": "Camila Sales",
        "email": "camila.sales@gmail.com",
        "space_type": "living_room",
        "wall_color": "keep existing",
        **extra,
    }


def _items():
    return [
        {"name": "Entry catch-all tray", "qty": 1, "price": 12},
        {"name": "Woven basket 14 x 10 in", "qty": 2, "price": 18},
        {"name": "Lidded storage boxes", "qty": 4, "price": 22},
        {"name": "Wall shelf", "qty": 1, "price": 45},
        {"name": "Entry hooks", "qty": 1, "price": 20},
        {"name": "Picture frame 8x10 in", "qty": 1, "price": 15, "priority": "decorative"},
        {"name": "Decorative vase", "qty": 1, "price": 12, "priority": "decorative"},
        {"name": "Art print", "qty": 1, "price": 15, "priority": "decorative"},
    ]


def _deliverable(**extra):
    return {
        "lead_id": LEAD_ID,
        "wall_color_name": "keep existing",
        "package_status": "review",
        "package_version": 2,
        "design_plan_approved": False,
        "zones": [
            {"title": "Playpen", "desc": "A soft playpen stays in the play area."},
            {"title": "Entry drop", "desc": "Keys and bags land in one catch-all."},
            {"title": "Dining", "desc": "The table stays clear between meals."},
        ],
        "strategy": [
            "Create a drop zone by the entry for keys and bags so the floor stays clear.",
        ],
        "shopping_list": _items(),
        "shopping_links": [
            {
                "name": "Entry hooks",
                "url": "https://www.target.com/p/entry-hooks/-/A-123",
                "retailer": "Target",
                "link_type": "product",
                "label": "View at Target",
                "verified": True,
            },
            {
                "name": "Art print",
                "url": "https://www.target.com/s?searchTerm=art+print",
                "retailer": "Target",
                "link_type": "search",
                "label": "Search at Target",
                "verified": False,
            },
        ],
        **extra,
    }


def _pdf_text(lead, deliverable, images=None):
    reader = PdfReader(io.BytesIO(build_pdf(lead=lead, deliverable=deliverable, images=images or {})))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _board_text(monkeypatch, lead, deliverable, images=None):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def _record(self, xy, text, *args, **kwargs):
        drawn.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", _record)
    build_image_board(lead=lead, deliverable=deliverable, images=images or {})
    monkeypatch.undo()
    return "\n".join(drawn)


def test_version_labels_and_next_release_stay_held():
    assert package_version({}) == 1
    assert version_label(1) == "Versão 1 para sua análise"
    assert version_label(2) == "Versão 2 para sua análise"
    assert version_label(3) == "Versão 3 para sua análise"
    assert "V3" not in version_label(3)
    held = next_release({"package_status": "review"})
    assert held == {
        "package_version": 2,
        "version_label": "Versão 2 para sua análise",
        "package_status": "review",
        "design_plan_approved": False,
        "emailed": False,
    }
    # A final package from before sent_for_review existed counts as already emailed.
    bumped = next_release({"package_status": "final", "package_version": 2, "design_plan_approved": True})
    assert bumped["package_version"] == 3
    assert bumped["version_label"] == "Versão 3 para sua análise"
    assert bumped["sent_for_review"] == 2
    assert bumped["package_status"] == "review"
    assert bumped["design_plan_approved"] is False
    assert bumped["emailed"] is False
    assert next_release({"package_status": "incomplete"})["package_status"] == "incomplete"


def test_version_counts_only_copies_sent_for_review():
    """Regenerating an unsent copy keeps its number. This lead has not been sent V2."""
    unsent = next_release({"package_status": "review", "package_version": 2})
    assert unsent["package_version"] == 2
    assert unsent["version_label"] == "Versão 2 para sua análise"
    assert "sent_for_review" not in unsent
    # A mistaken bump to 3, with nothing emailed, collapses back to Versão 2.
    collapsed = next_release({"package_status": "review", "package_version": 3})
    assert collapsed["package_version"] == 2
    assert collapsed["version_label"] == "Versão 2 para sua análise"
    sent = next_release({"package_status": "review", "package_version": 2, "sent_for_review": 2})
    assert sent["package_version"] == 3
    assert sent["version_label"] == "Versão 3 para sua análise"
    assert sent["sent_for_review"] == 2
    kept = next_release({"package_status": "review", "package_version": 3, "sent_for_review": 2})
    assert kept["package_version"] == 3
    assert kept["version_label"] == "Versão 3 para sua análise"
    assert kept["emailed"] is False


def test_playpen_is_an_item_inside_the_play_zone():
    lead, deliverable = _lead(), _deliverable()
    prepared = prepare_deliverable(lead, deliverable)
    titles = [zone["title"] for zone in prepared["zones"]]
    assert "Playpen" not in titles
    assert "Play" in titles
    playpen = next(item for item in prepared["room_items"] if item["name"] == "Playpen")
    assert playpen["class"] == "item"
    flow = resolve_room_flow(lead, prepared)
    block = next(item for item in flow["furniture"] if item.get("label") == "PLAYPEN")
    assert block["kind"] == "block"
    assert "play" in str(block["zone"])
    assert validate_room_flow(flow) == []
    nursery = {"id": NURSERY_ID, "space_type": "kids_room", "name": "Camila Sales"}
    nursery_flow = resolve_room_flow(nursery, {"lead_id": NURSERY_ID})
    assert "PLAYPEN" not in [item.get("label") for item in nursery_flow.get("furniture") or []]


def test_frame_and_basket_sizes_need_a_measurement():
    lead, deliverable = _lead(), _deliverable()
    prepared = prepare_deliverable(lead, deliverable)
    names = [item["name"] for item in prepared["shopping_list"]]
    assert "Woven basket" in names
    assert "Picture frame" in names
    assert not any("14" in name or "8x10" in name or " x " in name for name in names)
    facts = package_facts(lead, deliverable, prepared=prepared)
    assert any(name.startswith("Woven basket") for name in facts["measure_items"])
    assert "Picture frame" in facts["measure_items"]
    nursery = {"id": NURSERY_ID, "space_type": "kids_room"}
    basket = {"shopping_list": [{"name": "Woven basket 14 x 10 in", "qty": 1, "price": 18}]}
    assert apply_measurement_rule(nursery, basket) == []
    assert basket["shopping_list"][0]["name"] == "Woven basket 14 x 10 in"


def test_shopping_total_splits_priority_and_link_kind():
    lead, deliverable = _lead(), _deliverable()
    facts = package_facts(lead, deliverable)
    assert facts["total"] == 243
    assert facts["total_line"] == TOTAL
    assert facts["total_note"] == "Includes the $12 catch-all · Before tax and shipping"
    functional = [row["name"] for row in facts["functional"]]
    decorative = [row["name"] for row in facts["decorative"]]
    assert "Entry catch-all tray" in functional
    assert "Picture frame" in decorative and "Decorative vase" in decorative and "Art print" in decorative
    assert facts["functional"] and facts["decorative"]
    kinds = {row["name"]: row["link"]["kind_label"] for row in facts["items"]}
    assert kinds["Entry hooks"] == "Tested product link"
    assert kinds["Art print"] == "Reference search"
    plain = package_facts(_lead(), _deliverable(shopping_list=[{"name": "Wall shelf", "qty": 1, "price": 150}]))
    assert plain["total_line"] == "Illustrative reference total: $150, before tax and shipping."


def test_shared_steps_what_stays_title_and_subtitle():
    lead, deliverable = _lead(), _deliverable()
    facts = package_facts(lead, deliverable)
    assert [step["title"] for step in facts["steps"]] == [
        "Measure and verify",
        "Set up functional storage",
        "Add styling",
    ]
    assert [step["name"] for step in facts["process"]] == [name for name, _body in PROCESS_STEPS]
    assert facts["what_stays"] == WHAT_STAYS_TEXT
    painted = package_facts(
        _lead(),
        _deliverable(wall_color_name="Soft white", wall_color_hex="#F4F1EC"),
    )
    assert painted["what_stays"] == "Keep all current furniture."
    assert customer_project_title(lead, deliverable) == "Living Room"
    assert default_room_flow(lead, deliverable)["subtitle"] == (
        "A calmer flow through the living, dining, and entry areas."
    )
    spec = zone_map_spec(lead, deliverable, {})
    assert spec["subtitle"] == "A calmer flow through the living, dining, and entry areas."
    assert spec["version_label"] == "Versão 2 para sua análise"
    assert WHAT_STAYS_TEXT in zone_map_text(spec)
    assert whole_title(deliverable["strategy"][0], max_words=6) == "Create a drop zone"
    moves = board_spec(lead, deliverable, {})["moves"]
    assert moves[0]["title"] == "CREATE A DROP ZONE"


def test_three_pieces_share_the_held_version_and_fill_their_pages(monkeypatch):
    lead, deliverable = _lead(), _deliverable()
    images = {
        "source_pairs": [
            {"label": "SOURCE_01", "before": _jpeg((140, 120, 100)), "after": _jpeg((200, 180, 150))},
            {"label": "SOURCE_02", "before": _jpeg((120, 110, 100)), "after": _jpeg((190, 170, 140), (320, 240))},
        ]
    }
    spec = board_spec(lead, deliverable, images)
    assert spec["review_note"][-1] == "Versão 2 para sua análise"
    assert spec["what_stays"] == WHAT_STAYS_TEXT
    assert spec["detail_sources"] == ["SOURCE_01", "SOURCE_02"]
    assert spec["released"] is False
    board = _board_text(monkeypatch, lead, deliverable, images)
    pdf = " ".join(_pdf_text(lead, deliverable, images).split())
    flow = zone_map_text(zone_map_spec(lead, deliverable, images))
    for surface in (board, pdf, flow):
        assert "Versão 2 para sua análise" in surface
        assert find_time_sensitive(surface) == []
        assert "The FlowSpace Design Team" not in surface
    assert "FlowSpace Design System" in pdf
    assert TOTAL in pdf
    assert "Self-paced reset" in pdf
    assert "CHECK BEFORE BUYING" in pdf
    assert "Functional" in pdf and "Optional decorative" in pdf
    assert "Tested product link" in pdf and "Reference search" in pdf
    assert "measure before buying" in pdf.lower()
    assert "Living Room" in pdf
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
    assert fills
    assert min(fills) >= MIN_PAGE_FILL
    assert len(PdfReader(io.BytesIO(build_pdf(lead=lead, deliverable=deliverable, images=images))).pages) == len(fills)


def test_regenerate_endpoint_bumps_version_and_does_not_email(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DB_NAME", "flowspace_test")
    import server

    class _Coll:
        def __init__(self):
            self.docs = {}

        async def find_one(self, query, proj=None):
            key = query.get("id") or query.get("lead_id")
            doc = self.docs.get(key)
            return dict(doc) if doc else None

        async def update_one(self, query, update, upsert=False):
            key = query.get("id") or query.get("lead_id")
            doc = self.docs.setdefault(key, {})
            if "id" in query:
                doc.setdefault("id", query["id"])
            if "lead_id" in query:
                doc.setdefault("lead_id", query["lead_id"])
            doc.update(update.get("$set") or {})

    class _DB:
        def __init__(self):
            self.leads = _Coll()
            self.deliverables = _Coll()

    db = _DB()
    db.leads.docs[LEAD_ID] = _lead()
    stored = _deliverable(package_version=None, source_afters=[{"label": "SOURCE_01", "after_url": "/api/uploads/photo/abc"}])
    stored.pop("package_version")
    db.deliverables.docs[LEAD_ID] = stored

    def _boom(*_args, **_kwargs):
        raise AssertionError("regenerate must not email")

    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "send_blueprint", _boom)
    result = asyncio.run(server.regenerate_package(LEAD_ID, True))
    assert result["emailed"] is False
    assert result["package_version"] == 2
    assert result["version_label"] == "Versão 2 para sua análise"
    assert result["package_status"] == "review"
    assert result["pieces"]["board"].endswith("/deliverable/board")
    assert result["pieces"]["zone_map"].endswith("/deliverable/zone-map")
    assert result["pieces"]["pdf"].endswith("/deliverable/pdf")
    saved = db.deliverables.docs[LEAD_ID]
    assert saved["package_version"] == 2
    assert saved["package_status"] == "review"
    assert saved["design_plan_approved"] is False
    assert saved["source_afters"][0]["label"] == "SOURCE_01"
    assert "Playpen" not in [zone["title"] for zone in saved["zones"]]
    lead = db.leads.docs[LEAD_ID]
    assert lead["email_sent"] is False
    assert lead["status"] == "review"
    assert lead["package_status"] != "final"
    # Nothing has been emailed, so a second regenerate keeps Versão 2.
    again = asyncio.run(server.regenerate_package(LEAD_ID, True))
    assert again["package_version"] == 2
    assert again["version_label"] == "Versão 2 para sua análise"
    assert db.deliverables.docs[LEAD_ID]["package_version"] == 2
    assert "sent_for_review" not in db.deliverables.docs[LEAD_ID]


def test_regenerate_keeps_versao_2_until_a_copy_is_sent(monkeypatch):
    """Lead 4a2f3284 has not been sent V2, even if a regenerate already stored 3."""
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DB_NAME", "flowspace_test")
    import server

    class _Coll:
        def __init__(self):
            self.docs = {}

        async def find_one(self, query, proj=None):
            key = query.get("id") or query.get("lead_id")
            doc = self.docs.get(key)
            return dict(doc) if doc else None

        async def update_one(self, query, update, upsert=False):
            key = query.get("id") or query.get("lead_id")
            doc = self.docs.setdefault(key, {})
            if "id" in query:
                doc.setdefault("id", query["id"])
            if "lead_id" in query:
                doc.setdefault("lead_id", query["lead_id"])
            doc.update(update.get("$set") or {})

    class _DB:
        def __init__(self):
            self.leads = _Coll()
            self.deliverables = _Coll()

    db = _DB()
    db.leads.docs[LEAD_ID] = _lead()
    db.deliverables.docs[LEAD_ID] = _deliverable(package_version=3)
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "send_blueprint", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not email")))
    monkeypatch.setattr(server, "send_draft_package", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not email")))

    result = asyncio.run(server.regenerate_package(LEAD_ID, True))
    assert result["package_version"] == 2
    assert result["version_label"] == "Versão 2 para sua análise"
    assert result["emailed"] is False
    assert db.deliverables.docs[LEAD_ID]["package_version"] == 2
    assert "sent_for_review" not in db.deliverables.docs[LEAD_ID]

    db.deliverables.docs[LEAD_ID]["sent_for_review"] = 2
    db.deliverables.docs[LEAD_ID]["package_version"] = 2
    after_send = asyncio.run(server.regenerate_package(LEAD_ID, True))
    assert after_send["package_version"] == 3
    assert after_send["version_label"] == "Versão 3 para sua análise"
    assert db.deliverables.docs[LEAD_ID]["sent_for_review"] == 2
    stayed = asyncio.run(server.regenerate_package(LEAD_ID, True))
    assert stayed["package_version"] == 3
    assert stayed["version_label"] == "Versão 3 para sua análise"


def test_send_records_the_emailed_version_without_bumping_it(monkeypatch):
    monkeypatch.setenv("MONGO_URL", "mongodb://localhost:27017")
    monkeypatch.setenv("DB_NAME", "flowspace_test")
    import server

    lead = _lead()
    deliverable = _deliverable(package_version=2, package_status="review")
    saved = {}

    class _Coll:
        async def update_one(self, query, update, upsert=False):
            saved.update(update.get("$set") or {})

    class _DB:
        leads = _Coll()
        deliverables = _Coll()

    async def _inputs(_lead_id, _request):
        return lead, deliverable, {}

    async def _sent(**_kwargs):
        return True, None

    monkeypatch.setattr(server, "db", _DB())
    monkeypatch.setattr(server, "_blueprint_render_inputs", _inputs)
    monkeypatch.setattr(server, "build_pdf", lambda **_kw: b"%PDF")
    monkeypatch.setattr(server, "build_image_board", lambda **_kw: b"png")
    monkeypatch.setattr(server, "build_zone_map", lambda **_kw: b"png")
    monkeypatch.setattr(server, "draft_send_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "final_email_block_reason", lambda _d: None)
    monkeypatch.setattr(server, "send_draft_package", _sent)
    monkeypatch.setattr(server, "send_blueprint", _sent)

    class _Request:
        query_params = {}

    draft = asyncio.run(server.send_draft_package_endpoint(LEAD_ID, _Request(), to=None, _=True))
    assert draft["sent_for_review"] == 2
    assert draft["package_version"] == 2
    assert saved["sent_for_review"] == 2
    assert "package_version" not in saved

    final = asyncio.run(server.send_final_package(LEAD_ID, _Request(), _=True))
    assert final["sent_for_review"] == 2
    assert final["package_version"] == 2
    assert final["package_status"] == "final"
    assert saved["sent_for_review"] == 2
    assert saved["package_status"] == "final"
