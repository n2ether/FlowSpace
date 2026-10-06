"""Space-specific prompt rails.

Kids' room / nursery rules are enforced here so plan drafting and image
generation share one wording. The OpenAI image path keeps calling
``image_prompt_rails``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

NURSERY_SPACE_KEYS = frozenset(
    {
        "kids_room",
        "kidsroom",
        "nursery",
        "child_room",
        "childrens_room",
        "baby_room",
    }
)

# Conditional on the photo: do not invent a six-drawer count the room does not have.
NURSERY_IMAGE_RAILS = (
    "NURSERY / KIDS ROOM LOCK: Preserve the real room, the furniture already in it, "
    "its proportions, windows, door, and any space theme already in the photo. "
    "FIXED FEATURES LOCK: keep every wall switch, outlet, thermostat, and similar "
    "built-in control in its exact location — including the wall switch beside the door. "
    "Do not remove, cover, relocate, or invent a replacement for a wall switch. "
    "If a dresser is visible, keep that exact dresser. A six-drawer dresser keeps all "
    "six drawers. Do not replace drawers with baskets. Do not add large open cubbies, "
    "cube organizers, or a new bank of open shelves. Tidy loose items and textiles only. "
    "Do not add a towel hanger, towel bar, or hanging towel near the door or on the "
    "door wall — that addition is not part of the design. "
    "FAMILY PHOTO WALL: when family photos or a photo collage are already on a wall, "
    "keep that existing collage. Recompose or reposition it so its height feels "
    "intentional relative to nearby shelves and space-themed artwork. Prefer one calm "
    "cohesive grouping with negative space. Do not fill the wall with extra frames or "
    "several small decorative pieces. "
    "Storage must make daily life simpler, not add a sorting chore. The room should "
    "still look meaningfully calmer and more intentional."
)

# Every nursery render — hero and extra views — and any composite that pastes those renders.
CRIB_INTERIOR_RAILS = (
    "CRIB INTERIOR LOCK — obey this in every render, including the hero and every extra view: "
    "remove the teddy bear and every loose cushion, pillow, stuffed animal, bumper, loose blanket, "
    "and other loose object from inside the crib. "
    "The only things allowed in the crib are a fitted sheet and a wearable sleep sack. "
    "Do not leave toys or cushions in the crib. Do not composite a teddy or cushion back into the crib."
)

SPACE_THEME_IMAGE_RAILS = (
    "SPACE THEME LOCK: this kids' room already has a space theme. Keep it and make it clearer. "
    "Artwork, textiles, and small decor are planets, the moon, rockets, and astronauts. "
    "CRIB WALL: make Nicholas's space-explorer theme personal — a coordinated focal panel or "
    "restrained composition of planets, the moon, rockets, and/or astronauts on the crib wall. "
    "Reuse existing tactile sculptural space pieces from the photo where appropriate. "
    "Do not use generic nursery animals, woodland creatures, farm animals, rabbits, or unrelated cartoon art. "
    "Any 3D wall elements must look lightweight, securely mounted, and outside the crib's "
    "reachable or pull-down zone. The crib sleep surface stays completely clear. "
    "Do not replace the space theme with a new theme. Do not repaint the walls to create it."
)

NURSERY_DRAFT_RULES = """
Kids' room / nursery rules (only when space_type is a kids' room, nursery, or the answers describe one):
- Preserve the existing dresser and every drawer. If it is a six-drawer dresser, all six drawers stay.
- Do not replace drawers with baskets. Do not recommend a basket system in place of the dresser.
- Do not add large open cubbies, Kallax-style cube storage, or a new wall of open shelves.
- Storage must simplify the day (fewer decisions), not add a sorting or labeling chore.
- Keep the real room, furniture, proportions, and any space theme already there. The refresh should still look meaningfully calmer.
- If the room has a space theme, keep planets, the moon, rockets, and astronauts. Do not swap that art for generic nursery animals or rabbits.
- Preserve fixed features such as wall switches (including beside the door) in their exact locations.
- Do not add a towel hanger or towel near the door.
- Keep an existing family-photo collage calm: one intentional grouping with negative space; do not fill the wall with extra frames.
- On the crib wall, prefer a personal space-explorer composition; 3D pieces stay lightweight, securely mounted, and outside crib reach.
- In every view the crib interior stays clear: a fitted sheet and a wearable sleep sack only. No teddy bear, loose cushion, pillow, bumper, or loose blanket in the crib.
- Shopping-list prices must add up to the budget figure you state. One kit total only.
- The customer's budget band is their stated budget. Do not write a second kit price.
- Do not put a blanket, electric blanket, or crib blanket on the shopping list. Warm the window with a thermal curtain or shade (a thermal window layer), not a blanket.
- Do not recommend a portable heater, space heater, or wall-mounted heater. Use the heating already in the room, about 68–72°F.
- "No loose blankets in the crib" is a safety rule, not a product to buy.
- Write every customer-facing sentence in full. Do not leave a thought half-finished.
- Keep the room's existing rug (shape, size, color) unless the customer asked to change it. Do not add a second rug to the shopping list.
- Do not name the child's age or a birthday; write "As <child> grows" instead of "is turning one".
"""

NURSERY_DO_NOT = (
    "Do not replace dresser drawers with baskets.",
    "Do not add large open cubbies or cube storage.",
    "Do not place a portable heater, wall heater, or electric blanket near the sleep area.",
    "Do not put a teddy bear, loose cushion, pillow, bumper, or loose blanket in the crib.",
    "Do not remove, cover, or relocate the wall switch beside the door.",
    "Do not add a towel hanger or hanging towel near the door.",
    "Do not fill the family-photo wall with extra frames.",
    "Do not use rabbit or generic animal art on the crib wall.",
    "Keep window cords out of reach.",
)

_NURSERY_TEXT = re.compile(
    r"\b(nursery|kids?'?\s*room|child(?:ren)?'?s\s+room|baby\s+room)\b",
    re.I,
)
_SIX_DRAWER = re.compile(r"\b(six|6)[-\s]?drawer\b", re.I)
_SPACE_THEME = re.compile(
    r"\b(?:space[-\s]?theme(?:d)?|planets?|rockets?|astronauts?|outer\s+space|galax(?:y|ies)|solar\s+system|moon)\b",
    re.I,
)

# Extra after views must not repeat the window-and-crib hero.
# (slot, edit instruction, board caption)
NURSERY_SUPPORTING_VIEWS: Tuple[Tuple[str, str, str], ...] = (
    (
        "view_1",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the dresser and changing station only. "
        "Frame the six-drawer dresser large, from a three-quarter angle beside it. "
        "The crib and the window must sit at the edge or out of frame — they are not the subject. "
        "This must not look like the window-and-crib hero. Keep all six drawers. "
        "Do not replace drawers with baskets or add open cubbies. Same wall paint.",
        "Dresser and changing station",
    ),
    (
        "view_2",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the rocking chair. "
        "Stand to the side of the room so the rocker is the subject, not the crib and not the window wall. "
        "Show the chair and the floor beside it. Do not repeat the hero's window-and-crib composition. "
        "Same wall paint and furniture. Do not redesign the room.",
        "Rocker",
    ),
    (
        "view_3",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the door and the clear walking path. "
        "Camera at the doorway, looking along the open floor. The crib and window are not the subject. "
        "Show circulation from the door into the room. Same door location, same wall paint, same furniture. "
        "Keep the original wall switch beside the door in its exact location. "
        "Do not add a towel hanger, towel bar, or hanging towel near the door. "
        "Do not invent a new floor plan.",
        "Door and circulation",
    ),
)

GENERAL_SUPPORTING_VIEWS: Tuple[Tuple[str, str, str], ...] = (
    (
        "view_1",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the main storage, closer than the wide hero. "
        "Do not repeat the hero framing. Same walls, windows, and architecture.",
        "Main storage",
    ),
    (
        "view_2",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the work surface or daily-use zone. "
        "Use a different camera position from the hero. Same wall paint and openings.",
        "Daily-use zone",
    ),
    (
        "view_3",
        "DISTINCT ADDITIONAL AFTER VIEW. Focal point: the door and the clear circulation path. "
        "Do not repeat the wide hero framing. Same door, same walls. Do not invent a new floor plan.",
        "Door and circulation",
    ),
)


def _space_key(lead: Dict[str, Any] | None) -> str:
    raw = str((lead or {}).get("space_type") or "")
    return raw.strip().lower().replace(" ", "_").replace("'", "")


def is_nursery_space(lead: Dict[str, Any] | None) -> bool:
    """True for a kids' room or nursery. Does not match 'kids' bikes' in a garage."""
    lead = lead or {}
    if _space_key(lead) in NURSERY_SPACE_KEYS:
        return True
    blob = " ".join(
        str(lead.get(key) or "")
        for key in (
            "space_type",
            "goals",
            "biggest_challenge",
            "must_stay",
            "notes",
            "daily_improvement",
            "bothers_other",
        )
    )
    return bool(_NURSERY_TEXT.search(blob))


def mentions_six_drawer(*blobs: str) -> bool:
    return any(_SIX_DRAWER.search(blob or "") for blob in blobs)


def _theme_blob(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None = None) -> str:
    lead = lead or {}
    deliverable = deliverable or {}
    parts = [
        str(lead.get(key) or "")
        for key in (
            "goals",
            "must_stay",
            "notes",
            "space_type",
            "biggest_challenge",
            "daily_improvement",
            "bothers_other",
        )
    ]
    for key in ("summary", "intro", "notes"):
        parts.append(str(deliverable.get(key) or ""))
    for zone in deliverable.get("zones") or []:
        if isinstance(zone, dict):
            parts.append(str(zone.get("title") or ""))
            parts.append(str(zone.get("desc") or ""))
        else:
            parts.append(str(zone))
    for key in ("strategy", "needs", "action_plan"):
        parts.extend(str(item) for item in (deliverable.get(key) or []))
    return " ".join(parts)


def is_space_theme(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None = None) -> bool:
    """True when a kids' room already has a space theme (planets, moon, rockets, astronauts)."""
    if not is_nursery_space(lead):
        return False
    return bool(_SPACE_THEME.search(_theme_blob(lead, deliverable)))


def image_prompt_rails(
    lead: Dict[str, Any] | None,
    deliverable: Dict[str, Any] | None = None,
) -> str:
    """Extra image-edit constraint. Empty for closets, garages, and other rooms.

    Nursery rails include the crib-interior lock. Space-theme rails are added
    only when that theme is already in the room or the plan.
    """
    if not is_nursery_space(lead):
        return ""
    parts = [NURSERY_IMAGE_RAILS, CRIB_INTERIOR_RAILS]
    if is_space_theme(lead, deliverable):
        parts.append(SPACE_THEME_IMAGE_RAILS)
    return " ".join(parts)


RUG_PRESERVE_RAILS = (
    "RUG LOCK: if the source photo shows a rug, keep that same rug — same shape, same size relative "
    "to the furniture, same color, texture, and pattern, in the same spot — and show it identically "
    "in every view of this room. A round rug stays round: do not turn it into a rectangle, oval, or "
    "runner, do not resize it, recolor it, or add a second rug."
)

_RUG_CHANGE_REQUEST = re.compile(
    r"\b(?:new|replace|replacing|change|changing|swap|different|bigger|larger|smaller|remove|get rid of)\b"
    r"[^.!?\n]{0,40}\brugs?\b"
    r"|\brugs?\b[^.!?\n]{0,40}\b(?:replace|replaced|change|changed|swap|swapped|remove|removed)\b",
    re.I,
)


def customer_requested_rug_change(lead: Dict[str, Any] | None) -> bool:
    """True only when the customer's own answers ask for a different rug."""
    lead = lead or {}
    blob = " ".join(
        str(lead.get(key) or "")
        for key in ("goals", "biggest_challenge", "daily_improvement", "bothers_other", "notes", "must_stay")
    )
    return bool(_RUG_CHANGE_REQUEST.search(blob))


def rug_spec(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Structured rug from the plan (``deliverable.rug``) over the room-flow record. Empty when none."""
    deliverable = deliverable or {}
    spec: Dict[str, Any] = {}
    flow = deliverable.get("room_flow") if isinstance(deliverable.get("room_flow"), dict) else None
    if not flow:
        from room_flow import load_record

        flow = load_record(str((lead or {}).get("id") or deliverable.get("lead_id") or "")) or {}
    if isinstance(flow.get("rug"), dict):
        spec.update({k: v for k, v in flow["rug"].items() if v not in (None, "")})
    if isinstance(deliverable.get("rug"), dict):
        spec.update({k: v for k, v in deliverable["rug"].items() if v not in (None, "")})
    return spec


def _rug_size(spec: Dict[str, Any]) -> str:
    ft = spec.get("diameter_ft")
    m = spec.get("diameter_m")
    if ft and m:
        return f"about {ft:g} ft ({m:g} m) across"
    if ft:
        return f"about {ft:g} ft across"
    if m:
        return f"about {m:g} m across"
    return ""


def rug_description(spec: Dict[str, Any]) -> str:
    """One sentence naming the rug: shape, size, color, texture, pattern, placement."""
    if not spec:
        return ""
    shape = str(spec.get("shape") or "").strip().lower()
    head = f"a single {shape} rug" if shape else "a single rug"
    bits = [b for b in (_rug_size(spec),) if b]
    for key in ("color", "texture", "pattern"):
        value = " ".join(str(spec.get(key) or "").split())
        if value:
            bits.append(value)
    placement = " ".join(str(spec.get("placement") or "").split())
    sentence = head + (", " + ", ".join(bits) if bits else "")
    if placement:
        sentence += f", {placement}"
    return sentence


def rug_prompt_rails(lead: Dict[str, Any] | None, deliverable: Dict[str, Any] | None = None) -> str:
    """Rug lock for every after-generation prompt. Off when the customer asked for a different rug."""
    if customer_requested_rug_change(lead):
        return ""
    described = rug_description(rug_spec(lead, deliverable))
    if not described:
        return RUG_PRESERVE_RAILS
    return f"{RUG_PRESERVE_RAILS} THE RUG IN THIS ROOM IS {described}. Show exactly that rug."


def supporting_view_plan(lead: Dict[str, Any] | None) -> Tuple[Tuple[str, str, str], ...]:
    """Extra after views: (slot, edit instruction, board caption).

    Nursery views aim at the dresser, the rocker, and the door — not another
    window-and-crib hero. Other rooms get the same idea with their own subjects.
    """
    if is_nursery_space(lead):
        return NURSERY_SUPPORTING_VIEWS
    return GENERAL_SUPPORTING_VIEWS


def supporting_view_caption(lead: Dict[str, Any] | None, key: str) -> str:
    for slot, _instruction, caption in supporting_view_plan(lead):
        if slot == key:
            return caption
    return "Additional after view"


def nursery_storage_line(lead: Dict[str, Any] | None, storage_str: str) -> str:
    """Storage sentence inside the image prompt. Nursery must not ask for baskets-as-drawers."""
    if is_nursery_space(lead):
        return (
            "Tidy only what is loose. Keep the existing dresser and every drawer. "
            "Do not add baskets in place of drawers, and do not add large open cubbies. "
        )
    return (
        f"Add tidy storage for {storage_str}: matching baskets, "
        "labeled bins, streamlined shelving. Clear clutter from the floor and surfaces. "
    )


def nursery_draft_addon(lead: Dict[str, Any] | None) -> str:
    """User-message suffix so the photo and the rail sit in the same turn."""
    if not is_nursery_space(lead):
        return ""
    return (
        "This is a kids' room / nursery. Preserve the existing dresser and every drawer. "
        "If the dresser has six drawers, all six stay. Do not replace drawers with baskets. "
        "Do not add large open cubbies. Storage must reduce daily effort, not add a chore. "
        "State one shopping total that equals qty × price for every line. "
        "Do not add a blanket product or a heater. "
        "The crib interior stays clear: a fitted sheet and a wearable sleep sack only. "
        "No teddy bear, loose cushion, pillow, or loose blanket in the crib. "
        "Finish every sentence."
    ) + (
        " Preserve wall switches in their exact locations (including beside the door). "
        "Do not add a towel hanger near the door. "
        "Keep any family-photo collage as one calm grouping with negative space. "
    ) + (
        " This room has a space theme. Keep planets, the moon, rockets, and astronauts. "
        "On the crib wall use a personal space-explorer composition; reuse existing tactile "
        "space pieces; no rabbit or generic animal art. 3D decor stays securely mounted "
        "outside crib reach."
        if is_space_theme(lead)
        else ""
    )
