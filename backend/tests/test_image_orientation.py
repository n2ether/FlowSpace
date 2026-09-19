"""EXIF / gravity-correct helpers — no live APIs."""
import io

from PIL import Image

from image_orientation import (
    UnreadableImage,
    jpeg_for_vision,
    normalize_photo_bytes,
    read_exif_orientation,
    rotate_photo_bytes,
    upright_bytes,
)


def _jpeg_with_exif(*, size=(80, 40), color=(20, 80, 200), orientation=1) -> bytes:
    img = Image.new("RGB", size, color)
    # Distinct ceiling stripe on the pixel-top so we can assert transpose.
    for x in range(size[0]):
        img.putpixel((x, 0), (250, 20, 20))
        img.putpixel((x, 1), (250, 20, 20))
    exif = img.getexif()
    exif[274] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, exif=exif)
    return buf.getvalue()


def test_orientation_6_transposes_landscape_pixels_to_portrait():
    raw = _jpeg_with_exif(size=(80, 40), orientation=6)
    before = Image.open(io.BytesIO(raw))
    assert before.size == (80, 40)
    assert read_exif_orientation(before) == 6

    upright, info = normalize_photo_bytes(raw)
    assert info["applied"] is True
    assert info["changed"] is True
    assert info["exif_orientation"] == 6
    assert info["width"] == 40
    assert info["height"] == 80
    assert info["is_portrait"] is True
    assert info["is_landscape"] is False

    after = Image.open(io.BytesIO(upright))
    assert after.size == (40, 80)
    assert read_exif_orientation(after) == 1


def test_orientation_1_does_not_count_as_changed():
    raw = _jpeg_with_exif(size=(60, 80), orientation=1)
    upright, info = normalize_photo_bytes(raw)
    assert info["applied"] is False
    assert info["changed"] is False
    assert info["width"] == 60
    assert info["height"] == 80
    after = Image.open(io.BytesIO(upright))
    assert after.size == (60, 80)


def test_unreadable_bytes_raise():
    try:
        normalize_photo_bytes(b"not-an-image")
        raise AssertionError("expected UnreadableImage")
    except UnreadableImage:
        pass
    assert upright_bytes(b"not-an-image") == b"not-an-image"
    assert upright_bytes(None) is None


def test_upright_bytes_keeps_already_correct_jpeg():
    raw = _jpeg_with_exif(size=(60, 80), orientation=1)
    assert upright_bytes(raw) is raw


def test_rotate_90_swaps_sides():
    raw = _jpeg_with_exif(size=(80, 40), orientation=1)
    rotated = rotate_photo_bytes(raw, 90)
    img = Image.open(io.BytesIO(rotated))
    assert img.size == (40, 80)


def test_jpeg_for_vision_downscales():
    raw = _jpeg_with_exif(size=(400, 200), orientation=1)
    small = jpeg_for_vision(raw, max_side=100)
    img = Image.open(io.BytesIO(small))
    assert max(img.size) <= 100
