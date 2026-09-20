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


def _extract_json(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


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

    content: Any
    photo = upright_bytes(reference_photo_bytes) if reference_photo_bytes else None
    if photo:
        import base64

        vision_jpeg = jpeg_for_vision(photo, max_side=1280)
        user_text = (
            "A gravity-corrected photo of the customer's space is attached. "
            "Floor is at the bottom; ceiling is at the top. Use it for observation "
            "and spatial_constraint only — do not invent openings the photo does not show.\n\n"
            + user_text
        )
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(vision_jpeg).decode("ascii"),
                },
            },
            {"type": "text", "text": user_text},
        ]
    else:
        content = user_text

    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    raw = message.content[0].text
    logger.info("AI draft received (%d chars)", len(raw or ""))
    plan = _extract_json(raw)
    return _coerce(plan, lead=lead)
