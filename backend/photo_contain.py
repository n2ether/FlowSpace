"""Contain-fit for room photos.

The Blueprint board, companion PDF, and review contact sheet all place
customer photos and organized afters through this helper. The whole frame
is scaled uniformly so it fits inside the slot. Aspect ratio and field of
view stay as they are in the file. Nothing is cover-cropped to fill a wider
or shorter box.
"""
from __future__ import annotations

from typing import Tuple


def contain_rect(
    src_w: float,
    src_h: float,
    max_w: float,
    max_h: float,
) -> Tuple[float, float, float, float]:
    """Return ``(offset_x, offset_y, width, height)`` inside ``max_w`` × ``max_h``.

    The rectangle is the largest uniform scale of ``src_w`` × ``src_h`` that
    fits. Offsets center it. A zero or negative input collapses to an empty
    placement rather than stretching one axis.
    """
    if src_w <= 0 or src_h <= 0 or max_w <= 0 or max_h <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    scale = min(max_w / float(src_w), max_h / float(src_h))
    dw = float(src_w) * scale
    dh = float(src_h) * scale
    if dw > max_w:
        dw = float(max_w)
    if dh > max_h:
        dh = float(max_h)
    ox = (float(max_w) - dw) / 2.0
    oy = (float(max_h) - dh) / 2.0
    return (ox, oy, dw, dh)


def contain_pixels(
    src_w: int,
    src_h: int,
    max_w: int,
    max_h: int,
) -> Tuple[int, int, int, int]:
    """Integer ``(offset_x, offset_y, width, height)`` for a PIL paste.

    Rounding never exceeds the slot, so the paste cannot spill and the full
    source still fits.
    """
    if max_w <= 0 or max_h <= 0:
        return (0, 0, 0, 0)
    _ox, _oy, dw, dh = contain_rect(src_w, src_h, max_w, max_h)
    dw_i = max(1, int(round(dw))) if dw > 0 else 0
    dh_i = max(1, int(round(dh))) if dh > 0 else 0
    if dw_i > max_w:
        dw_i = max_w
    if dh_i > max_h:
        dh_i = max_h
    if dw_i <= 0 or dh_i <= 0:
        return (0, 0, 0, 0)
    ox_i = max(0, (max_w - dw_i) // 2)
    oy_i = max(0, (max_h - dh_i) // 2)
    return (ox_i, oy_i, dw_i, dh_i)


def frame_size(aspect_w_over_h: float, max_w: int, max_h: int) -> Tuple[int, int]:
    """Largest integer frame of ``width / height == aspect`` inside the max box.

    Used when the slot itself should match the photo, so contain has nothing
    left to letterbox and a wide fixed crop box is never allocated.
    """
    if max_w <= 0 or max_h <= 0:
        return (max(1, max_w), max(1, max_h))
    aspect = float(aspect_w_over_h) if aspect_w_over_h and aspect_w_over_h > 0 else 1.0
    width = int(max_w)
    height = max(1, int(round(width / aspect)))
    if height > max_h:
        height = int(max_h)
        width = max(1, int(round(height * aspect)))
    if width > max_w:
        width = int(max_w)
    return (max(1, width), max(1, height))
