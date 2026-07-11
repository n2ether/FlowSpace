"""
AI-assisted deliverable drafting via Emergent LLM (Claude Sonnet 4.5).

Takes a lead's questionnaire answers and returns a structured JSON design plan
that maps directly to the Deliverable model.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """You are a senior home-organization designer for FlowSpace.
Given a customer's questionnaire answers, produce a thoughtful, calm,
practical design plan tailored to their space and preferences.

Return ONLY valid JSON matching exactly this schema (no prose, no markdown,
no code fences) — keep every list short and concrete (max ~5 items each):

{
  "intro": string,            // 1–2 warm sentences welcoming them
  "needs": [string],          // 3–6 functional needs for the space
  "zones": [{"title": string, "desc": string}],  // 3–4 functional zones
  "wall_color_name": string,  // designer-friendly paint name
  "wall_color_code": string,  // a real-sounding code (e.g. "SW 6204") — invent if needed
  "wall_color_hex": string,   // valid 7-char hex like "#cfd7d3" matching color_prefs
  "wall_color_note": string,  // 1 short sentence on why this color works
  "shopping_list": [{"name": string, "qty": number, "price": number}],  // 5–8 items, USD
  "budget_note": string,      // 1 short line on how the total fits their budget
  "strategy": [string],       // 3–5 design principles tied to desired_feeling
  "action_plan": [string],    // 4–6 ordered steps the customer can follow
  "benefits": [string],       // 3–5 outcomes
  "notes": string,            // 1 line caveat about measurements
  "summary": string,          // 2–3 sentences recapping the design intent
  "attachment_note": string   // 1 short line; can be empty string
}

Style guidance:
- Calm, friendly, second-person voice. Avoid jargon.
- Prices are reasonable USD estimates (Target/IKEA/Wayfair-ish ranges).
- shopping_list.price is a per-unit number (e.g. 49.99), not a string.
- wall_color_hex must be a valid hex code. If the customer chose 'sage', pick a sage hex.
- The plan must reflect: space_type, bothers_about, desired_feeling, must_stay,
  storage_needs, style_prefs, color_prefs, budget, diy_level, and daily_improvement.
- If diy_level indicates low DIY, prefer simple-assembly items and small steps.
- If budget is low (under_100 / 100_300), keep totals within that band."""


# Friendly label maps so the LLM sees human-readable answers instead of opaque keys.
BOTHERS = {
    "clutter": "Too much clutter",
    "no_storage": "Not enough storage",
    "hard_clean": "Hard to clean",
    "stressful": "Feels stressful/overwhelming",
    "not_cozy": "Doesn't feel cozy",
    "no_function": "Doesn't function well",
    "bad_layout": "Poor furniture layout",
    "too_dark": "Too dark",
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
    out: List[str] = []
    for v in values or []:
        out.append(mapping.get(v, v.replace("_", " ")))
    return out


def _summarize_lead(lead: Dict[str, Any]) -> str:
    """Build a clean prompt body from raw lead fields."""
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
        parts.append(f"Also feels like: {lead['feeling_other']}")

    if lead.get("must_stay"):
        parts.append(f"Must keep in the room: {lead['must_stay']}")

    if lead.get("storage_needs"):
        parts.append("Needs more storage for: " + ", ".join(_humanize(lead["storage_needs"], STORAGE)))

    if lead.get("style_prefs"):
        parts.append("Style preferences: " + ", ".join(_humanize(lead["style_prefs"], STYLE)))
    if lead.get("color_prefs"):
        parts.append("Color preferences: " + ", ".join(_humanize(lead["color_prefs"], COLORS)))

    if lead.get("budget"):
        parts.append("Budget: " + BUDGET.get(lead["budget"], lead["budget"]))
    if lead.get("diy_level"):
        parts.append("DIY comfort: " + DIY.get(lead["diy_level"], lead["diy_level"]))

    if lead.get("daily_improvement"):
        parts.append(f"One way it should improve daily life: {lead['daily_improvement']}")

    return "\n".join(parts) or f"Space: {space}"


def _extract_json(raw: str) -> Dict[str, Any]:
    """Tolerantly parse the LLM response — strip code fences and grab the JSON object."""
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
    """Normalize/validate the LLM output so it round-trips into the Deliverable model."""
    def as_str(v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    def as_str_list(v: Any) -> List[str]:
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
        "notes": as_str(plan.get("notes")) or "Important: all measurements are approximate. Confirm with a tape measure before purchasing.",
        "summary": as_str(plan.get("summary")),
        "attachment_note": as_str(plan.get("attachment_note")),
    }


async def draft_deliverable(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Call Claude Sonnet 4.5 and return a normalized deliverable dict."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"deliverable-{lead.get('id', uuid.uuid4())}-{uuid.uuid4().hex[:8]}",
        system_message=SYSTEM_PROMPT,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)

    user_text = (
        "Customer questionnaire answers:\n\n"
        + _summarize_lead(lead)
        + "\n\nReturn ONLY the JSON object as specified — no markdown, no preamble."
    )
    msg = UserMessage(text=user_text)
    raw = await chat.send_message(msg)
    logger.info("AI deliverable draft received (%d chars)", len(raw or ""))

    plan = _extract_json(raw)
    return _coerce(plan)


ROOM_PLAN_SYSTEM_PROMPT = """You are FlowSpace's senior organization designer.
Create a premium, practical room-organization plan from a customer's intake.
Your output must be valid JSON only, no markdown.

Schema:
{
  "room_summary": string,
  "organization_strategy": [string],
  "mental_health_benefits": [string],
  "storage_solutions": [{"name": string, "why": string, "estimated_cost": string}],
  "diy_steps": [string],
  "estimated_difficulty": string,
  "estimated_time": string,
  "estimated_budget": string,
  "product_search_terms": [string]
}

Guidelines:
- Focus on organizing clutter and improving daily calm.
- Recommend only realistic storage products: bins, shelves, labels, baskets,
  cabinets, hooks, drawer organizers, pantry systems, closet systems, laundry
  storage, garage racks, or similar practical organization products.
- Respect rent/own and drilling/mounting permission.
- Keep the tone supportive, clear, and mentally peaceful.
- Search terms should be short retail-friendly phrases such as "clear storage
  bins", "garage shelving", "closet cube organizer", "laundry room wall
  shelves", and "pantry labels"."""


DEFAULT_SEARCH_TERMS = {
    "garage": ["garage shelving", "clear storage bins", "wall hooks", "label maker"],
    "closet": ["closet cube organizer", "slim velvet hangers", "shoe rack", "drawer dividers"],
    "pantry": ["pantry labels", "clear pantry bins", "airtight food containers", "tiered shelf organizer"],
    "laundry": ["laundry room wall shelves", "rolling laundry cart", "woven baskets", "utility hooks"],
    "bedroom": ["under-bed storage", "drawer organizers", "woven baskets", "closet bins"],
    "office": ["desktop drawer organizer", "paper file bins", "floating shelves", "cable management box"],
}


def _search_url(store: str, term: str) -> str:
    from urllib.parse import quote_plus

    q = quote_plus(term)
    if store == "Walmart":
        return f"https://www.walmart.com/search?q={q}"
    if store == "Target":
        return f"https://www.target.com/s?searchTerm={q}"
    if store == "IKEA":
        return f"https://www.ikea.com/us/en/search/?q={q}"
    return f"https://www.google.com/search?q={q}"


def add_retailer_sections(plan: Dict[str, Any]) -> Dict[str, Any]:
    terms = [
        str(term).strip()
        for term in (plan.get("product_search_terms") or [])
        if str(term).strip()
    ][:10]
    plan["product_recommendations"] = {
        store: [{"term": term, "url": _search_url(store, term)} for term in terms]
        for store in ("Walmart", "Target", "IKEA")
    }
    return plan


def _fallback_room_plan(intake: Dict[str, Any]) -> Dict[str, Any]:
    room = (intake.get("room_type") or "room").lower()
    budget = intake.get("budget") or "selected budget"
    mounting_allowed = bool(intake.get("mounting_allowed"))
    terms = DEFAULT_SEARCH_TERMS.get(room, [
        "clear storage bins",
        "cube organizer",
        "storage baskets",
        "drawer organizers",
        "pantry labels",
    ])
    if not mounting_allowed:
        terms = [t for t in terms if "wall" not in t and "floating" not in t] + [
            "freestanding shelving",
            "over the door organizer",
        ]

    plan = {
        "room_summary": (
            f"This {room} plan turns visual clutter into simple zones while keeping the room's "
            "existing structure, finishes, and daily function intact."
        ),
        "organization_strategy": [
            "Group items by use so the most-needed objects live at eye level.",
            "Use repeated bins and labels to reduce visual noise.",
            "Reserve closed storage for busy-looking categories and open storage for daily-use items.",
            "Keep walkways and work surfaces clear to make the room easier to reset.",
        ],
        "mental_health_benefits": [
            "Clear surfaces can lower visual overwhelm and make it easier to start tasks.",
            "Labeled zones reduce decision fatigue because every item has a known home.",
            "A calmer entry view helps the room feel more restorative when you walk in.",
        ],
        "storage_solutions": [
            {"name": terms[0], "why": "Creates consistent homes for grouped items.", "estimated_cost": "$20-$80"},
            {"name": terms[1], "why": "Adds vertical or modular capacity without changing the room layout.", "estimated_cost": "$35-$150"},
            {"name": terms[2], "why": "Softens the look of small loose items.", "estimated_cost": "$15-$60"},
            {"name": terms[3], "why": "Keeps small categories separated and easy to maintain.", "estimated_cost": "$10-$45"},
        ],
        "diy_steps": [
            "Empty one category at a time and remove anything that no longer belongs in the room.",
            "Measure the open wall, shelf, closet, or cabinet areas before purchasing organizers.",
            "Install or place the largest storage piece first, then add bins and baskets by category.",
            "Label each container in plain language so the system is easy to maintain.",
            "Do a 10-minute reset after one week and adjust any category that is hard to put away.",
        ],
        "estimated_difficulty": "Easy to moderate",
        "estimated_time": "One focused afternoon for sorting plus assembly time for larger storage pieces",
        "estimated_budget": str(budget),
        "product_search_terms": terms[:8],
    }
    return add_retailer_sections(plan)


def _coerce_room_plan(plan: Dict[str, Any], intake: Dict[str, Any]) -> Dict[str, Any]:
    fallback = _fallback_room_plan(intake)

    def as_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    storage = []
    for item in plan.get("storage_solutions") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                storage.append(
                    {
                        "name": name,
                        "why": str(item.get("why") or "").strip(),
                        "estimated_cost": str(item.get("estimated_cost") or "").strip(),
                    }
                )
        elif str(item).strip():
            storage.append({"name": str(item).strip(), "why": "", "estimated_cost": ""})

    coerced = {
        "room_summary": str(plan.get("room_summary") or fallback["room_summary"]).strip(),
        "organization_strategy": as_list(plan.get("organization_strategy")) or fallback["organization_strategy"],
        "mental_health_benefits": as_list(plan.get("mental_health_benefits")) or fallback["mental_health_benefits"],
        "storage_solutions": storage or fallback["storage_solutions"],
        "diy_steps": as_list(plan.get("diy_steps")) or fallback["diy_steps"],
        "estimated_difficulty": str(plan.get("estimated_difficulty") or fallback["estimated_difficulty"]).strip(),
        "estimated_time": str(plan.get("estimated_time") or fallback["estimated_time"]).strip(),
        "estimated_budget": str(plan.get("estimated_budget") or fallback["estimated_budget"]).strip(),
        "product_search_terms": as_list(plan.get("product_search_terms")) or fallback["product_search_terms"],
    }
    return add_retailer_sections(coerced)


async def draft_room_plan(intake: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the customer-facing room transformation plan."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        logger.warning("EMERGENT_LLM_KEY is not configured; using deterministic room plan")
        return _fallback_room_plan(intake)

    chat = LlmChat(
        api_key=api_key,
        session_id=f"room-plan-{intake.get('job_id', uuid.uuid4())}-{uuid.uuid4().hex[:8]}",
        system_message=ROOM_PLAN_SYSTEM_PROMPT,
    ).with_model(MODEL_PROVIDER, MODEL_NAME)

    preferred = ", ".join(intake.get("preferred_stores") or []) or "Walmart, Target, IKEA"
    user_text = "\n".join(
        [
            f"Customer: {intake.get('customer_name') or intake.get('name') or 'FlowSpace customer'}",
            f"Room type: {intake.get('room_type') or intake.get('space_type') or 'room'}",
            f"Pain point: {intake.get('pain_point') or ''}",
            f"Budget: {intake.get('budget') or ''}",
            f"Preferred stores: {preferred}",
            f"Style preference: {intake.get('style_preference') or ''}",
            f"Rent or own: {intake.get('rent_or_own') or ''}",
            f"Drilling/mounting allowed: {bool(intake.get('mounting_allowed'))}",
            "Return only the JSON object.",
        ]
    )
    raw = await chat.send_message(UserMessage(text=user_text))
    plan = _extract_json(raw)
    return _coerce_room_plan(plan, intake)
