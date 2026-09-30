"""
AI-assisted deliverable drafting via Anthropic Claude.

Takes a lead's questionnaire answers and returns a structured JSON design plan
that maps directly to the Deliverable model.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import anthropic

from blueprint_layers import DRAFTER_SCHEMA_SNIPPET, derive_layers, merge_layers
from image_orientation import jpeg_for_vision, upright_bytes

logger = logging.getLogger(__name__)

MODEL_NAME = "claude-sonnet-4-5"
# Sonnet drafts with blueprint layers run long. 4096 tokens cut Camila's
# Kids' room plan mid-string (~16k chars) and the raw JSONDecodeError left
# the paid lead in ERROR. 8192 finishes a normal plan; repair still covers
# a cut-off reply.
DRAFT_MAX_TOKENS = 8192
_DRAFT_ATTEMPTS = 2
_RETRY_HINT = (
    "\n\nYour previous reply was truncated or was not valid JSON. "
    "Return ONE compact JSON object and nothing else — no markdown fences, no commentary. "
    "Keep every list to at most 3 short items so the object finishes."
)
_SUBSTANTIVE_KEYS = (
    "intro",
    "summary",
    "notes",
    "zones",
    "needs",
    "strategy",
    "action_plan",
    "shopping_list",
    "benefits",
    "blueprint_layers",
)

SYSTEM_PROMPT = """You are a senior home-organization designer for FlowSpace.
We focus on storage for mental health — a calm, organized space reduces anxiety,
overwhelm, and decision fatigue.

Primary spaces: closets, garages, laundry rooms, pantries, mudrooms, and storage
areas the customer actually uploaded. Write for THAT space_type. Do not produce
a bedroom redesign unless space_type is bedroom.

Given a customer's questionnaire answers, produce a thoughtful, calm,
practical organization plan (zones, shopping list, action steps, benefits)
AND the six Brain layers. Layers are customer-visible — not private notes.

Return ONLY valid JSON matching exactly this schema (no prose, no markdown,
no code fences) — keep every list short and concrete (max ~5 items each):

{
  "intro": string,
  "needs": [string],
  "zones": [{"title": string, "desc": string}],
  "wall_color_name": string,
  "wall_color_code": string,
  "wall_color_hex": string,
  "wall_color_note": string,
  "shopping_list": [{"name": string, "qty": number, "price": number}],
  "budget_note": string,
  "strategy": [string],
  "action_plan": [string],
  "benefits": [string],
  "notes": string,
  "summary": string,
  "attachment_note": string,""" + DRAFTER_SCHEMA_SNIPPET + """
}

Style: calm, friendly, second-person. Prices in USD (IKEA/Target ranges).
wall_color_hex is empty when keeping existing paint; otherwise a valid 7-char hex.
shopping_list.price is per-unit number.
Always weave in the mental-health angle: clutter causes stress, organization creates calm.

Hard rules:
- Windows and room dimensions must stay ~95% faithful to the customer's real space. Never invent footage, window counts, openings, or measured callouts.
- Do not propose new walls, windows, doors, or construction. Organize with bins, furniture, and layout.
- Never place shelves, cabinets, racks, or storage over or in front of windows or doors. Openings stay fully visible and in their photo location.
- Ceiling fans, lights, vents, and fixtures stay on the ceiling. Do not relocate them onto walls.
- Treat the attached photo as gravity-correct: floor at the bottom, ceiling at the top. Do not describe the room as rotated.
- Wall paint is OPTIONAL and OFF by default. Default wall_color_name to "Keep existing / no paint change", wall_color_code "", wall_color_hex "", wall_color_note "No paint change — keep the existing wall color from the photo." Only fill a real paint color if the customer explicitly asked to paint or change wall color. Do not invent optional Warm Taupe / accent-wall colors that imply a makeover. Color preferences describe textiles and accessories only, never walls. Never put "paint the walls" in action_plan. The visual transform will not apply paint unless they asked.
- notes must mention ~95% window/dimension accuracy and that wall paint stays as photographed unless the customer asked.

Brain-layer rules:
- Observation: only what the photo/answers show. Name possessions. No invented dims.
- Human need: answer the routine (daily/weekly use) in human_need.routine.
- Spatial constraint: preserve_shell true, windows_dims_fidelity "~95%", no_invented_floor_plan true. known_from_photo is qualitative only.
- Recommendation: one system + why_it_should_work (causal, not fluff).
- Validation: REAL checks — fit, flow, budget_band (vs stated budget), possession_respect, plus conflicts and assumptions. status is pass, watch, or fail. Do not invent scores or room measurements.
- Customer instruction: start_here + do_this_week the customer can do without construction."""

BOTHERS = {
    "clutter": "Too much clutter", "no_storage": "Not enough storage",
    "hard_clean": "Hard to clean", "stressful": "Feels stressful/overwhelming",
    "not_cozy": "Doesn't feel cozy", "no_function": "Doesn't function well",
    "bad_layout": "Poor furniture layout", "too_dark": "Too dark",
    "no_hobby": "No space for hobbies/work",
}
FEELING = {
    "calm": "Calm", "cozy": "Cozy", "minimal": "Clean / minimal", "airy": "Airy / open",
    "elegant": "Elegant", "warm": "Warm", "functional": "Functional", "modern": "Modern",
    "luxurious": "Luxurious", "practical": "Practical",
}
STORAGE = {
    "clothing": "Clothing", "shoes": "Shoes", "paperwork": "Paperwork",
    "hobby": "Hobby / craft items", "decor": "Decor", "laundry": "Laundry",
    "tools": "Tools", "sports": "Sports gear",
}
STYLE = {
    "modern": "Modern", "minimal": "Minimal", "farmhouse": "Farmhouse",
    "traditional": "Traditional", "scandinavian": "Scandinavian",
    "cozy_layered": "Cozy & layered", "natural": "Natural / organic",
    "feminine": "Feminine soft", "hotel": "Hotel-inspired", "mixed": "Mixed style",
}
COLORS = {
    "warm_neutrals": "Warm neutrals", "white": "White / light", "sage": "Sage green",
    "earth": "Earth tones", "blue": "Soft blues", "dark": "Dark / moody",
    "wood": "Wood tones", "black": "Black accents",
}
BUDGET = {
    "under_100": "Under $100", "100_300": "$100 – 300",
    "300_700": "$300 – 700", "700_plus": "$700+",
}
DIY = {
    "very": "Very DIY-friendly", "simple": "Simple assembly only",
    "minimal": "Prefer minimal work", "hire": "Would hire help if needed",
}


KEEP_EXISTING_WALL_NAME = "Keep existing / no paint change"
KEEP_EXISTING_WALL_NOTE = (
    "No paint change — keep the existing wall color from the photo."
)
PAINT_REQUEST_RE = re.compile(
    r"\b(paint|repaint|re-paint|painted|painting|accent wall|wall colou?r|wall paint)\b",
    re.I,
)


def _humanize(values: List[str], mapping: Dict[str, str]) -> List[str]:
    return [mapping.get(v, v.replace("_", " ")) for v in (values or [])]


def customer_requested_paint(lead: Optional[Dict[str, Any]]) -> bool:
    """True only when the customer explicitly asked to paint / change wall color.

    color_prefs (earth, sage, …) are textile/accessory colors and do not count.
    """
    if not lead:
        return False
    blobs = [
        lead.get("biggest_challenge"),
        lead.get("goals"),
        lead.get("bothers_other"),
        lead.get("feeling_other"),
        lead.get("must_stay"),
        lead.get("daily_improvement"),
        lead.get("notes"),
    ]
    text = " ".join(str(v) for v in blobs if v)
    return bool(PAINT_REQUEST_RE.search(text))


def is_keep_existing_wall(deliverable: Optional[Dict[str, Any]]) -> bool:
    if not deliverable:
        return True
    name = (deliverable.get("wall_color_name") or "").strip().lower()
    if "keep existing" in name or "no paint" in name:
        return True
    hex_color = (deliverable.get("wall_color_hex") or "").strip()
    code = (deliverable.get("wall_color_code") or "").strip()
    if not name and not hex_color and not code:
        return True
    return False


def _summarize_lead(lead: Dict[str, Any]) -> str:
    parts: List[str] = []
    space = (lead.get("space_type") or "space").capitalize()
    parts.append(f"Space: {space}")
    if lead.get("name"):
        parts.append(f"Customer name: {lead['name']}")
    if lead.get("biggest_challenge"):
        parts.append(f"Main problem: {lead['biggest_challenge']}")
    if lead.get("goals") and lead.get("goals") != lead.get("biggest_challenge"):
        parts.append(f"Goals: {lead['goals']}")
    if lead.get("bothers_about"):
        parts.append("What bothers them: " + ", ".join(_humanize(lead["bothers_about"], BOTHERS)))
    if lead.get("bothers_other"):
        parts.append(f"Other concern: {lead['bothers_other']}")
    if lead.get("desired_feeling"):
        parts.append("Wants the space to feel: " + ", ".join(_humanize(lead["desired_feeling"], FEELING)))
    if lead.get("feeling_other"):
        parts.append(f"Also: {lead['feeling_other']}")
    if lead.get("must_stay"):
        parts.append(f"Must keep: {lead['must_stay']}")
    if lead.get("storage_needs"):
        parts.append("Storage for: " + ", ".join(_humanize(lead["storage_needs"], STORAGE)))
    if lead.get("style_prefs"):
        parts.append("Style: " + ", ".join(_humanize(lead["style_prefs"], STYLE)))
    if lead.get("color_prefs"):
        parts.append(
            "Textile/accessory colors (NOT wall paint): "
            + ", ".join(_humanize(lead["color_prefs"], COLORS))
        )
    else:
        parts.append("No color preference stated — do not invent a wall paint color.")
    if customer_requested_paint(lead):
        parts.append(
            "Customer explicitly asked about paint/wall color — a paint suggestion is allowed."
        )
    else:
        parts.append(
            "Wall paint: KEEP EXISTING / no paint change. Customer did not ask to paint. "
            "Do not invent an optional accent wall color."
        )
    if lead.get("budget"):
        parts.append("Budget: " + BUDGET.get(lead["budget"], lead["budget"]))
    if lead.get("diy_level"):
        parts.append("DIY: " + DIY.get(lead["diy_level"], lead["diy_level"]))
    if lead.get("daily_improvement"):
        parts.append(f"Daily improvement goal: {lead['daily_improvement']}")
    return "\n".join(parts) or f"Space: {space}"


class DraftJSONError(ValueError):
    """Model draft was not usable JSON. The lead can be retried."""


def _isolate_json_text(raw: str) -> str:
    """Pull the JSON object out of fences, including a fence the model never closed."""
    text = (raw or "").strip()
    blocks = [
        match.group(1).strip()
        for match in re.finditer(r"```(?:json)?\s*\n?([\s\S]*?)```", text, flags=re.I)
    ]
    fenced = [block for block in blocks if "{" in block]
    if fenced:
        return max(fenced, key=len)
    text = re.sub(r"^```(?:json)?[^\n]*\n?", "", text, count=1, flags=re.I)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_string(text: str, index: int) -> tuple[Optional[str], int]:
    if index >= len(text) or text[index] != '"':
        return None, index
    cursor = index + 1
    escaped = False
    while cursor < len(text):
        char = text[cursor]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return text[index : cursor + 1], cursor + 1
        cursor += 1
    return None, index


def _parse_number(text: str, index: int) -> Optional[tuple[str, int]]:
    cursor = index
    if cursor < len(text) and text[cursor] == "-":
        cursor += 1
    if cursor >= len(text) or not text[cursor].isdigit():
        return None
    if text[cursor] == "0":
        cursor += 1
    else:
        while cursor < len(text) and text[cursor].isdigit():
            cursor += 1
    if cursor < len(text) and text[cursor] == ".":
        fraction = cursor + 1
        if fraction >= len(text) or not text[fraction].isdigit():
            return None
        cursor = fraction + 1
        while cursor < len(text) and text[cursor].isdigit():
            cursor += 1
    if cursor < len(text) and text[cursor] in "eE":
        exponent = cursor + 1
        if exponent < len(text) and text[exponent] in "+-":
            exponent += 1
        if exponent >= len(text) or not text[exponent].isdigit():
            return None
        cursor = exponent + 1
        while cursor < len(text) and text[cursor].isdigit():
            cursor += 1
    return text[index:cursor], cursor


def _parse_literal(text: str, index: int) -> Optional[tuple[str, int]]:
    for literal in ("true", "false", "null"):
        if not text.startswith(literal, index):
            continue
        end = index + len(literal)
        if end < len(text) and (text[end].isalnum() or text[end] == "_"):
            return None
        return literal, end
    return None


def _parse_value(text: str, index: int) -> tuple[Optional[str], int]:
    index = _skip_ws(text, index)
    if index >= len(text):
        return None, index
    char = text[index]
    if char == '"':
        return _parse_string(text, index)
    if char == "{":
        return _parse_object(text, index)
    if char == "[":
        return _parse_array(text, index)
    if char in "-0123456789":
        parsed = _parse_number(text, index)
        return parsed if parsed is not None else (None, index)
    if char in "tfn":
        parsed = _parse_literal(text, index)
        return parsed if parsed is not None else (None, index)
    return None, index


def _parse_object(text: str, index: int) -> tuple[Optional[str], int]:
    """Parse an object, dropping a truncated key or value at the end."""
    if index >= len(text) or text[index] != "{":
        return None, index
    index += 1
    parts: List[str] = []
    while True:
        index = _skip_ws(text, index)
        if index >= len(text):
            break
        if text[index] == "}":
            return "{" + ",".join(parts) + "}", index + 1
        key, after_key = _parse_string(text, index)
        if key is None:
            break
        index = _skip_ws(text, after_key)
        if index >= len(text) or text[index] != ":":
            break
        index = _skip_ws(text, index + 1)
        if index >= len(text):
            break
        value, after_value = _parse_value(text, index)
        if value is None:
            break
        parts.append(f"{key}:{value}")
        index = _skip_ws(text, after_value)
        if index >= len(text):
            break
        if text[index] == ",":
            index += 1
            continue
        if text[index] == "}":
            return "{" + ",".join(parts) + "}", index + 1
        break
    if not parts:
        return None, index
    return "{" + ",".join(parts) + "}", index


def _parse_array(text: str, index: int) -> tuple[Optional[str], int]:
    if index >= len(text) or text[index] != "[":
        return None, index
    index += 1
    parts: List[str] = []
    while True:
        index = _skip_ws(text, index)
        if index >= len(text):
            break
        if text[index] == "]":
            return "[" + ",".join(parts) + "]", index + 1
        value, after_value = _parse_value(text, index)
        if value is None:
            break
        parts.append(value)
        index = _skip_ws(text, after_value)
        if index >= len(text):
            break
        if text[index] == ",":
            index += 1
            continue
        if text[index] == "]":
            return "[" + ",".join(parts) + "]", index + 1
        break
    if not parts:
        return None, index
    return "[" + ",".join(parts) + "]", index


def _escape_controls(text: str) -> str:
    """Escape raw newlines/tabs inside strings so json.loads can accept a repair."""
    out: List[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                out.append(char)
                escaped = False
                continue
            if char == "\\":
                out.append(char)
                escaped = True
                continue
            if char == '"':
                in_string = False
                out.append(char)
                continue
            if char == "\n":
                out.append("\\n")
                continue
            if char == "\r":
                out.append("\\r")
                continue
            if char == "\t":
                out.append("\\t")
                continue
            out.append(char)
            continue
        if char == '"':
            in_string = True
        out.append(char)
    return "".join(out)


def _loads_dict(text: str) -> Optional[Dict[str, Any]]:
    for candidate in (text, _escape_controls(text)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _loads_outer_object(text: str) -> Optional[Dict[str, Any]]:
    """Decode a complete object, ignoring trailing prose. Truncation returns None."""
    if not text:
        return None
    starts = [0]
    brace = text.find("{")
    if brace > 0:
        starts.append(brace)
    for start in starts:
        try:
            data, _end = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _repair_truncated_object(text: str) -> Optional[Dict[str, Any]]:
    if not text or text[0] != "{":
        return None
    rendered, _index = _parse_object(text, 0)
    if not rendered:
        return None
    return _loads_dict(rendered)


def _plan_usable(plan: Dict[str, Any]) -> bool:
    for key in _SUBSTANTIVE_KEYS:
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and len(value) > 0:
            return True
    return False


def _extract_json(raw: str) -> Dict[str, Any]:
    """Parse a model draft. Fences and a cut-off tail are recovered.

    A still-unusable reply raises DraftJSONError so callers can retry the
    lead. JSONDecodeError is not propagated — that string used to be stored
    as the customer-facing automation error.
    """
    text = _isolate_json_text(raw)
    try:
        direct = _loads_outer_object(text)
    except json.JSONDecodeError:
        direct = None
    if isinstance(direct, dict) and _plan_usable(direct):
        return direct

    search_from = 0
    while True:
        brace = text.find("{", search_from)
        if brace < 0:
            break
        try:
            repaired = _repair_truncated_object(text[brace:])
        except json.JSONDecodeError:
            repaired = None
        if isinstance(repaired, dict) and _plan_usable(repaired):
            logger.info(
                "Repaired AI draft JSON (%d chars, %d keys)",
                len(text),
                len(repaired),
            )
            return repaired
        search_from = brace + 1

    raise DraftJSONError(
        "AI draft JSON was truncated or malformed and could not be repaired. "
        "Retry this lead."
    )


def _message_text(message: Any) -> str:
    parts: List[str] = []
    for block in getattr(message, "content", None) or []:
        if isinstance(block, dict):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "".join(parts)


def _user_content(user_text: str, photo_b64: Optional[str]) -> Any:
    if not photo_b64:
        return user_text
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": photo_b64,
            },
        },
        {"type": "text", "text": user_text},
    ]


def _coerce(plan: Dict[str, Any], lead: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    def as_str(v):
        return "" if v is None else str(v).strip()

    def as_str_list(v):
        if not v:
            return []
        if isinstance(v, str):
            return [v.strip()]
        return [str(x).strip() for x in v if str(x).strip()]

    zones = []
    for z in plan.get("zones") or []:
        if isinstance(z, dict):
            zones.append({"title": as_str(z.get("title")), "desc": as_str(z.get("desc"))})
        elif isinstance(z, str):
            zones.append({"title": z, "desc": ""})

    shopping_list = []
    for it in plan.get("shopping_list") or []:
        if not isinstance(it, dict):
            continue
        try:
            qty = float(it.get("qty", 1) or 1)
            price = float(it.get("price", 0) or 0)
        except Exception:
            qty, price = 1.0, 0.0
        name = as_str(it.get("name"))
        if name:
            shopping_list.append({"name": name, "qty": qty, "price": price})

    hex_color = as_str(plan.get("wall_color_hex"))
    if hex_color and not hex_color.startswith("#"):
        hex_color = "#" + hex_color
    if hex_color and not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        hex_color = "#cfd7d3" if customer_requested_paint(lead) else ""

    wall_name = as_str(plan.get("wall_color_name"))
    wall_code = as_str(plan.get("wall_color_code"))
    wall_note = as_str(plan.get("wall_color_note"))
    if not customer_requested_paint(lead):
        wall_name = KEEP_EXISTING_WALL_NAME
        wall_code = ""
        hex_color = ""
        wall_note = KEEP_EXISTING_WALL_NOTE

    coerced = {
        "intro": as_str(plan.get("intro")),
        "needs": as_str_list(plan.get("needs")),
        "zones": zones,
        "wall_color_name": wall_name,
        "wall_color_code": wall_code,
        "wall_color_hex": hex_color,
        "wall_color_note": wall_note,
        "shopping_list": shopping_list,
        "budget_note": as_str(plan.get("budget_note")),
        "strategy": as_str_list(plan.get("strategy")),
        "action_plan": as_str_list(plan.get("action_plan")),
        "benefits": as_str_list(plan.get("benefits")),
        "notes": as_str(plan.get("notes"))
        or (
            "Windows and room proportions stay ~95% true to your photo. "
            "Wall paint stays as photographed — no paint change unless you asked."
        ),
        "summary": as_str(plan.get("summary")),
        "attachment_note": as_str(plan.get("attachment_note")),
        "blueprint_layers": {},
    }
    coerced["blueprint_layers"] = merge_layers(
        plan.get("blueprint_layers") or {},
        derive_layers(lead or {}, coerced),
    )
    return coerced


async def draft_deliverable(
    lead: Dict[str, Any],
    *,
    reference_photo_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Call Claude and return a normalized deliverable dict.

    When a gravity-corrected customer photo is available, attach it so
    observation / spatial layers can name real windows and fixtures.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=api_key)
    user_text = (
        "Customer questionnaire answers:\n\n"
        + _summarize_lead(lead)
        + "\n\nFill blueprint_layers completely so a reviewer can answer: "
        "routine, possessions, physical fit, budget, and why it should work. "
        "Never recommend storage over windows/doors or fixtures on walls. "
        "Default wall paint to keep existing / no paint change unless they asked to paint. "
        "Return ONLY the JSON object — no markdown, no preamble."
    )

    photo_b64: Optional[str] = None
    photo = upright_bytes(reference_photo_bytes) if reference_photo_bytes else None
    if photo:
        import base64

        vision_jpeg = jpeg_for_vision(photo, max_side=1280)
        photo_b64 = base64.b64encode(vision_jpeg).decode("ascii")
        user_text = (
            "A gravity-corrected photo of the customer's space is attached. "
            "Floor is at the bottom; ceiling is at the top. Use it for observation "
            "and spatial_constraint only — do not invent openings the photo does not show.\n\n"
            + user_text
        )

    last_error: Optional[DraftJSONError] = None
    for attempt in range(1, _DRAFT_ATTEMPTS + 1):
        prompt = user_text if attempt == 1 else user_text + _RETRY_HINT
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=DRAFT_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _user_content(prompt, photo_b64)}],
        )
        raw = _message_text(message)
        stop_reason = getattr(message, "stop_reason", None)
        logger.info(
            "AI draft received (%d chars, stop=%s, attempt=%d)",
            len(raw),
            stop_reason,
            attempt,
        )
        try:
            plan = _extract_json(raw)
        except DraftJSONError as exc:
            last_error = exc
            logger.warning(
                "AI draft JSON unusable (attempt %d, stop=%s, %d chars): %s",
                attempt,
                stop_reason,
                len(raw),
                exc,
            )
            continue
        return _coerce(plan, lead=lead)

    raise last_error or DraftJSONError(
        "AI draft JSON was truncated or malformed and could not be repaired. "
        "Retry this lead."
    )
