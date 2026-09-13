"""
Canonical image slots for ``build_pdf(lead=, deliverable=, images=)``.

Live automation (Claude → FLUX → PDF → Resend) and the admin PDF route
must populate these keys with raw image **bytes** (JPEG/PNG). URLs are
resolved *before* ``build_pdf`` — the generator never fetches.

Keys
----
front_view : bytes | None
    Page-1 hero. Successful FLUX (Kontext / text-to-image) organized render.
    When this is missing, the hero is a branded mint placeholder unless
    ``front_view_kind="original"`` and bytes are the customer's photo.
front_view_kind : str
    ``organized`` — FLUX / admin organized render (default when bytes exist).
    ``original`` — customer photo used as a labeled interim hero because
    FLUX failed. Prefer this over an empty mint panel when a photo exists.
    ``placeholder`` — no bytes; mint “Organized view coming soon” panel.
floor_plan : bytes | None
    Optional. Embed only a real plan the pipeline actually produced.
    Never invent a floor plan or measured drawing.
view_1, view_2, view_3 : bytes | None
    Optional detail-card photos (admin extra renders). Unused slots stay
    as labeled zone cards — we do not duplicate the hero into every card.
customer_photos : list[bytes]
    Original customer uploads for later reference pages (photos after the
    first still get their own pages). The first upload is also ``before``.
before : bytes | None
    Last-page **Before** panel — the customer's original uploaded photo.
    Derived from this key, else the first ``customer_photos`` item, else
    ``front_view`` when ``front_view_kind="original"``.
after : bytes | None
    Last-page **After** panel — the FLUX organized render. Derived from
    this key, else ``front_view`` when ``front_view_kind="organized"``.
    Never invented. If FLUX failed, the panel is an honest empty state.

UX when FLUX fails
------------------
Show the customer's original photo as the hero, banner-labeled so it is
not mistaken for the organized render. If no original exists, keep the
branded mint placeholder. Either path is a soft fail — the PDF and
email still go out. The last page still shows Before | After: the
available photo plus a labeled unavailable panel (no fake after).
"""
from __future__ import annotations

import io
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Slots whose values are a single image payload (not a list).
IMAGE_BYTE_KEYS = (
    "front_view",
    "floor_plan",
    "view_1",
    "view_2",
    "view_3",
    "before",
    "after",
)
HERO_KINDS = ("organized", "original", "placeholder")

HERO_BANNER_ORGANIZED = "ORGANIZED VIEW — YOUR REAL SPACE, RE-ZONED"
HERO_BANNER_ORIGINAL = "YOUR PHOTO — ORGANIZED VIEW UNAVAILABLE"
HERO_PLACEHOLDER_LABEL = "Organized view coming soon"
HERO_PLACEHOLDER_SUB = "Your photo, re-zoned — visual arrives with the plan"

COMPARE_BEFORE_BANNER = "BEFORE — YOUR PHOTO"
COMPARE_AFTER_BANNER = "AFTER — ORGANIZED VIEW"
COMPARE_BEFORE_EMPTY = "Original photo not provided"
COMPARE_BEFORE_EMPTY_SUB = "We compare against the photo you uploaded"
COMPARE_AFTER_EMPTY = "Organized view unavailable"
COMPARE_AFTER_EMPTY_SUB = "We do not invent an organized after"


def coerce_image_bytes(src: Any) -> Optional[bytes]:
    """Accept bytes-like payloads; treat empty / URLs / other types as missing."""
    if src is None:
        return None
    if isinstance(src, memoryview):
        src = src.tobytes()
    if isinstance(src, bytearray):
        src = bytes(src)
    if isinstance(src, bytes):
        return src or None
    return None


def coerce_photo_list(src: Any) -> List[bytes]:
    if not src:
        return []
    if isinstance(src, (bytes, bytearray, memoryview)):
        one = coerce_image_bytes(src)
        return [one] if one else []
    if isinstance(src, Sequence) and not isinstance(src, (str, bytes, bytearray)):
        out: List[bytes] = []
        for item in src:
            b = coerce_image_bytes(item)
            if b:
                out.append(b)
        return out
    return []


def choose_hero(
    *,
    organized_bytes: Optional[bytes],
    original_bytes: Optional[bytes],
) -> Tuple[Optional[bytes], str]:
    """Prefer FLUX organized render; else labeled original; else placeholder."""
    organized = coerce_image_bytes(organized_bytes)
    if organized:
        return organized, "organized"
    original = coerce_image_bytes(original_bytes)
    if original:
        return original, "original"
    return None, "placeholder"


def as_gridfs_source(data: bytes) -> io.BytesIO:
    """File-like wrapper so Motor ``upload_from_stream`` always gets ``.read()``."""
    return io.BytesIO(coerce_image_bytes(data) or b"")


def assemble_pdf_images(
    *,
    hero_bytes: Optional[bytes] = None,
    hero_kind: str = "placeholder",
    floor_plan: Optional[bytes] = None,
    view_1: Optional[bytes] = None,
    view_2: Optional[bytes] = None,
    view_3: Optional[bytes] = None,
    before: Optional[bytes] = None,
    after: Optional[bytes] = None,
    customer_photos: Optional[Iterable[Any]] = None,
    fetched: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the ``images=`` dict ``build_pdf`` expects.

    In-memory hero bytes win over a GridFS re-fetch (``fetched['front_view']``).
    Detail / floor-plan slots use the explicit args, then ``fetched``.
    ``before`` / ``after`` feed the last-page comparison; they are derived
    from the hero + first customer photo when omitted.
    """
    fetched = dict(fetched or {})
    kind = (hero_kind or "placeholder").strip().lower()
    if kind not in HERO_KINDS:
        kind = "organized" if hero_bytes or fetched.get("front_view") else "placeholder"

    front = coerce_image_bytes(hero_bytes) or coerce_image_bytes(fetched.get("front_view"))
    if not front:
        kind = "placeholder"
    elif kind == "placeholder":
        kind = "organized"

    photos = coerce_photo_list(
        customer_photos if customer_photos is not None else fetched.get("customer_photos")
    )
    before_b = coerce_image_bytes(before) or coerce_image_bytes(fetched.get("before"))
    after_b = coerce_image_bytes(after) or coerce_image_bytes(fetched.get("after"))
    if not before_b:
        if photos:
            before_b = photos[0]
        elif kind == "original" and front:
            before_b = front
    if not after_b and kind == "organized" and front:
        after_b = front

    return {
        "front_view": front,
        "front_view_kind": kind,
        "floor_plan": coerce_image_bytes(floor_plan) or coerce_image_bytes(fetched.get("floor_plan")),
        "view_1": coerce_image_bytes(view_1) or coerce_image_bytes(fetched.get("view_1")),
        "view_2": coerce_image_bytes(view_2) or coerce_image_bytes(fetched.get("view_2")),
        "view_3": coerce_image_bytes(view_3) or coerce_image_bytes(fetched.get("view_3")),
        "before": before_b,
        "after": after_b,
        "customer_photos": photos,
    }


def normalize_pdf_images(images: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Coerce a caller-supplied ``images`` mapping into the canonical shape."""
    images = dict(images or {})
    return assemble_pdf_images(
        hero_bytes=images.get("front_view"),
        hero_kind=str(images.get("front_view_kind") or "placeholder"),
        floor_plan=images.get("floor_plan"),
        view_1=images.get("view_1"),
        view_2=images.get("view_2"),
        view_3=images.get("view_3"),
        before=images.get("before"),
        after=images.get("after"),
        customer_photos=images.get("customer_photos"),
    )
