"""Generates structured design-plan content for the FlowSpace PDF using LLM
with safe per-room fallbacks if the model fails or returns malformed JSON."""

from __future__ import annotations
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

logger = logging.getLogger(__name__)

ROOM_LABEL = {
    "bedroom": "BEDROOM",
    "garage": "GARAGE",
    "closet": "CLOSET",
    "laundry": "LAUNDRY ROOM",
    "kitchen": "KITCHEN",
    "living": "LIVING ROOM",
    "office": "HOME OFFICE",
    "pantry": "PANTRY",
    "other": "ROOM",
}

ROOM_TITLE_SUFFIX = {
    "bedroom": "DESIGN PLAN",
    "garage": "DESIGN PLAN",
    "closet": "DESIGN PLAN",
    "laundry": "DESIGN PLAN",
    "kitchen": "ORGANIZATION PLAN",
    "living": "DESIGN PLAN",
    "office": "DESIGN PLAN",
    "pantry": "ORGANIZATION PLAN",
    "other": "DESIGN PLAN",
}

DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
    "bedroom": {
        "keywords": ["PRACTICAL", "CALMING", "COASTAL"],
        "summary": "A space that feels welcoming, peaceful and easy to live in.",
        "room_needs": [
            {"icon": "shopping-bag", "title": "Clothing & Accessories", "body": "Closet, dressers, seasonal items"},
            {"icon": "bed", "title": "Bedding & Linens", "body": "Extra sheets, blankets, pillows"},
            {"icon": "user", "title": "Personal Items", "body": "Daily essentials, books, meds"},
            {"icon": "leaf", "title": "Décor & Accents", "body": "Meaningful décor, soft lighting"},
            {"icon": "box", "title": "Storage", "body": "Hidden storage, baskets, bench"},
            {"icon": "lamp", "title": "Lighting", "body": "Warm, layered, relaxing lighting"},
        ],
        "zones": [
            {"title": "Sleeping Zone", "body": "Bed centered on the wall with nightstands for balance."},
            {"title": "Storage Zone", "body": "Dresser as focal point, shelf for open storage."},
            {"title": "Circulation Zone", "body": "Clear walkways for easy movement and flow."},
            {"title": "Calm Corner", "body": "Greenery, soft textures and natural elements add a relaxing feel."},
        ],
        "color": {"title": "WALL COLOR SUGGESTION", "name": "Sea Salt SW 6204", "hex": "#cfd9d4",
                  "reason": "A soft, coastal blue that feels calm, airy and timeless."},
        "shopping": [
            {"item": "Table lamps (set of 2)", "qty": 1, "price": 40},
            {"item": "Curtains (set of 2 panels)", "qty": 1, "price": 50},
            {"item": "Large wall art (above bed)", "qty": 1, "price": 60},
            {"item": "Area rug (8x10)", "qty": 1, "price": 80},
            {"item": "Storage baskets (set of 4)", "qty": 1, "price": 30},
        ],
        "budget_range": "$100 – $300",
        "strategy": [
            "Keep the layout balanced and clutter-free.",
            "Use matching nightstands for visual harmony.",
            "Layer soft textures for warmth and comfort.",
            "Add greenery to bring life and freshness.",
            "Use hidden storage to reduce visual noise.",
        ],
        "action_plan": [
            "Declutter and keep only what you need.",
            "Add new curtains and wall art.",
            "Refresh lighting with matching lamps.",
            "Add storage baskets for organization.",
            "Enjoy your calm, cozy bedroom!",
        ],
        "benefits": [
            "More restful and relaxing environment",
            "Easy to keep tidy and organized",
            "Feels brighter, softer and more open",
            "Reflects a timeless coastal style",
            "Better daily routine and better sleep",
        ],
        "view_labels": ["WINDOW WALL", "OPPOSITE WALL", "DOOR & BATH ENTRY", "STORAGE DETAIL"],
        "floor_plan": {"width_ft": 15, "depth_ft": 14, "notes": "Bed centered on long wall; door bottom-left."},
    },
    "garage": {
        "keywords": ["ORGANIZED", "FUNCTIONAL", "MODERN"],
        "summary": "A workshop-ready space where every tool has a home and the floor stays clear.",
        "room_needs": [
            {"icon": "wrench", "title": "Tools & Hardware", "body": "Hand tools, power tools, fasteners"},
            {"icon": "shopping-bag", "title": "Sports Gear", "body": "Bikes, balls, helmets, seasonal kit"},
            {"icon": "box", "title": "Seasonal Items", "body": "Holiday décor, camping, off-season"},
            {"icon": "layout-grid", "title": "Shelving", "body": "Wall-mounted, modular, vertical"},
            {"icon": "spray", "title": "Cleaning Supplies", "body": "Brooms, mops, fluids, rags"},
            {"icon": "compass", "title": "Floor Space", "body": "Clear paths and parking zones"},
        ],
        "zones": [
            {"title": "Tool Zone", "body": "Pegboard wall above workbench for daily-use tools."},
            {"title": "Bulk Storage Zone", "body": "Upper shelves for seasonal and rarely-used items."},
            {"title": "Wall Storage Zone", "body": "Hooks and rails for sports equipment and yard gear."},
            {"title": "Clear Floor Zone", "body": "Open paths so the car fits and you can move freely."},
        ],
        "color": {"title": "STYLE SUGGESTION", "name": "Matte black + wood",
                  "hex": "#1f2937",
                  "reason": "Matte black hooks with light wood shelving for a clean, hard-working look."},
        "shopping": [
            {"item": "Heavy-duty wall shelving", "qty": 2, "price": 65},
            {"item": "Clear storage bins (set of 6)", "qty": 1, "price": 45},
            {"item": "Wall hook & rail system", "qty": 1, "price": 35},
            {"item": "Label kit", "qty": 1, "price": 15},
            {"item": "Pegboard tool organizer", "qty": 1, "price": 55},
        ],
        "budget_range": "$150 – $400",
        "strategy": [
            "Keep the floor clear so the car always fits.",
            "Use vertical wall space instead of stacking on the floor.",
            "Group items by frequency of use, not type.",
            "Label every bin so the whole family can put things back.",
            "Use clear bins for seasonal items, opaque for messy ones.",
        ],
        "action_plan": [
            "Pull everything out and sort into keep / donate / toss.",
            "Mount shelves and pegboard on the walls.",
            "Sort items into labeled bins by zone.",
            "Park the car in and confirm clearance.",
            "Enjoy a garage that finally works.",
        ],
        "benefits": [
            "Park the car inside again",
            "Never lose a tool or screw",
            "Less visual clutter, calmer home",
            "Faster weekend projects",
            "Safer paths for kids and pets",
        ],
        "view_labels": ["DOOR VIEW", "WORK WALL", "STORAGE WALL", "OVERHEAD STORAGE"],
        "floor_plan": {"width_ft": 20, "depth_ft": 22, "notes": "Workbench along long wall, vehicle bay center."},
    },
    "closet": {
        "keywords": ["CLEAN", "SIMPLE", "EFFICIENT"],
        "summary": "An everyday closet that makes getting dressed feel calm, fast and intentional.",
        "room_needs": [
            {"icon": "shirt", "title": "Hanging Clothes", "body": "Shirts, dresses, coats by length"},
            {"icon": "shoes", "title": "Shoes", "body": "Daily, dress, seasonal pairs"},
            {"icon": "folder", "title": "Folded Items", "body": "Jeans, sweaters, denim, athleisure"},
            {"icon": "watch", "title": "Accessories", "body": "Bags, belts, scarves, jewelry"},
            {"icon": "box", "title": "Seasonal Storage", "body": "Off-season items in clear bins"},
            {"icon": "star", "title": "Daily Essentials", "body": "Most-worn items front and center"},
        ],
        "zones": [
            {"title": "Hanging Zone", "body": "Matching hangers in one color for instant calm."},
            {"title": "Shelf Zone", "body": "Folded items grouped by category, labeled."},
            {"title": "Shoe Zone", "body": "Slanted shoe rack along the floor."},
            {"title": "Accessory Zone", "body": "Drawer dividers or hanging organizers."},
        ],
        "color": {"title": "STYLE SUGGESTION", "name": "Warm white + light oak",
                  "hex": "#efe9df",
                  "reason": "Warm white walls with light oak shelving for a clean, airy feel."},
        "shopping": [
            {"item": "Matching velvet hangers (50)", "qty": 1, "price": 35},
            {"item": "Slanted shoe rack", "qty": 1, "price": 40},
            {"item": "Drawer dividers (set of 8)", "qty": 1, "price": 25},
            {"item": "Fabric storage baskets (set of 4)", "qty": 1, "price": 30},
            {"item": "Shelf labels", "qty": 1, "price": 10},
        ],
        "budget_range": "$80 – $200",
        "strategy": [
            "Use one hanger style for instant calm.",
            "Sort clothes by category, then color.",
            "Keep daily essentials at eye level.",
            "Use bins for awkward, hard-to-fold items.",
            "Donate anything you haven't worn in a year.",
        ],
        "action_plan": [
            "Empty the closet completely.",
            "Sort: keep, donate, repair, toss.",
            "Install the shoe rack and dividers.",
            "Re-hang everything on matching hangers.",
            "Label each shelf and zone.",
        ],
        "benefits": [
            "Mornings feel calmer and faster",
            "Outfits are easier to spot and plan",
            "Less laundry confusion",
            "Clothes last longer",
            "Closet feels twice as big",
        ],
        "view_labels": ["FRONT VIEW", "LEFT WALL", "RIGHT WALL", "SHELF DETAIL"],
        "floor_plan": {"width_ft": 8, "depth_ft": 6, "notes": "Door front center, shelving on long walls."},
    },
    "laundry": {
        "keywords": ["CLEAN", "EFFICIENT", "BRIGHT"],
        "summary": "A laundry room that's a pleasure to be in — bright, organized, and easy to keep that way.",
        "room_needs": [
            {"icon": "spray", "title": "Detergents & Cleaners", "body": "Pods, sprays, stain remover"},
            {"icon": "shirt", "title": "Sorting Hampers", "body": "Whites, darks, delicates, towels"},
            {"icon": "box", "title": "Folding Station", "body": "Counter or table for folding"},
            {"icon": "leaf", "title": "Air-Dry & Hang", "body": "Drying rack and rod"},
            {"icon": "lamp", "title": "Lighting", "body": "Bright overhead + task lighting"},
            {"icon": "compass", "title": "Floor Space", "body": "Clear walking path"},
        ],
        "zones": [
            {"title": "Wash Zone", "body": "Detergents and start buttons within reach."},
            {"title": "Sort Zone", "body": "Three hampers labeled lights / darks / delicates."},
            {"title": "Fold Zone", "body": "Counter with baskets underneath."},
            {"title": "Hang Zone", "body": "Rod or rack for air-dry items."},
        ],
        "color": {"title": "WALL COLOR SUGGESTION", "name": "Alabaster SW 7008", "hex": "#ece9e1",
                  "reason": "A soft warm white that keeps the room bright and airy."},
        "shopping": [
            {"item": "Sorting hampers (set of 3)", "qty": 1, "price": 55},
            {"item": "Wall shelf", "qty": 2, "price": 25},
            {"item": "Folding counter / table", "qty": 1, "price": 90},
            {"item": "Drying rack", "qty": 1, "price": 30},
            {"item": "Storage baskets (set of 4)", "qty": 1, "price": 30},
        ],
        "budget_range": "$100 – $300",
        "strategy": [
            "Sort as soon as laundry lands — never use the floor.",
            "Keep daily-use supplies at eye level.",
            "Match all bins and baskets for a calm look.",
            "Add a folding surface to finish loads on the spot.",
            "Add bright task lighting over the washer.",
        ],
        "action_plan": [
            "Pull everything out and toss expired products.",
            "Install shelving and folding surface.",
            "Add labeled hampers for sorting.",
            "Refresh the lighting.",
            "Enjoy a laundry routine that feels lighter.",
        ],
        "benefits": [
            "Laundry day feels lighter",
            "No more floor piles",
            "Clothes don't get lost",
            "Brighter, calmer space",
            "Easier to keep clean",
        ],
        "view_labels": ["WASHER WALL", "FOLDING WALL", "STORAGE WALL", "DOOR VIEW"],
        "floor_plan": {"width_ft": 10, "depth_ft": 8, "notes": "Appliances on long wall, folding counter opposite."},
    },
    "kitchen": {
        "keywords": ["CLEAN", "EFFICIENT", "WARM"],
        "summary": "A kitchen that flows — easy to cook in, easy to clean up, easy to live around.",
        "room_needs": [
            {"icon": "shopping-bag", "title": "Cookware", "body": "Pots, pans, lids, bakeware"},
            {"icon": "box", "title": "Pantry Items", "body": "Dry goods, snacks, baking"},
            {"icon": "user", "title": "Daily Essentials", "body": "Coffee, mugs, breakfast"},
            {"icon": "leaf", "title": "Produce & Fresh", "body": "Fruit bowl, vegetable storage"},
            {"icon": "lamp", "title": "Lighting", "body": "Task + ambient lighting"},
            {"icon": "compass", "title": "Counter Space", "body": "Clear prep surfaces"},
        ],
        "zones": [
            {"title": "Prep Zone", "body": "Knives, cutting boards, counter clear."},
            {"title": "Cook Zone", "body": "Pots, pans, oils next to the stove."},
            {"title": "Clean Zone", "body": "Sink area with dish soap and towels."},
            {"title": "Pantry Zone", "body": "Dry goods in labeled containers."},
        ],
        "color": {"title": "STYLE SUGGESTION", "name": "Warm white + brass",
                  "hex": "#f4ebd6",
                  "reason": "Warm white cabinets with brass pulls feel timeless and inviting."},
        "shopping": [
            {"item": "Pantry storage containers (set of 10)", "qty": 1, "price": 50},
            {"item": "Drawer organizers (set of 4)", "qty": 1, "price": 30},
            {"item": "Under-shelf risers", "qty": 2, "price": 20},
            {"item": "Spice rack", "qty": 1, "price": 25},
            {"item": "Tiered fruit basket", "qty": 1, "price": 35},
        ],
        "budget_range": "$100 – $250",
        "strategy": [
            "Group items by task, not by category.",
            "Keep counters clear; only daily items stay out.",
            "Decant pantry staples into matching jars.",
            "Use risers to double cabinet shelf space.",
            "Drawer dividers for the utensil drawer.",
        ],
        "action_plan": [
            "Empty one cabinet at a time.",
            "Toss expired food and donate duplicates.",
            "Install organizers and risers.",
            "Decant pantry items into clear containers.",
            "Label everything.",
        ],
        "benefits": [
            "Cooking feels faster and calmer",
            "Counters stay clear",
            "Less food waste",
            "Easier to clean",
            "Kitchen feels more welcoming",
        ],
        "view_labels": ["COUNTER VIEW", "PANTRY VIEW", "OPPOSITE WALL", "ISLAND DETAIL"],
        "floor_plan": {"width_ft": 14, "depth_ft": 12, "notes": "L-shape with island; sink under window."},
    },
    "other": {
        "keywords": ["ORGANIZED", "CALM", "INTENTIONAL"],
        "summary": "A space that finally works the way you live.",
        "room_needs": [
            {"icon": "layout-grid", "title": "Daily Essentials", "body": "What you reach for every day"},
            {"icon": "box", "title": "Long-term Storage", "body": "Things you keep but rarely use"},
            {"icon": "leaf", "title": "Décor & Accents", "body": "Pieces that bring you joy"},
            {"icon": "lamp", "title": "Lighting", "body": "Bright, layered, comfortable"},
            {"icon": "user", "title": "Personal Touches", "body": "Books, art, mementos"},
            {"icon": "compass", "title": "Open Space", "body": "Clear paths and surfaces"},
        ],
        "zones": [
            {"title": "Active Zone", "body": "Daily-use items front and center."},
            {"title": "Storage Zone", "body": "Bins and shelves for less-used items."},
            {"title": "Décor Zone", "body": "A few intentional pieces, not many."},
            {"title": "Open Zone", "body": "Clear floor and surface space."},
        ],
        "color": {"title": "STYLE SUGGESTION", "name": "Warm neutral + sage",
                  "hex": "#e2e3da",
                  "reason": "Warm neutrals with sage accents feel calm and welcoming."},
        "shopping": [
            {"item": "Storage baskets (set of 4)", "qty": 1, "price": 40},
            {"item": "Wall shelf", "qty": 2, "price": 30},
            {"item": "Bins with lids (set of 6)", "qty": 1, "price": 45},
            {"item": "Label kit", "qty": 1, "price": 15},
            {"item": "Area rug", "qty": 1, "price": 60},
        ],
        "budget_range": "$100 – $300",
        "strategy": [
            "Keep daily items easy to reach.",
            "Use matching storage for visual harmony.",
            "Donate anything you haven't used in a year.",
            "Add greenery for warmth.",
            "Layer lighting for comfort.",
        ],
        "action_plan": [
            "Sort everything into keep / donate / toss.",
            "Set up storage bins and shelves.",
            "Group items by how often you use them.",
            "Label what's not see-through.",
            "Step back and enjoy.",
        ],
        "benefits": [
            "Less visual clutter",
            "Easier to keep clean",
            "Feels brighter and calmer",
            "Items easier to find",
            "Room feels bigger",
        ],
        "view_labels": ["VIEW 1", "VIEW 2", "VIEW 3", "VIEW 4"],
        "floor_plan": {"width_ft": 12, "depth_ft": 10, "notes": "Approximate — adjust to your space."},
    },
}


def _coerce_room(room_type: Optional[str]) -> str:
    if not room_type:
        return "other"
    rt = room_type.strip().lower()
    for key in DEFAULT_PLANS:
        if rt == key or rt.startswith(key):
            return key
    if "bed" in rt:
        return "bedroom"
    if "garage" in rt:
        return "garage"
    if "closet" in rt or "wardrobe" in rt:
        return "closet"
    if "laundry" in rt:
        return "laundry"
    if "kitchen" in rt or "pantry" in rt:
        return "kitchen"
    return "other"


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # First, try direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try a code-fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # First {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


async def generate_design_plan(
    *,
    room_type: Optional[str],
    after_image_b64: Optional[str] = None,
    user_notes: Optional[str] = None,
    budget: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate (and return) the structured design-plan dict for the PDF.
    Always returns a complete plan — falls back to the per-room default."""
    rt = _coerce_room(room_type)
    base = json.loads(json.dumps(DEFAULT_PLANS[rt]))  # deep copy
    api_key = api_key or os.environ.get("EMERGENT_LLM_KEY")

    plan = {
        "room_key": rt,
        "room_label": ROOM_LABEL[rt],
        "title": f"{ROOM_LABEL[rt]} {ROOM_TITLE_SUFFIX[rt]}",
        **base,
    }
    if budget:
        plan["budget_range"] = budget

    if not api_key:
        return plan

    # Approximate target spend for the shopping list (midpoint of the budget range)
    target_total: Optional[int] = None
    if budget:
        nums = re.findall(r"\d[\d,]*", budget.replace(",", ""))
        try:
            nums_i = [int(n) for n in nums]
            if len(nums_i) >= 2:
                target_total = (nums_i[0] + nums_i[1]) // 2
            elif nums_i:
                target_total = nums_i[0]
        except Exception:
            target_total = None

    schema_hint = {
        "keywords": ["WORD1", "WORD2", "WORD3"],
        "summary": "One-sentence design summary (max 18 words).",
        "color_name": "Paint or finish name",
        "color_hex": "#xxxxxx",
        "color_reason": "Short reason (max 16 words).",
        "shopping": [
            {"item": "Item name", "qty": 1, "price": 40},
        ],
        "strategy": ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5"],
        "action_plan": ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"],
        "benefits": ["Benefit 1", "Benefit 2", "Benefit 3", "Benefit 4", "Benefit 5"],
    }

    sys = (
        "You are an interior organization designer creating polished, practical "
        "design plans. Reply with ONLY a JSON object matching the schema. "
        "Keep language warm, simple, premium. No emojis. No markdown fences."
    )
    budget_line = (
        f"Customer budget: {budget}. Build a 5-item shopping list whose subtotal "
        f"is around ${target_total} (must NOT exceed the top of the range). "
        if budget and target_total
        else "Use practical, mid-range USD pricing for the 5-item shopping list. "
    )
    user_text = (
        f"Room type: {plan['room_label']} ({rt}).\n"
        f"User notes: {user_notes or 'none'}.\n"
        f"{budget_line}"
        "Use the same JSON shape as this example "
        f"(values shown are placeholders, replace with your own): {json.dumps(schema_hint)}"
    )

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"plan-{uuid.uuid4()}",
            system_message=sys,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        contents = []
        if after_image_b64:
            contents = [ImageContent(after_image_b64)]
        msg = UserMessage(text=user_text, file_contents=contents)
        response = await chat.send_message(msg)
        text = response if isinstance(response, str) else str(response)
        data = _extract_json(text)
        if data:
            _merge_plan(plan, data)
    except Exception as e:
        logger.warning(f"Design plan AI failed, using defaults: {e}")

    return plan


def _merge_plan(plan: Dict[str, Any], data: Dict[str, Any]) -> None:
    """Merge AI-supplied fields into the default plan, validating types."""
    kw = data.get("keywords")
    if isinstance(kw, list) and len(kw) >= 3:
        plan["keywords"] = [str(x).upper()[:18] for x in kw[:3]]

    summary = data.get("summary")
    if isinstance(summary, str) and 4 <= len(summary) <= 220:
        plan["summary"] = summary.strip()

    if data.get("color_name"):
        plan["color"]["name"] = str(data["color_name"])[:40]
    if data.get("color_hex") and re.match(r"^#[0-9a-fA-F]{6}$", str(data["color_hex"])):
        plan["color"]["hex"] = str(data["color_hex"])
    if data.get("color_reason"):
        plan["color"]["reason"] = str(data["color_reason"])[:200]

    shopping = data.get("shopping")
    if isinstance(shopping, list) and shopping:
        cleaned = []
        for s in shopping[:5]:
            if not isinstance(s, dict):
                continue
            try:
                item = str(s.get("item", "")).strip()[:60]
                qty = int(s.get("qty", 1) or 1)
                price = float(s.get("price", 0) or 0)
                if item and price > 0:
                    cleaned.append({"item": item, "qty": qty, "price": round(price)})
            except Exception:
                continue
        if cleaned:
            plan["shopping"] = cleaned

    # Hard-clamp the total to the budget top so the PDF never overshoots
    budget_str = plan.get("budget_range", "") or ""
    nums = re.findall(r"\d[\d,]*", budget_str.replace(",", ""))
    if nums:
        try:
            cap = int(nums[-1]) if len(nums) >= 2 else int(nums[0])
            total = sum(int(it.get("qty", 1) or 1) * float(it.get("price", 0) or 0)
                        for it in plan["shopping"])
            if total > cap and total > 0:
                factor = cap / total
                for it in plan["shopping"]:
                    it["price"] = max(5, round(float(it["price"]) * factor))
        except Exception:
            pass

    for key in ("strategy", "action_plan", "benefits"):
        val = data.get(key)
        if isinstance(val, list) and val:
            plan[key] = [str(x).strip()[:120] for x in val[:6] if str(x).strip()]
