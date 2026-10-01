"""Space-specific prompt rails.

Kids' room / nursery rules are enforced here so plan drafting and image
generation share one wording. Image-provider swaps (FLUX today, OpenAI
Images on the in-flight branch) should keep calling ``image_prompt_rails``.
"""
from __future__ import annotations

import re
from typing import Any, Dict

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
    "If a dresser is visible, keep that exact dresser. A six-drawer dresser keeps all "
    "six drawers. Do not replace drawers with baskets. Do not add large open cubbies, "
    "cube organizers, or a new bank of open shelves. Tidy loose items and textiles only. "
    "Storage must make daily life simpler, not add a sorting chore. The room should "
    "still look meaningfully calmer and more intentional."
)

NURSERY_DRAFT_RULES = """
Kids' room / nursery rules (only when space_type is a kids' room, nursery, or the answers describe one):
- Preserve the existing dresser and every drawer. If it is a six-drawer dresser, all six drawers stay.
- Do not replace drawers with baskets. Do not recommend a basket system in place of the dresser.
- Do not add large open cubbies, Kallax-style cube storage, or a new wall of open shelves.
- Storage must simplify the day (fewer decisions), not add a sorting or labeling chore.
- Keep the real room, furniture, proportions, and any space theme already there. The refresh should still look meaningfully calmer.
- Shopping-list prices must add up to the budget figure you state. One kit total only.
- Write every customer-facing sentence in full. Do not leave a thought half-finished.
"""

NURSERY_DO_NOT = (
    "Do not replace dresser drawers with baskets.",
    "Do not add large open cubbies or cube storage.",
    "Do not place a portable heater or loose cord near the sleep area.",
)

_NURSERY_TEXT = re.compile(
    r"\b(nursery|kids?'?\s*room|child(?:ren)?'?s\s+room|baby\s+room)\b",
    re.I,
)
_SIX_DRAWER = re.compile(r"\b(six|6)[-\s]?drawer\b", re.I)


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


def image_prompt_rails(lead: Dict[str, Any] | None) -> str:
    """Extra image-edit constraint. Empty for closets, garages, and other rooms."""
    if not is_nursery_space(lead):
        return ""
    return NURSERY_IMAGE_RAILS


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
        "Finish every sentence."
    )
