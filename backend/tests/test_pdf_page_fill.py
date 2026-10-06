"""Every companion-guide page is complete: no near-empty pages, type sizes unchanged."""
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from pdf_generator import MIN_PAGE_FILL, _styles, build_pdf, companion_page_fill
from pdf_images import assemble_pdf_images
from shopping_links import load_record

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_sample_blueprint import (  # noqa: E402
    _synthetic_organized_jpeg,
    _synthetic_original_jpeg,
    load_fixture,
)

NURSERY = json.loads((ROOT / "fixtures" / "nursery_nico.json").read_text(encoding="utf-8"))


def _jpeg(color, size):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _pairs(count, size, missing_last=False):
    pairs = []
    for index in range(count):
        after = None if (missing_last and index == count - 1) else _jpeg((210, 196, 180 - index * 10), size)
        pairs.append({"before": _jpeg((150, 120 + index * 10, 110), size), "after": after})
    return {"source_pairs": pairs}


def _curated():
    items = load_record(NURSERY["lead"]["id"])["items"]
    return {
        **NURSERY["deliverable"],
        "shopping_list": [{"name": it["name"], "qty": it["qty"], "price": it["price"]} for it in items],
    }


def _hero():
    original, organized = _synthetic_original_jpeg(), _synthetic_organized_jpeg()
    return assemble_pdf_images(
        hero_bytes=organized, hero_kind="organized", before=original, after=organized, customer_photos=[original]
    )


def _before_only():
    original = _synthetic_original_jpeg()
    return assemble_pdf_images(hero_bytes=original, hero_kind="original", before=original, after=None)


GARAGE_LEAD, GARAGE = load_fixture()

CASES = {
    "nursery curated, four portrait views": (NURSERY["lead"], _curated(), _pairs(4, (900, 1200))),
    "nursery curated, four landscape views": (NURSERY["lead"], _curated(), _pairs(4, (1200, 900))),
    "nursery curated, one view missing": (NURSERY["lead"], _curated(), _pairs(4, (900, 1200), missing_last=True)),
    "nursery curated, no photos": (NURSERY["lead"], _curated(), {}),
    "nursery plan, single hero": (NURSERY["lead"], NURSERY["deliverable"], _hero()),
    "garage, single hero": (GARAGE_LEAD, GARAGE, _hero()),
    "garage, before only": (GARAGE_LEAD, GARAGE, _before_only()),
    "garage, no photos": (GARAGE_LEAD, GARAGE, {}),
    "garage, two items": (GARAGE_LEAD, {**GARAGE, "shopping_list": GARAGE["shopping_list"][:2]}, _hero()),
}


@pytest.mark.parametrize("name", list(CASES))
def test_no_companion_page_is_near_empty(name):
    lead, deliverable, images = CASES[name]
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
    assert fills, name
    assert MIN_PAGE_FILL >= 0.40
    for page, fill in enumerate(fills, 1):
        assert fill >= MIN_PAGE_FILL, f"{name}: page {page} is {fill:.0%} filled ({[round(f, 2) for f in fills]})"


def test_before_after_pages_fill_the_frame():
    lead, deliverable, images = CASES["nursery curated, four portrait views"]
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
    assert len(fills) == 6
    assert all(fill >= 0.85 for fill in fills[2:]), fills
    assert all(fill >= 0.70 for fill in fills[:2]), fills


def test_shopping_tail_shares_its_page_with_the_photos():
    """A list that spills a few rows does not strand them on their own sheet."""
    lead, deliverable, images = CASES["garage, single hero"]
    fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
    assert len(fills) == 2
    assert min(fills) >= 0.80, fills


def test_guide_type_is_not_shrunk():
    styles = _styles()
    assert styles["guideBody"].fontSize >= 12
    assert styles["guideH"].fontSize >= 14
    assert styles["shopItem"].fontSize >= 10.6
    assert styles["shopNote"].fontSize >= 10.6
    assert styles["shopTotal"].fontSize >= 12


def test_page_fill_matches_the_rendered_pdf_page_count():
    from pypdf import PdfReader

    for name, (lead, deliverable, images) in CASES.items():
        pdf = build_pdf(lead=lead, deliverable=deliverable, images=images)
        fills = companion_page_fill(lead=lead, deliverable=deliverable, images=images)
        assert len(PdfReader(io.BytesIO(pdf)).pages) == len(fills), name
