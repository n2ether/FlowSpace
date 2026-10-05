"""Conceptual Zone Map / Flow Plan — the standard FlowSpace room-flow layout.

One portrait page per project: brand header, project title and badge, a
top-down map of the room (outline, window, door, furniture, zones, clear
path), "The zones" column (one job per zone), the flow principle, a
"Why this helps" band, and a source-rule footer.

The plan is data, in metres. ``resolve_room_flow`` picks it from, in order:

1. ``deliverable["room_flow"]`` when the record carries one,
2. ``room_flows/<lead id>.json`` — a measured outline supplied for that lead,
3. a default drawn from the plan's zones, labelled as an approximate outline.

The badge, the map note, and the footer all read one outline phrase, so a
measured outline is never also called "not a measured plan", and an
approximate one never claims measurements. Furniture and zones are always
approximate. Customer pixels never carry SOURCE_/AFTER_ codes, a lead id,
or QA language; only the review banner (``review=True``) names the lead.
"""
from __future__ import annotations

import copy
import io
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

BACKEND = Path(__file__).resolve().parent
RECORDS_DIR = BACKEND / "room_flows"
FONTS_DIR = BACKEND / "fonts"

# Drawn at 2x the 717 x 1024 reference sheet. Layout numbers below are
# reference pixels and go through ``_s``.
REF_W, REF_H = 717, 1024
SCALE = 2
W, H = REF_W * SCALE, REF_H * SCALE

PAPER = (247, 241, 232)
CARD_EDGE = (221, 208, 190)
INK = (46, 44, 40)
MUTED = (104, 98, 90)
GREEN = (36, 72, 52)
GREEN_TEXT = (209, 228, 215)
CLAY = (160, 104, 70)
WALL = (36, 72, 52)
DOOR = (150, 62, 62)
FLOOR = (251, 248, 241)
WHY_FILL = (227, 229, 214)
MARK = (98, 112, 104)
WHITE = (255, 255, 255)

REVIEW_STATUS = "DRAFT. Review version. Not yet approved. Customer release held."
TAGLINE = "Clear space. Create flow. Live better."

ZONE_STYLES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "sleep": {"fill": (219, 233, 225), "ring": (70, 128, 108), "edge": (140, 152, 146)},
    "change": {"fill": (238, 226, 208), "ring": (168, 112, 74), "edge": (160, 148, 132)},
    "comfort": {"fill": (229, 229, 239), "ring": (88, 88, 138), "edge": (146, 146, 160)},
    "play": {"fill": (237, 231, 213), "ring": (138, 128, 88), "edge": (150, 146, 128)},
    "storage": {"fill": (232, 228, 216), "ring": (120, 112, 84), "edge": (150, 146, 128)},
    "work": {"fill": (226, 232, 236), "ring": (74, 102, 120), "edge": (140, 150, 156)},
}
_STYLE_CYCLE = ("sleep", "change", "comfort", "play")

FURNITURE_STYLES = {
    "dresser": {"fill": (237, 217, 192), "line": (124, 90, 60)},
    "crib": {"fill": (222, 236, 228), "line": GREEN},
    "rocker": {"fill": (217, 216, 237), "line": (84, 84, 124)},
    "basket": {"fill": (214, 175, 130), "line": (138, 98, 60)},
    "rug": {"fill": (234, 224, 202), "line": (150, 130, 100)},
    "block": {"fill": (232, 228, 218), "line": (110, 104, 94)},
}

_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


# ──────────────────────────── Plan data ─────────────────────────────


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def edge_length(outline: Sequence[Sequence[float]], index: int) -> float:
    a = outline[index]
    b = outline[(index + 1) % len(outline)]
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def outline_phrases(flow: Dict[str, Any]) -> Dict[str, str]:
    """Every sentence that describes the outline, from one source."""
    _credit = _clean(flow.get("outline_credit"))  # retained for measured-outline provenance
    if flow.get("outline_source") == "measured":
        return {
            "badge": "Measured room outline",
            "map_note": "Room outline based on your measurements. Furniture footprints and zones are approximate.",
            "map_footnote": "Room outline based on your measurements. Furniture footprints and zones are approximate.",
            "map_footnote_2": "Furniture footprints and zones are approximate.",
            "rule": "Room outline based on your measurements. Furniture footprints and zones are approximate.",
            "board_caption": "Room outline based on your measurements. Furniture footprints and zones are approximate.",
        }
    return {
        "badge": "Approximate room outline",
        "map_note": "Approximate room outline. Furniture footprints and zones are approximate.",
        "map_footnote": "Approximate room outline. Furniture footprints and zones are approximate.",
        "map_footnote_2": "Furniture footprints and zones are approximate.",
        "rule": "Approximate room outline. Furniture footprints and zones are approximate.",
        "board_caption": "Approximate room outline. Furniture footprints and zones are approximate.",
    }


def _zone_style_key(title: str, index: int) -> str:
    low = title.lower()
    for key, words in (
        ("sleep", ("sleep", "crib", "bed")),
        ("change", ("change", "diaper", "dress")),
        ("comfort", ("comfort", "feed", "rock", "seat", "read")),
        ("play", ("play", "movement", "floor")),
        ("storage", ("storage", "stor", "shelf", "bin")),
        ("work", ("work", "desk", "office", "landing")),
    ):
        if any(word in low for word in words):
            return key
    return _STYLE_CYCLE[index % len(_STYLE_CYCLE)]


def _short_title(title: str) -> str:
    words = [w for w in re.sub(r"\bzone\b", "", title, flags=re.I).replace("&", "+").split() if w]
    return " ".join(words[:3]) or "Zone"


def _first_sentence(text: str, fallback: str) -> str:
    text = _clean(text)
    if not text:
        return fallback
    sentence = re.split(r"(?<=[.!?])\s+", text)[0]
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


# Zone areas for an approximate outline, by count. Normalised 0..1 in a
# 1.0 x 1.15 room; window on the top wall, door low on the left wall.
_DEFAULT_AREAS = {
    1: ((0.30, 0.20, 0.92, 0.70),),
    2: ((0.08, 0.12, 0.46, 0.62), (0.56, 0.12, 0.92, 0.62)),
    3: ((0.08, 0.10, 0.44, 0.52), (0.58, 0.10, 0.92, 0.56), (0.52, 0.70, 0.92, 1.06)),
    4: (
        (0.58, 0.10, 0.92, 0.52),
        (0.08, 0.10, 0.42, 0.52),
        (0.62, 0.64, 0.92, 1.06),
        (0.30, 0.82, 0.56, 1.06),
    ),
}


def default_room_flow(lead: Dict[str, Any], deliverable: Dict[str, Any]) -> Dict[str, Any]:
    """Standard layout when no outline was supplied. Says it is approximate."""
    zones_in: List[Tuple[str, str]] = []
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            title, desc = _clean(zone.get("title")), _clean(zone.get("desc"))
        else:
            title, desc = _clean(zone), ""
        # The clear path is drawn as the route itself, not as a boxed zone.
        if title and not re.search(r"\b(circulation|walkway|walk path|clear path)\b", title, re.I):
            zones_in.append((title, desc))
    if not zones_in:
        zones_in = [("Daily use", ""), ("Storage", ""), ("Clear floor", "")]
    zones_in = zones_in[:4]
    areas = _DEFAULT_AREAS[len(zones_in)]
    zones = []
    for index, ((title, desc), area) in enumerate(zip(zones_in, areas)):
        short = _short_title(title)
        zones.append(
            {
                "id": _zone_style_key(title, index),
                "number": f"{index + 1:02d}",
                "title": short,
                "job": _first_sentence(desc, f"One clear home for {short.lower()}."),
                "map_label": short.upper(),
                "rect": list(area),
            }
        )
    seen: Dict[str, int] = {}
    for zone in zones:
        seen[zone["id"]] = seen.get(zone["id"], 0) + 1
        if seen[zone["id"]] > 1:
            zone["style"] = _STYLE_CYCLE[(int(zone["number"]) - 1) % len(_STYLE_CYCLE)]
            zone["id"] = f"{zone['id']}-{seen[zone['id']]}"
    titles = [z["title"].lower() for z in zones]
    subtitle = "A calmer flow for " + (
        ", ".join(titles[:-1]) + " & " + titles[-1] if len(titles) > 1 else titles[0]
    )
    return {
        "outline_source": "approximate",
        "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.15], [0.0, 1.15]],
        "walls": [{"label": "WINDOW WALL"}, {}, {}, {}],
        "window": {"wall": 0, "from_m": 0.35, "to_m": 0.65},
        "door": {"wall": 3, "from_m": 0.10, "to_m": 0.34},
        "zones": zones,
        "furniture": [],
        "path": [[0.04, 0.93], [0.36, 0.62], [0.52, 0.56]],
        "subtitle": subtitle,
        "flow_principle": ["Less visual noise.", "Fewer decisions.", "Easier resets."],
        "flow_note": "A clear route through the room makes everyday routines calmer.",
        "why_headline": "The room becomes easier to read, easier to reset, and easier to live in.",
        "why_note": "Environmental psychology in practice: visual calm, clear circulation, and one simple place for each recurring task.",
    }


def load_record(lead_id: str) -> Optional[Dict[str, Any]]:
    lead_id = _clean(lead_id)
    if not lead_id or not re.fullmatch(r"[A-Za-z0-9-]{8,64}", lead_id):
        return None
    path = RECORDS_DIR / f"{lead_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_room_flow(lead: Optional[Dict[str, Any]], deliverable: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    lead = lead or {}
    deliverable = deliverable or {}
    stored = deliverable.get("room_flow")
    if isinstance(stored, dict) and stored.get("outline"):
        return copy.deepcopy(stored)
    record = load_record(str(lead.get("id") or deliverable.get("lead_id") or ""))
    if record:
        return record
    return default_room_flow(lead, deliverable)


def validate_room_flow(flow: Dict[str, Any]) -> List[str]:
    """Issues that would make the map disagree with itself. Empty when sound."""
    issues: List[str] = []
    outline = flow.get("outline") or []
    walls = flow.get("walls") or []
    if len(outline) < 3:
        return ["outline needs at least three corners"]
    if walls and len(walls) != len(outline):
        issues.append("walls must list one entry per outline edge")
    for index, wall in enumerate(walls[: len(outline)]):
        stated = wall.get("length_m") if isinstance(wall, dict) else None
        if stated is not None and abs(edge_length(outline, index) - float(stated)) > 0.015:
            issues.append(f"wall {index} is drawn {edge_length(outline, index):.2f} m but labelled {float(stated):.2f} m")
    if flow.get("outline_source") == "measured" and not any(
        isinstance(w, dict) and w.get("length_m") for w in walls
    ):
        issues.append("a measured outline must carry wall lengths")
    for item in list(flow.get("furniture") or []) + list(flow.get("zones") or []):
        for x, y in _shape_corners(item):
            if not point_in_polygon((x, y), outline, tolerance=0.02):
                issues.append(f"{item.get('id') or item.get('label')} sits outside the room outline")
                break
    numbers = [str(z.get("number")) for z in flow.get("zones") or []]
    if len(numbers) != len(set(numbers)):
        issues.append("zone numbers repeat")
    return issues


def _shape_corners(item: Dict[str, Any]) -> List[Tuple[float, float]]:
    if item.get("rect"):
        l, t, r, b = [float(v) for v in item["rect"]]
        return [(l, t), (r, t), (r, b), (l, b)]
    if item.get("ellipse"):
        cx, cy, rx, ry = [float(v) for v in item["ellipse"]]
        return [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in [i * math.pi / 8 for i in range(16)]]
    return []


def point_in_polygon(point: Tuple[float, float], poly: Sequence[Sequence[float]], tolerance: float = 0.0) -> bool:
    x, y = point
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = float(poly[i][0]), float(poly[i][1])
        x2, y2 = float(poly[(i + 1) % n][0]), float(poly[(i + 1) % n][1])
        if (y1 > y) != (y2 > y):
            cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cross:
                inside = not inside
    if inside or tolerance <= 0:
        return inside
    for i in range(n):
        if _segment_distance(point, poly[i], poly[(i + 1) % n]) <= tolerance:
            return True
    return False


def _segment_distance(p, a, b) -> float:
    ax, ay, bx, by = float(a[0]), float(a[1]), float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy or 1e-9
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _wall_label(flow: Dict[str, Any], index: int) -> str:
    walls = flow.get("walls") or []
    wall = walls[index] if index < len(walls) and isinstance(walls[index], dict) else {}
    if wall.get("door"):
        return ""
    label = _clean(wall.get("label"))
    if label:
        return label
    if wall.get("length_m") is not None:
        return f"{float(wall['length_m']):.2f} m"
    return ""


def wall_labels(flow: Dict[str, Any]) -> List[str]:
    return [label for label in (_wall_label(flow, i) for i in range(len(flow.get("outline") or []))) if label]


def source_rule(flow: Dict[str, Any], source_views: int) -> str:
    count = int(source_views or flow.get("source_views") or 0)
    if count >= 2:
        based = f"Based on the {_NUMBER_WORDS.get(count, str(count))} source views"
    elif count == 1:
        based = "Based on your room photo"
    else:
        based = "Based on your room photos"
    return f"{based} \u2022 Same room, same retained furniture \u2022 {outline_phrases(flow)['rule']}"


def zone_map_spec(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    images: Optional[Dict[str, Any]] = None,
    *,
    final: bool = False,
) -> Dict[str, Any]:
    """All copy and geometry the zone map paints. Rendering reads only this."""
    from blueprint_consistency import prepare_deliverable
    from pdf_generator import customer_project_title, plan_title

    lead = lead or {}
    doc = prepare_deliverable(lead, deliverable)
    flow = resolve_room_flow(lead, {**doc, "room_flow": (deliverable or {}).get("room_flow")})
    pairs = (images or {}).get("source_pairs") or []
    views = len([p for p in pairs if isinstance(p, dict)]) if isinstance(pairs, list) else 0
    title = customer_project_title(lead, doc) or plan_title(lead.get("space_type"))
    phrases = outline_phrases(flow)
    status = "ROOM FLOW PLAN" if final else "DRAFT CONCEPT"
    return {
        "title": title.upper(),
        "subtitle": _clean(flow.get("subtitle")) or "A calmer flow for the room you already have",
        "badge_status": status,
        "badge_outline": phrases["badge"],
        "phrases": phrases,
        "flow": flow,
        "zones": list(flow.get("zones") or [])[:4],
        "flow_principle": [str(x) for x in (flow.get("flow_principle") or [])][:3],
        "flow_note": _clean(flow.get("flow_note")),
        "why_headline": _clean(flow.get("why_headline")),
        "why_note": _clean(flow.get("why_note")),
        "source_rule": source_rule(flow, views),
        "footer_status": "ROOM FLOW PLAN" if final else "DRAFT CONCEPT FOR REVIEW",
        "final": final,
    }


def zone_map_text(spec: Dict[str, Any]) -> str:
    """Every string the customer zone map paints (without the review banner)."""
    flow = spec["flow"]
    parts = [
        "FlowSpace",
        TAGLINE.upper(),
        spec["title"],
        spec["subtitle"].upper(),
        spec["badge_status"],
        spec["badge_outline"],
        "01 ROOM FLOW + FUNCTIONAL ZONES",
        spec["phrases"]["map_note"],
        spec["phrases"]["map_footnote"],
        spec["phrases"]["map_footnote_2"],
        "02 THE ZONES",
        "Each zone has one job.",
        "FLOW PRINCIPLE",
        *spec["flow_principle"],
        spec["flow_note"],
        "03 WHY THIS HELPS",
        spec["why_headline"],
        spec["why_note"],
        "SOURCE RULE",
        spec["source_rule"],
        spec["footer_status"],
        "CLEAR PATH",
    ]
    for zone in spec["zones"]:
        parts += [str(zone.get("number") or ""), str(zone.get("title") or "").upper(), str(zone.get("job") or "")]
        parts.append(str(zone.get("map_label") or ""))
    for item in flow.get("furniture") or []:
        parts.append(str(item.get("label") or ""))
    parts.extend(wall_labels(flow))
    return "\n".join(p for p in parts if p)


# ──────────────────────────── Drawing helpers ─────────────────────────────

_FONT_FILES = {
    "sans": ("Inter-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    "sans-medium": ("Inter-Medium.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    "sans-semibold": ("Inter-SemiBold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    "sans-bold": ("Inter-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    "serif": ("Fraunces-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
    "serif-medium": ("Fraunces-Medium.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
}
_fonts: Dict[Tuple[str, int], ImageFont.ImageFont] = {}


def font(kind: str, size: float) -> ImageFont.ImageFont:
    px = max(6, int(round(size)))
    key = (kind, px)
    if key in _fonts:
        return _fonts[key]
    face: Optional[ImageFont.ImageFont] = None
    for candidate in _FONT_FILES.get(kind, _FONT_FILES["sans"]):
        path = Path(candidate) if candidate.startswith("/") else FONTS_DIR / candidate
        try:
            face = ImageFont.truetype(str(path), size=px)
            break
        except OSError:
            continue
    _fonts[key] = face or ImageFont.load_default()
    return _fonts[key]


def _s(value: float) -> int:
    return int(round(value * SCALE))


def _spaced_width(draw: ImageDraw.ImageDraw, text: str, face, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(draw.textlength(ch, font=face) for ch in text) + tracking * (len(text) - 1)


def spaced_text(draw: ImageDraw.ImageDraw, xy, text: str, face, fill, tracking: float = 0.0, anchor: str = "l") -> None:
    """Letter-spaced caps. ``anchor`` is l, m, or r on the x axis."""
    x, y = xy
    if tracking <= 0:
        width = draw.textlength(text, font=face)
    else:
        width = _spaced_width(draw, text, face, tracking)
    if anchor == "m":
        x -= width / 2
    elif anchor == "r":
        x -= width
    if tracking <= 0:
        draw.text((x, y), text, font=face, fill=fill)
        return
    for ch in text:
        draw.text((x, y), ch, font=face, fill=fill)
        x += draw.textlength(ch, font=face) + tracking


def wrap(draw: ImageDraw.ImageDraw, text: str, face, width: float) -> List[str]:
    words = _clean(text).split()
    lines: List[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=face) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _dashed(draw: ImageDraw.ImageDraw, points: Sequence[Tuple[float, float]], fill, width: int, dash: float, gap: float) -> None:
    period = max(1e-6, dash + gap)
    walked = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg <= 0:
            continue
        ux, uy = (x1 - x0) / seg, (y1 - y0) / seg
        # Dash starts sit at multiples of ``period`` along the whole polyline.
        k = math.floor(walked / period)
        while True:
            start = k * period - walked
            end = start + dash
            if start >= seg:
                break
            a, b = max(0.0, start), min(seg, end)
            if b > a:
                draw.line((x0 + ux * a, y0 + uy * a, x0 + ux * b, y0 + uy * b), fill=fill, width=width)
            k += 1
        walked += seg


def _ellipse_points(cx: float, cy: float, rx: float, ry: float, n: int = 96) -> List[Tuple[float, float]]:
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return pts + [pts[0]]


def _rotated_text(base: Image.Image, center: Tuple[float, float], text: str, face, fill, angle: float, tracking: float = 0.0) -> None:
    probe = ImageDraw.Draw(base)
    width = int(_spaced_width(probe, text, face, tracking)) + 8
    height = int(face.size * 1.5) + 4
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    spaced_text(ImageDraw.Draw(layer), (4, 2), text, face, fill + (255,), tracking)
    layer = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    base.alpha_composite(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)))


# ──────────────────────────── Floor plan ─────────────────────────────


class _Mapper:
    def __init__(self, outline: Sequence[Sequence[float]], box: Tuple[float, float, float, float]):
        xs = [float(p[0]) for p in outline]
        ys = [float(p[1]) for p in outline]
        self.min_x, self.min_y = min(xs), min(ys)
        span_x = max(1e-6, max(xs) - self.min_x)
        span_y = max(1e-6, max(ys) - self.min_y)
        x0, y0, x1, y1 = box
        self.k = min((x1 - x0) / span_x, (y1 - y0) / span_y)
        self.ox = x0 + ((x1 - x0) - span_x * self.k) / 2
        self.oy = y0 + ((y1 - y0) - span_y * self.k) / 2

    def pt(self, x: float, y: float) -> Tuple[float, float]:
        return (self.ox + (float(x) - self.min_x) * self.k, self.oy + (float(y) - self.min_y) * self.k)

    def rect(self, r: Sequence[float]) -> Tuple[float, float, float, float]:
        a = self.pt(r[0], r[1])
        b = self.pt(r[2], r[3])
        return (a[0], a[1], b[0], b[1])

    def m(self, metres: float) -> float:
        return metres * self.k


def _style_for(zone: Dict[str, Any]) -> Dict[str, Tuple[int, int, int]]:
    key = str(zone.get("style") or zone.get("id") or "").split("-")[0]
    return ZONE_STYLES.get(key, ZONE_STYLES["play"])


def _draw_zone_area(base: Image.Image, mp: _Mapper, zone: Dict[str, Any], u: float) -> None:
    draw = ImageDraw.Draw(base)
    style = _style_for(zone)
    width = max(1, int(round(1.2 * u)))
    if zone.get("rect"):
        box = mp.rect(zone["rect"])
        draw.rectangle(box, fill=style["fill"])
        x0, y0, x1, y1 = box
        _dashed(draw, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], style["edge"], width, 5 * u, 3.5 * u)
    elif zone.get("ellipse"):
        cx, cy, rx, ry = zone["ellipse"]
        c = mp.pt(cx, cy)
        box = (c[0] - mp.m(rx), c[1] - mp.m(ry), c[0] + mp.m(rx), c[1] + mp.m(ry))
        draw.ellipse(box, fill=style["fill"])
        _dashed(draw, _ellipse_points(c[0], c[1], mp.m(rx), mp.m(ry)), style["edge"], width, 5 * u, 3.5 * u)


def _draw_rug(base: Image.Image, mp: _Mapper, item: Dict[str, Any], u: float) -> None:
    cx, cy, rx, ry = item["ellipse"]
    c = mp.pt(cx, cy)
    prx, pry = mp.m(rx), mp.m(ry)
    style = FURNITURE_STYLES["rug"]
    draw = ImageDraw.Draw(base)
    draw.ellipse((c[0] - prx, c[1] - pry, c[0] + prx, c[1] + pry), fill=style["fill"], outline=style["line"], width=max(1, int(1.5 * u)))
    inner_rx, inner_ry = prx * 0.84, pry * 0.80
    grid = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = max(6.0, mp.m(0.11))
    x = c[0] - inner_rx
    while x <= c[0] + inner_rx:
        gd.line((x, c[1] - inner_ry, x, c[1] + inner_ry), fill=(196, 180, 150, 255), width=1)
        x += step
    y = c[1] - inner_ry
    while y <= c[1] + inner_ry:
        gd.line((c[0] - inner_rx, y, c[0] + inner_rx, y), fill=(196, 180, 150, 255), width=1)
        y += step
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).ellipse((c[0] - inner_rx, c[1] - inner_ry, c[0] + inner_rx, c[1] + inner_ry), fill=255)
    grid.putalpha(Image.composite(grid.getchannel("A"), Image.new("L", base.size, 0), mask))
    base.alpha_composite(grid)
    draw = ImageDraw.Draw(base)
    draw.ellipse(
        (c[0] - inner_rx, c[1] - inner_ry, c[0] + inner_rx, c[1] + inner_ry),
        outline=style["line"],
        width=max(1, int(u)),
    )


def _draw_furniture(base: Image.Image, mp: _Mapper, item: Dict[str, Any], u: float) -> None:
    kind = str(item.get("kind") or "block")
    if kind == "rug":
        _draw_rug(base, mp, item, u)
        return
    if not item.get("rect"):
        return
    draw = ImageDraw.Draw(base)
    style = FURNITURE_STYLES.get(kind, FURNITURE_STYLES["block"])
    x0, y0, x1, y1 = mp.rect(item["rect"])
    w, h = x1 - x0, y1 - y0
    line_w = max(1, int(round(1.6 * u)))
    if kind == "crib":
        draw.rounded_rectangle((x0, y0, x1, y1), radius=6 * u, fill=style["fill"], outline=style["line"], width=max(2, int(2.2 * u)))
        ix0, iy0, ix1, iy1 = x0 + w * 0.1, y0 + h * 0.06, x1 - w * 0.1, y1 - h * 0.06
        draw.rounded_rectangle((ix0, iy0, ix1, iy1), radius=4 * u, outline=(110, 136, 120), width=max(1, int(u)))
        slats = 6
        for i in range(1, slats + 1):
            sx = ix0 + (ix1 - ix0) * i / (slats + 1)
            draw.line((sx, iy0 + h * 0.05, sx, iy1 - h * 0.05), fill=(130, 150, 138), width=max(1, int(u)))
    elif kind == "dresser":
        draw.rounded_rectangle((x0, y0, x1, y1), radius=5 * u, fill=style["fill"], outline=style["line"], width=line_w)
        drawers = int(item.get("drawers") or 6)
        rows = 3 if drawers >= 3 else max(1, drawers)
        cols = max(1, drawers // rows)
        for r in range(1, rows):
            ry = y0 + h * r / rows
            draw.line((x0 + w * 0.12, ry, x1 - w * 0.12, ry), fill=(170, 140, 110), width=max(1, int(u)))
        knob = max(1.5, 1.8 * u)
        for r in range(rows):
            ky = y0 + h * (r + 0.5) / rows
            for col in range(cols):
                kx = x0 + w * (col + 0.5) / cols
                draw.ellipse((kx - knob, ky - knob, kx + knob, ky + knob), fill=style["line"])
    elif kind == "rocker":
        draw.rounded_rectangle((x0, y0, x1, y1), radius=min(w, h) * 0.32, fill=style["fill"], outline=style["line"], width=max(2, int(2.2 * u)))
        draw.arc(
            (x0 + w * 0.2, y0 + h * 0.32, x1 - w * 0.2, y1 + h * 0.1),
            start=200,
            end=340,
            fill=style["line"],
            width=max(2, int(1.8 * u)),
        )
    elif kind == "basket":
        draw.arc((x0 + w * 0.25, y0 - h * 0.35, x1 - w * 0.25, y0 + h * 0.35), start=180, end=360, fill=style["line"], width=line_w)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=4 * u, fill=style["fill"], outline=style["line"], width=line_w)
    else:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=5 * u, fill=style["fill"], outline=style["line"], width=line_w)


def _draw_path(base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float) -> None:
    pts = [mp.pt(p[0], p[1]) for p in flow.get("path") or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 2:
        return
    band = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(band).line(pts, fill=(222, 160, 128, 120), width=max(6, int(15 * u)), joint="curve")
    base.alpha_composite(band)
    _dashed(ImageDraw.Draw(base), pts, (168, 76, 64), max(1, int(round(1.4 * u))), 5 * u, 4 * u)


def _edge_points(mp: _Mapper, outline, index: int, start_m: Optional[float] = None, end_m: Optional[float] = None):
    a = outline[index]
    b = outline[(index + 1) % len(outline)]
    length = edge_length(outline, index) or 1.0
    t0 = 0.0 if start_m is None else float(start_m) / length
    t1 = 1.0 if end_m is None else float(end_m) / length
    pa = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
    pb = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
    return mp.pt(*pa), mp.pt(*pb)


def _outward_normal(outline, index: int) -> Tuple[float, float]:
    """Unit normal pointing out of the room (screen coordinates, y down)."""
    a = outline[index]
    b = outline[(index + 1) % len(outline)]
    dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    length = math.hypot(dx, dy) or 1.0
    area = 0.0
    for i in range(len(outline)):
        x1, y1 = outline[i]
        x2, y2 = outline[(i + 1) % len(outline)]
        area += float(x1) * float(y2) - float(x2) * float(y1)
    # Clockwise on screen (positive area with y down) puts the outside on the left.
    if area > 0:
        return (dy / length, -dx / length)
    return (-dy / length, dx / length)


def _draw_walls(base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float) -> None:
    draw = ImageDraw.Draw(base)
    outline = flow["outline"]
    door = flow.get("door") or {}
    door_wall = door.get("wall")
    wall_w = max(3, int(round(4.2 * u)))
    n = len(outline)
    for i in range(n):
        a, b = _edge_points(mp, outline, i)
        if i == door_wall and door.get("from_m") is None:
            continue
        if i == door_wall:
            pa, pb = _edge_points(mp, outline, i, door.get("from_m"), door.get("to_m"))
            draw.line((a, pa), fill=WALL, width=wall_w)
            draw.line((pb, b), fill=WALL, width=wall_w)
            continue
        draw.line((a, b), fill=WALL, width=wall_w)
    r = wall_w / 2
    for i in range(n):
        x, y = mp.pt(*outline[i])
        draw.ellipse((x - r, y - r, x + r, y + r), fill=WALL)


def _draw_door(base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float) -> None:
    door = flow.get("door") or {}
    if door.get("wall") is None:
        return
    outline = flow["outline"]
    index = int(door["wall"])
    pa, pb = _edge_points(mp, outline, index, door.get("from_m"), door.get("to_m"))
    draw = ImageDraw.Draw(base)
    draw.line((pa, pb), fill=DOOR, width=max(2, int(round(2.4 * u))))
    nx, ny = _outward_normal(outline, index)
    leaf = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    mark_w = max(1, int(1.3 * u))
    # Swing marks at both jambs, as in the reference: one into the room, one outside.
    _dashed(draw, [pb, (pb[0] - nx * leaf * 0.42, pb[1] - ny * leaf * 0.42)], DOOR, mark_w, 3.5 * u, 3 * u)
    _dashed(draw, [pa, (pa[0] + nx * leaf * 0.32, pa[1] + ny * leaf * 0.32)], DOOR, mark_w, 3.5 * u, 3 * u)


def _draw_window(base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float) -> None:
    window = flow.get("window") or {}
    if window.get("wall") is None:
        return
    pa, pb = _edge_points(mp, flow["outline"], int(window["wall"]), window.get("from_m"), window.get("to_m"))
    draw = ImageDraw.Draw(base)
    half = 4.5 * u
    if abs(pb[1] - pa[1]) < abs(pb[0] - pa[0]):
        box = (min(pa[0], pb[0]), pa[1] - half, max(pa[0], pb[0]), pa[1] + half)
    else:
        box = (pa[0] - half, min(pa[1], pb[1]), pa[0] + half, max(pa[1], pb[1]))
    draw.rounded_rectangle(box, radius=3 * u, fill=(184, 216, 214), outline=WALL, width=max(1, int(1.4 * u)))
    if box[2] - box[0] > box[3] - box[1]:
        for x in (box[0] + 6 * u, box[2] - 6 * u):
            draw.line((x, box[1] + 1.5 * u, x, box[3] - 1.5 * u), fill=WALL, width=max(1, int(1.2 * u)))


def _draw_dimensions(
    base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float, min_px: float
) -> List[Tuple[float, float, float, float]]:
    """Wall-length labels outside the outline. Returns each label's painted box."""
    outline = flow["outline"]
    draw = ImageDraw.Draw(base)
    face = font("sans-medium", max(7.5 * u, min_px))
    boxes: List[Tuple[float, float, float, float]] = []
    for index in range(len(outline)):
        text = _wall_label(flow, index)
        if not text:
            continue
        a, b = _edge_points(mp, outline, index)
        nx, ny = _outward_normal(outline, index)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        horizontal = abs(b[1] - a[1]) < abs(b[0] - a[0]) * 0.5
        vertical = abs(b[0] - a[0]) < abs(b[1] - a[1]) * 0.5
        offset = 18 * u if horizontal else 16 * u
        cx, cy = mid[0] + nx * offset, mid[1] + ny * offset
        tracking = 0.9 * u if horizontal else 0.6 * u
        half_w = _spaced_width(draw, text, face, tracking) / 2
        half_h = face.size * 0.75
        if horizontal:
            spaced_text(draw, (cx, cy - face.size / 2), text, face, MUTED, tracking, anchor="m")
            boxes.append((cx - half_w, cy - half_h, cx + half_w, cy + half_h))
        elif vertical:
            angle = 90 if nx < 0 else -90
            _rotated_text(base, (cx, cy), text, face, MUTED, angle, tracking)
            draw = ImageDraw.Draw(base)
            boxes.append((cx - half_h, cy - half_w, cx + half_h, cy + half_w))
        else:
            spaced_text(draw, (cx, cy - face.size / 2), text, face, MUTED, tracking, anchor="m")
            boxes.append((cx - half_w, cy - half_h, cx + half_w, cy + half_h))
    return boxes


def _label_safe_box(
    box: Tuple[float, float, float, float], flow: Dict[str, Any], u: float, min_px: float
) -> Tuple[float, float, float, float]:
    """Shrink ``box`` so wall labels drawn outside the outline still land inside it."""
    if not wall_labels(flow):
        return box
    size = max(7.5 * u, min_px)
    pad_y = 18 * u + size * 0.75 + 4
    pad_x = 16 * u + size * 0.75 + 4
    x0, y0, x1, y1 = box
    if x1 - x0 <= 2 * pad_x + 40 or y1 - y0 <= 2 * pad_y + 40:
        return box
    return (x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y)


def _label_block(draw, center_x: float, top: float, lines: Sequence[Tuple[str, Any, Tuple[int, int, int], float]]) -> None:
    y = top
    for text, face, fill, tracking in lines:
        spaced_text(draw, (center_x, y), text, face, fill, tracking, anchor="m")
        y += face.size * 1.45


def _draw_labels(base: Image.Image, mp: _Mapper, flow: Dict[str, Any], u: float, compact: bool, min_px: float) -> None:
    draw = ImageDraw.Draw(base)
    zones = {str(z.get("id")): z for z in flow.get("zones") or []}
    label_face = font("sans-bold", max(8 * u, min_px))
    zone_face = font("sans", max(6.8 * u, min_px - 1))
    labelled_zones = set()
    for item in flow.get("furniture") or []:
        label = _clean(item.get("label"))
        if not label:
            continue
        zone = zones.get(str(item.get("zone") or ""))
        lines = [(label, label_face, INK, 0.7 * u)]
        if zone and not compact and zone.get("map_label"):
            lines.append((str(zone["map_label"]), zone_face, MUTED, 0.9 * u))
            labelled_zones.add(str(zone.get("id")))
        if item.get("label_at"):
            cx, cy = mp.pt(*item["label_at"])
            top = cy - label_face.size * 0.6
        elif item.get("rect"):
            x0, _y0, x1, y1 = mp.rect(item["rect"])
            cx, top = (x0 + x1) / 2, y1 + 5 * u
        else:
            continue
        _label_block(draw, cx, top, lines)
    for zone in flow.get("zones") or []:
        if str(zone.get("id")) in labelled_zones:
            continue
        if compact and flow.get("furniture"):
            continue
        text = str(zone.get("map_label") or zone.get("title") or "").upper()
        if not text:
            continue
        if zone.get("rect"):
            x0, y0, x1, y1 = mp.rect(zone["rect"])
        elif zone.get("ellipse"):
            cx_, cy_, rx, ry = zone["ellipse"]
            x0, y0, x1, y1 = mp.rect((cx_ - rx, cy_ - ry, cx_ + rx, cy_ + ry))
        else:
            continue
        face = label_face
        lines = wrap(draw, text, face, max(20, (x1 - x0) - 8 * u))[:2]
        _label_block(draw, (x0 + x1) / 2, (y0 + y1) / 2 - face.size * 0.75 * len(lines), [(ln, face, INK, 0.6 * u) for ln in lines])
    if flow.get("path"):
        at = flow.get("path_label_at")
        if at:
            px, py = mp.pt(*at)
        else:
            pts = flow["path"]
            mid = pts[len(pts) // 2]
            px, py = mp.pt(mid[0], mid[1] - 0.12)
        face = font("sans-medium", max(7 * u, min_px - 1))
        spaced_text(draw, (px, py - face.size / 2), "CLEAR PATH", face, MUTED, 0.9 * u, anchor="m")


def draw_floor_plan(
    base: Image.Image,
    box: Tuple[float, float, float, float],
    flow: Dict[str, Any],
    *,
    compact: bool = False,
    min_px: float = 0.0,
    contain_labels: bool = False,
) -> Dict[str, Any]:
    """Top-down map of ``flow`` fitted inside ``box``. Returns the fitted geometry.

    ``base`` must be RGBA. ``compact`` drops the zone sub-labels for small cards.
    ``contain_labels`` keeps the wall-length labels inside ``box`` too, for a
    card where other content sits right outside it.
    """
    outline = flow.get("outline") or []
    if len(outline) < 3:
        return {}
    # Strokes and type are in reference pixels; the reference map box is 327 x 337.
    unit = max(0.6, min((box[2] - box[0]) / 327.0, (box[3] - box[1]) / 337.0))
    if contain_labels:
        box = _label_safe_box(box, flow, unit, min_px)
    mp = _Mapper(outline, box)
    poly = [mp.pt(*p) for p in outline]
    ImageDraw.Draw(base).polygon(poly, fill=FLOOR)
    zones = list(flow.get("zones") or [])
    for zone in zones:
        if zone.get("rect"):
            _draw_zone_area(base, mp, zone, unit)
    for zone in zones:
        if zone.get("ellipse"):
            _draw_zone_area(base, mp, zone, unit)
    furniture = list(flow.get("furniture") or [])
    for item in furniture:
        if item.get("kind") == "rug":
            _draw_furniture(base, mp, item, unit)
    _draw_path(base, mp, flow, unit)
    for item in furniture:
        if item.get("kind") != "rug":
            _draw_furniture(base, mp, item, unit)
    _draw_walls(base, mp, flow, unit)
    _draw_window(base, mp, flow, unit)
    _draw_door(base, mp, flow, unit)
    _draw_labels(base, mp, flow, unit, compact, min_px)
    label_boxes = _draw_dimensions(base, mp, flow, unit, min_px)
    return {
        "room": tuple(int(v) for v in (min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly))),
        "polygon": poly,
        "unit": unit,
        "label_boxes": label_boxes,
    }


# ──────────────────────────── Page ─────────────────────────────


def _draw_mark(draw: ImageDraw.ImageDraw, x: float, y: float, size: float, color) -> None:
    """House outline with the flow wave — the corrected FlowSpace mark."""
    s = size
    w = max(2, int(round(s / 22)))
    peak = (x + s * 0.5, y)
    left_eave, right_eave = (x, y + s * 0.42), (x + s, y + s * 0.42)
    left_foot, right_foot = (x, y + s * 0.95), (x + s, y + s * 0.95)
    draw.line([left_foot, left_eave, peak, right_eave, right_foot], fill=color, width=w, joint="curve")
    draw.line([right_foot, (x + s * 0.62, right_foot[1])], fill=color, width=w)
    draw.arc((x + s * 0.02, y + s * 0.52, x + s * 0.56, y + s * 1.12), start=200, end=330, fill=color, width=w)
    draw.arc((x + s * 0.40, y + s * 0.42, x + s * 0.98, y + s * 0.98), start=20, end=160, fill=color, width=w)


def _draw_eye(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GREEN)
    ew, eh = r * 0.62, r * 0.36
    width = max(2, int(r / 9))
    draw.arc((cx - ew, cy - eh * 1.9, cx + ew, cy + eh * 1.3), start=30, end=150, fill=WHITE, width=width)
    draw.arc((cx - ew, cy - eh * 1.3, cx + ew, cy + eh * 1.9), start=210, end=330, fill=WHITE, width=width)
    pr = r * 0.17
    draw.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=WHITE)


def _draw_review_banner(base: Image.Image, lead_id: str) -> int:
    draw = ImageDraw.Draw(base)
    height = _s(30)
    draw.rectangle((0, 0, W, height), fill=GREEN)
    text = REVIEW_STATUS + (f"  Lead {lead_id}" if lead_id else "")
    face = font("sans-semibold", _s(8.5))
    draw.text((_s(22), (height - face.size) / 2 - 2), text, font=face, fill=WHITE)
    return height


def build_zone_map(
    *,
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    images: Optional[Dict[str, Any]] = None,
    final: bool = False,
    review: bool = False,
    lead_id: str = "",
) -> bytes:
    """Render the Conceptual Zone Map / Flow Plan PNG.

    ``review=True`` adds the admin banner (status and lead id) above the
    customer sheet. The customer sheet itself never names the lead.
    """
    spec = zone_map_spec(lead, deliverable, images, final=final)
    banner_h = _s(30) if review else 0
    sheet = Image.new("RGBA", (W, H), PAPER + (255,))
    _paint_sheet(sheet, spec)
    if review:
        page = Image.new("RGBA", (W, H + banner_h), PAPER + (255,))
        page.alpha_composite(sheet, (0, banner_h))
        _draw_review_banner(page, lead_id or str((lead or {}).get("id") or ""))
        sheet = page
    out = io.BytesIO()
    sheet.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def _paint_sheet(base: Image.Image, spec: Dict[str, Any]) -> None:
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((_s(22), _s(22), _s(695), _s(1002)), radius=_s(8), outline=CARD_EDGE, width=_s(1))

    # Brand header
    word_face = font("sans", _s(46))
    draw.text((_s(70), _s(33)), "FlowSpace", font=word_face, fill=(28, 36, 44))
    mark_x = max(_s(333), _s(70) + draw.textlength("FlowSpace", font=word_face) + _s(14))
    _draw_mark(draw, mark_x, _s(34), _s(48), MARK)
    draw.line((_s(70), _s(95), _s(384), _s(95)), fill=(150, 146, 140), width=max(1, _s(0.7)))
    spaced_text(draw, (_s(93), _s(103)), TAGLINE.upper(), font("sans-medium", _s(10.5)), INK, _s(1.4))

    # Title, subtitle, badge
    badge_w = max(
        _s(118),
        int(draw.textlength(spec["badge_outline"], font=font("sans", _s(8.5)))) + _s(26),
        int(_spaced_width(draw, spec["badge_status"], font("sans-medium", _s(8)), _s(1.1))) + _s(26),
    )
    badge = (_s(668) - badge_w, _s(146), _s(668), _s(186))
    title_face = font("serif", _s(33))
    title = spec["title"]
    title_max = badge[0] - _s(49) - _s(16)
    while draw.textlength(title, font=title_face) > title_max and title_face.size > _s(20):
        title_face = font("serif", title_face.size - 2)
    draw.text((_s(49), _s(140)), title, font=title_face, fill=GREEN)
    spaced_text(draw, (_s(50), _s(182)), spec["subtitle"].upper(), font("sans", _s(9.5)), CLAY, _s(1.1))
    draw.rounded_rectangle(badge, radius=_s(8), fill=GREEN)
    spaced_text(draw, (badge[0] + _s(13), badge[1] + _s(8)), spec["badge_status"], font("sans-medium", _s(8)), GREEN_TEXT, _s(1.1))
    draw.text((badge[0] + _s(13), badge[1] + _s(22)), spec["badge_outline"], font=font("sans", _s(8.5)), fill=WHITE)
    draw.rectangle((_s(49), _s(203), _s(668), _s(205)), fill=GREEN)

    # 01 Map
    phrases = spec["phrases"]
    spaced_text(draw, (_s(69), _s(242)), "01 ROOM FLOW + FUNCTIONAL ZONES", font("sans-medium", _s(9.5)), GREEN, _s(1.2))
    draw.text((_s(69), _s(259)), phrases["map_note"], font=font("sans", _s(8.5)), fill=INK)
    draw_floor_plan(base, (_s(118), _s(300), _s(445), _s(637)), spec["flow"])
    draw = ImageDraw.Draw(base)
    note_face = font("sans", _s(7.2))
    draw.text((_s(97), _s(661)), phrases["map_footnote"], font=note_face, fill=INK)
    draw.text((_s(97), _s(677)), phrases["map_footnote_2"], font=note_face, fill=INK)

    # 02 Zones column
    col_x, col_r = _s(522), _s(668)
    spaced_text(draw, (col_x, _s(242)), "02 THE ZONES", font("sans-medium", _s(9.5)), GREEN, _s(1.2))
    draw.text((col_x, _s(263)), "Each zone has one job.", font=font("sans", _s(8.5)), fill=INK)
    draw.line((col_x, _s(287), col_r - _s(20), _s(287)), fill=CARD_EDGE, width=_s(0.8))
    y = _s(296)
    for zone in spec["zones"]:
        style = _style_for(zone)
        r = _s(10.5)
        cx, cy = col_x + _s(17), y + _s(11)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=style["fill"], outline=style["ring"], width=_s(1.2))
        num_face = font("sans-semibold", _s(8))
        number = str(zone.get("number") or "")
        draw.text((cx - draw.textlength(number, font=num_face) / 2, cy - num_face.size * 0.62), number, font=num_face, fill=GREEN)
        spaced_text(draw, (col_x + _s(36), y), str(zone.get("title") or "").upper(), font("sans-bold", _s(8.6)), GREEN, _s(0.7))
        ty = y + _s(16)
        for line in wrap(draw, str(zone.get("job") or ""), font("sans", _s(7.8)), col_r - col_x - _s(50))[:3]:
            draw.text((col_x + _s(36), ty), line, font=font("sans", _s(7.8)), fill=INK)
            ty += _s(13.5)
        y += _s(72)
    rule_y = max(y - _s(14), _s(576))
    draw.line((col_x, rule_y, col_r - _s(20), rule_y), fill=CARD_EDGE, width=_s(0.8))
    spaced_text(draw, (col_x, rule_y + _s(19)), "FLOW PRINCIPLE", font("sans", _s(7.8)), CLAY, _s(1.3))
    py = rule_y + _s(36)
    for line in spec["flow_principle"]:
        draw.text((col_x, py), line, font=font("serif", _s(15)), fill=GREEN)
        py += _s(22)
    py += _s(6)
    for line in wrap(draw, spec["flow_note"], font("sans", _s(7.8)), col_r - col_x - _s(8))[:4]:
        draw.text((col_x, py), line, font=font("sans", _s(7.8)), fill=INK)
        py += _s(13.5)

    # 03 Why this helps
    band = (_s(49), _s(757), _s(668), _s(873))
    draw.rounded_rectangle(band, radius=_s(16), fill=WHY_FILL)
    spaced_text(draw, (_s(71), _s(781)), "03 WHY THIS HELPS", font("sans", _s(7.8)), CLAY, _s(1.3))
    head_face = font("serif", _s(18.5))
    hy = _s(798)
    for line in wrap(draw, spec["why_headline"], head_face, _s(340))[:2]:
        draw.text((_s(71), hy), line, font=head_face, fill=GREEN)
        hy += _s(25)
    ny = max(hy + _s(4), _s(850))
    for line in wrap(draw, spec["why_note"], font("sans", _s(8.2)), _s(350))[:2]:
        draw.text((_s(71), ny), line, font=font("sans", _s(8.2)), fill=INK)
        ny += _s(14)
    _draw_eye(draw, _s(609), _s(817), _s(28))

    # Footer
    draw.rectangle((_s(49), _s(915), _s(668), _s(917)), fill=GREEN)
    spaced_text(draw, (_s(49), _s(933)), "SOURCE RULE", font("sans", _s(7.3)), CLAY, _s(1.2))
    rule_face = font("sans", _s(7.8))
    rule_text = spec["source_rule"]
    while draw.textlength(rule_text, font=rule_face) > _s(540) and rule_face.size > _s(6):
        rule_face = font("sans", rule_face.size - 1)
    draw.text((_s(49), _s(949)), rule_text, font=rule_face, fill=INK)
    brand_face = font("sans-bold", _s(9))
    draw.text((_s(668) - draw.textlength("FlowSpace", font=brand_face), _s(948)), "FlowSpace", font=brand_face, fill=GREEN)
    spaced_text(draw, (_s(49), _s(982)), spec["footer_status"], font("sans", _s(6.8)), MUTED, _s(1.1))
