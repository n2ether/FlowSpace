"""Living room Version 2: the lead's Room Flow record, the board caption, and measure-first rows."""
from design_plan_standards import BOARD_SHOPPING_CAPTION, SHOPPING_DISCLAIMER
from image_board import board_spec
from package_facts import apply_measurement_rule
from room_flow import load_record, record_view_names, resolve_room_flow, validate_room_flow

LEAD = {"id": "4a2f3284-6628-4bda-9952-6f5de13ec936", "name": "Camila Sales", "space_type": "living_room"}
NURSERY = {"id": "9dbedfba-81fc-45e0-b99d-36e0a1de01bb", "name": "Camila Sales", "space_type": "nursery"}


def test_record_draws_the_real_fixed_points():
    flow = load_record(LEAD["id"])
    assert flow and validate_room_flow(flow) == []
    assert flow["outline_source"] == "approximate"  # nothing measured yet
    assert flow["window"]["wall"] == flow["door"]["wall"] == 0  # front door shares the window wall
    assert [z["title"] for z in flow["zones"]] == ["Living", "Dining", "Entry Path", "Play"]
    labels = {item["label"] for item in flow["furniture"]}
    assert {"TV CONSOLE", "SECTIONAL", "DINING TABLE", "PLAYPEN"} <= labels
    assert record_view_names(LEAD) == ["Whole area", "TV and dining", "Couch and front door"]
    assert resolve_room_flow(LEAD, {})["zones"][3]["title"] == "Play"


def test_board_caption_points_to_the_guide_except_nursery():
    assert board_spec(LEAD, {"lead_id": LEAD["id"]}, {})["shop_note"] == BOARD_SHOPPING_CAPTION
    assert BOARD_SHOPPING_CAPTION.startswith("Representative examples for reference. Full shopping detail")
    assert board_spec(NURSERY, {"lead_id": NURSERY["id"]}, {})["shop_note"] == SHOPPING_DISCLAIMER


def test_unmeasured_baskets_and_frames_stay_measure_first_without_a_size():
    doc = {"shopping_list": [
        {"name": "Natural jute storage basket, medium, handles", "qty": 2, "price": 18},
        {"name": "Three-piece framed botanical print set", "qty": 1, "price": 85},
        {"name": "Small ceramic catch-all dish", "qty": 1, "price": 12},
    ]}
    apply_measurement_rule({"id": "x", "space_type": "living_room"}, doc)
    flags = [bool(item.get("measure_first")) for item in doc["shopping_list"]]
    assert flags == [True, True, False]


def _guide_text(lead, deliverable):
    import io

    from pypdf import PdfReader

    from pdf_generator import build_pdf

    pdf = build_pdf(lead=lead, deliverable=deliverable, images={})
    return " ".join(" ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages).split())


def test_guide_only_explains_link_kinds_it_prints():
    from design_plan_standards import LINK_REFERENCE_NOTE, LINK_TESTED_NOTE, link_kind_note
    from tests.test_living_room_package import _deliverable, _lead

    assert link_kind_note(set()) == ""
    assert link_kind_note({"reference"}) == LINK_REFERENCE_NOTE
    assert link_kind_note({"tested", "reference"}) == f"{LINK_TESTED_NOTE} {LINK_REFERENCE_NOTE}"

    unverified = _deliverable()
    for link in unverified["shopping_links"]:
        link["verified"] = False
    text = _guide_text(_lead(), unverified)
    assert "Tested product links open" not in text
    assert "Tested product link" not in text
    assert "Reference searches open" in text

    tested = _guide_text(_lead(), _deliverable())
    assert "Tested product links open the exact product page we checked" in tested


def _pdf_fonts(pdf):
    import io

    from pypdf import PdfReader

    found = set()
    for page in PdfReader(io.BytesIO(pdf)).pages:
        for font in ((page.get("/Resources") or {}).get("/Font") or {}).values():
            font = font.get_object()
            descriptor = font.get("/FontDescriptor")
            embedded = bool(descriptor) and any(
                key in descriptor.get_object() for key in ("/FontFile", "/FontFile2", "/FontFile3")
            )
            found.add((str(font.get("/BaseFont")), embedded or font.get("/Subtype") == "/Type0"))
    return found


def test_guide_and_draft_watermark_embed_every_font():
    from draft_watermark import watermark_pdf
    from pdf_generator import build_pdf
    from tests.test_living_room_package import _deliverable, _lead

    pdf = build_pdf(lead=_lead(), deliverable=_deliverable(), images={})
    for doc in (pdf, watermark_pdf(pdf)):
        fonts = _pdf_fonts(doc)
        assert fonts and all(embedded for _name, embedded in fonts), fonts
        assert not any("Helvetica" in name or "Times" in name for name, _ in fonts)
        assert any("Montserrat" in name for name, _ in fonts)


def test_admin_edit_keeps_per_item_measure_tags(monkeypatch):
    from fastapi.testclient import TestClient

    import server
    from tests.test_member_auth import FakeDB

    fake = FakeDB()
    fake.leads.docs.append({"id": LEAD["id"], "name": "Camila Sales", "email": "c@example.com", "space_type": "living_room"})
    fake.deliverables.docs.append(
        {
            "lead_id": LEAD["id"],
            "shopping_list": [
                {"name": "Jute basket", "qty": 2, "price": 18, "measure_first": True, "short_name": "Basket"},
                {"name": "Frame set", "qty": 1, "price": 85, "measure_first": True},
            ],
        }
    )
    monkeypatch.setattr(server, "db", fake)

    async def no_seed():
        return None

    monkeypatch.setattr(server, "seed_gallery_if_empty", no_seed)
    body = {
        "lead_id": LEAD["id"],
        "shopping_list": [
            # The editor round-trips the tag it received...
            {"name": "Jute basket", "qty": 3, "price": 18, "measure_first": True, "short_name": "Basket"},
            # ...and an older client that drops it must not erase it.
            {"name": "Frame set", "qty": 1, "price": 80},
            {"name": "Ceramic dish", "qty": 1, "price": 12},
        ],
    }
    with TestClient(server.app) as c:
        r = c.put(f"/api/admin/leads/{LEAD['id']}/deliverable", json=body, headers={"X-Admin-Token": server.ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    saved = {item["name"]: item for item in fake.deliverables.docs[0]["shopping_list"]}
    assert saved["Jute basket"]["measure_first"] is True and saved["Jute basket"]["qty"] == 3
    assert saved["Jute basket"]["short_name"] == "Basket"
    assert saved["Frame set"]["measure_first"] is True and saved["Frame set"]["price"] == 80
    assert "measure_first" not in saved["Ceramic dish"]
    returned = {item["name"]: item for item in r.json()["shopping_list"]}
    assert returned["Frame set"]["measure_first"] is True


def test_zone_anchor_keeps_tv_upper_case():
    from image_board import _sentence_case, _zone_cards

    assert _sentence_case("TV CONSOLE + SECTIONAL") == "TV console + sectional"
    assert _sentence_case("BENCH + MIRROR") == "Bench + mirror"
    flow = resolve_room_flow(LEAD, {})
    cards = _zone_cards(LEAD, {}, flow)
    assert cards[0]["object"].startswith("TV console")
    assert not any("Tv " in card["object"] for card in cards)


def test_draft_header_line_sits_clear_of_the_logo():
    import io

    from pypdf import PdfReader

    from draft_watermark import watermark_pdf
    from pdf_generator import build_pdf
    from tests.test_living_room_package import _deliverable, _lead

    pdf = watermark_pdf(build_pdf(lead=_lead(), deliverable=_deliverable(), images={}))
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    width = float(page.mediabox.width)
    spots = []

    def visit(text, cm, tm, font, size):
        if "in review, not final" in text:
            spots.append(cm[4] + tm[4])

    page.extract_text(visitor_text=visit)
    assert spots, "header line missing"
    # The logo and wordmark end ~100pt from the left edge; the line starts well past them.
    assert all(x > 120 for x in spots), spots
    assert all(x < width - 120 for x in spots), spots
