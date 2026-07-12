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
from typing import Any, Dict, List

import anthropic

logger = logging.getLogger(__name__)

MODEL_NAME = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a senior home-organization designer for FlowSpace.
We focus on storage solutions for mental health — our philosophy is that a calm,
organized space directly reduces anxiety, overwhelm, and decision fatigue.

Given a customer's questionnaire answers, produce a thoughtful, calm,
practical design plan tailored to their space and mental-health needs.

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
  "attachment_note": string
}

Style: calm, friendly, second-person. Prices in USD (IKEA/Target ranges).
wall_color_hex must be valid 7-char hex. shopping_list.price is per-unit number.
Always weave in the mental-health angle: clutter causes stress, organization creates calm."""

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


def _humanize(values: List[str], mapping: Dict[str, str]) -> List[str]:
    return [mapping.get(v, v.replace("_", " ")) for v in (values or [])]


def _summarize_lead(lead: Dict[str, Any]) -> str:
    parts: List[str] = []
    space = (lead.get("space_type") or "space").capitalize()
    parts.append(f"Space: {space}")
    if lead.get("name"):
        parts.append(f"Customer name: {lead['name']}")
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
        parts.append("Colors: " + ", ".join(_humanize(lead["color_prefs"], COLORS)))
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


def _coerce(plan: Dict[str, Any]) -> Dict[str, Any]:
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
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color or ""):
        hex_color = "#cfd7d3"

    return {
        "intro": as_str(plan.get("intro")),
        "needs": as_str_list(plan.get("needs")),
        "zones": zones,
        "wall_color_name": as_str(plan.get("wall_color_name")),
        "wall_color_code": as_str(plan.get("wall_color_code")),
        "wall_color_hex": hex_color,
        "wall_color_note": as_str(plan.get("wall_color_note")),
        "shopping_list": shopping_list,
        "budget_note": as_str(plan.get("budget_note")),
        "strategy": as_str_list(plan.get("strategy")),
        "action_plan": as_str_list(plan.get("action_plan")),
        "benefits": as_str_list(plan.get("benefits")),
        "notes": as_str(plan.get("notes")) or "All measurements are approximate. Confirm before purchasing.",
        "summary": as_str(plan.get("summary")),
        "attachment_note": as_str(plan.get("attachment_note")),
    }


async def draft_deliverable(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude and return a normalized deliverable dict."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=api_key)
    user_text = (
        "Customer questionnaire answers:\n\n"
        + _summarize_lead(lead)
        + "\n\nReturn ONLY the JSON object — no markdown, no preamble."
    )

    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
    )

    raw = message.content[0].text
    logger.info("AI draft received (%d chars)", len(raw or ""))
    plan = _extract_json(raw)
    return _coerce(plan)
