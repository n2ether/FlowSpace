"""Unit tests for Blueprint image-slot helpers (no Mongo / live API)."""
from pdf_images import (
    IMAGE_BYTE_KEYS,
    assemble_pdf_images,
    choose_hero,
    coerce_image_bytes,
    normalize_pdf_images,
)


def test_image_keys_document_hero_and_detail_slots():
    assert "front_view" in IMAGE_BYTE_KEYS
    assert "view_1" in IMAGE_BYTE_KEYS
    assert "view_2" in IMAGE_BYTE_KEYS
    assert "view_3" in IMAGE_BYTE_KEYS
    assert "floor_plan" in IMAGE_BYTE_KEYS
    assert "before" in IMAGE_BYTE_KEYS
    assert "after" in IMAGE_BYTE_KEYS


def test_coerce_rejects_urls_and_empty():
    assert coerce_image_bytes(None) is None
    assert coerce_image_bytes(b"") is None
    assert coerce_image_bytes("/api/uploads/photo/abc") is None
    assert coerce_image_bytes("https://example.com/x.jpg") is None
    assert coerce_image_bytes(b"\xff\xd8\xff") == b"\xff\xd8\xff"
    assert coerce_image_bytes(bytearray(b"png")) == b"png"


def test_choose_hero_prefers_flux_then_original():
    organized, kind = choose_hero(organized_bytes=b"flux", original_bytes=b"photo")
    assert (organized, kind) == (b"flux", "organized")

    original, kind = choose_hero(organized_bytes=None, original_bytes=b"photo")
    assert (original, kind) == (b"photo", "original")

    missing, kind = choose_hero(organized_bytes=None, original_bytes=None)
    assert (missing, kind) == (None, "placeholder")

    url_as_bytes, kind = choose_hero(organized_bytes="/api/x", original_bytes=b"photo")
    assert (url_as_bytes, kind) == (b"photo", "original")


def test_assemble_in_memory_hero_wins_over_fetched():
    images = assemble_pdf_images(
        hero_bytes=b"in-memory-flux",
        hero_kind="organized",
        fetched={"front_view": b"stale-gridfs", "view_1": b"detail"},
    )
    assert images["front_view"] == b"in-memory-flux"
    assert images["front_view_kind"] == "organized"
    assert images["view_1"] == b"detail"


def test_normalize_empty_images_is_placeholder():
    images = normalize_pdf_images({})
    assert images["front_view"] is None
    assert images["front_view_kind"] == "placeholder"
    assert images["customer_photos"] == []
    assert images["view_1"] is None
    assert images["before"] is None
    assert images["after"] is None


def test_assemble_derives_before_after_from_hero_and_photos():
    images = assemble_pdf_images(
        hero_bytes=b"flux",
        hero_kind="organized",
        customer_photos=[b"original", b"extra"],
    )
    assert images["before"] == b"original"
    assert images["after"] == b"flux"
    assert images["front_view"] == b"flux"

    only_original = assemble_pdf_images(hero_bytes=b"photo", hero_kind="original")
    assert only_original["before"] == b"photo"
    assert only_original["after"] is None  # never invent an after
