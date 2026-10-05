"""Customer-facing Blueprint presentation.

The portrait PNG, the phone page, the companion PDF, and the final email
all read this same plan. It carries copy and honesty flags only — never
image-model text, and never internal review language.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from blueprint_consistency import companion_sections
from image_board import _clean, board_spec, customer_view_caption


def _shopping(deliverable: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = _clean(str(item.get("name") or ""))
        if not name:
            continue
        try:
            qty = float(item.get("qty", 1) or 1)
            price = float(item.get("price", 0) or 0)
        except (TypeError, ValueError):
            qty, price = 1.0, 0.0
        sub = qty * price
        if sub and abs(sub - round(sub)) < 0.01:
            price_label = f"${sub:,.0f}"
        elif sub:
            price_label = f"${sub:,.2f}"
        else:
            price_label = "Confirm price"
        rows.append(
            {
                "name": name,
                "qty": int(qty) if qty.is_integer() else qty,
                "price": price_label,
            }
        )
    return rows


def _gallery(
    spec: Dict[str, Any],
    media: Optional[List[Dict[str, Any]]],
    lead: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    images = spec.get("images") or {}
    pairs = images.get("source_pairs") or []
    media = media or []
    gallery: List[Dict[str, Any]] = []
    if isinstance(pairs, list) and pairs:
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                continue
            extra = media[index] if index < len(media) and isinstance(media[index], dict) else {}
            label = str(pair.get("label") or extra.get("label") or f"SOURCE_{index + 1:02d}")
            after_label = str(pair.get("after_label") or extra.get("after_label") or f"AFTER_{index + 1:02d}")
            after_url = extra.get("after_url") or None
            has_after = bool(pair.get("after")) or bool(after_url)
            gallery.append(
                {
                    "label": label,
                    "after_label": after_label,
                    "before_url": extra.get("before_url") or extra.get("source_url") or None,
                    "after_url": after_url,
                    "missing": not has_after,
                    "caption": customer_view_caption(index, lead, missing=not has_after),
                }
            )
        return gallery

    hero_url = None
    if media and isinstance(media[0], dict):
        hero_url = media[0].get("after_url") or None
    if spec.get("claims_organized_photo") or hero_url:
        gallery.append(
            {
                "label": "SOURCE_01",
                "after_label": "AFTER_01",
                "before_url": (media[0].get("before_url") if media and isinstance(media[0], dict) else None),
                "after_url": hero_url,
                "missing": not (spec.get("claims_organized_photo") or hero_url),
                "caption": spec.get("hero_label") or "Organized view",
            }
        )
    return gallery


def build_presentation(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
    images: Optional[Dict[str, Any]] = None,
    *,
    lead_id: str = "",
    media: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """JSON the phone page renders. Selectable sections, not a flattened board."""
    lead = lead or {}
    deliverable = deliverable or {}
    spec = board_spec(lead, deliverable, images or {})
    sections, doc = companion_sections(lead, deliverable)
    benefits = [str(x).strip() for x in (doc.get("benefits") or []) if str(x).strip()]
    return {
        "lead_id": lead_id,
        "headline": spec["headline"],
        "plan_title": spec["plan_title"],
        "outcome": spec["subtitle"],
        "intro": sections["intro"],
        "tagline": spec["tagline"],
        "theme_line": spec.get("theme_line") or "",
        "hero_mode": spec["hero_mode"],
        "hero_label": spec["hero_label"],
        "claims_organized_photo": bool(spec.get("claims_organized_photo")),
        "gallery": _gallery(spec, media, lead),
        "changes": spec.get("moves") or [],
        "plan": spec.get("topdown") or {},
        "palette": spec.get("palette") or [],
        "shopping": _shopping(doc),
        "shopping_total": sections.get("list_total") or "—",
        "stated_budget": sections.get("stated_budget") or "",
        "roadmap": spec.get("roadmap") or [],
        "steps": sections.get("steps") or [],
        "safety": sections.get("safety_essentials") or [],
        "climate": sections.get("climate_essentials") or [],
        "why_it_helps": sections.get("why") or "",
        "warning_note": "Safety and climate are written once in the companion guide.",
        "reset_title": sections.get("reset_title") or "Weekly reset",
        "reset": sections.get("maintenance") or "",
        "benefits": benefits,
        "preview_path": f"/admin/leads/{lead_id}/blueprint" if lead_id else "",
        "review": {
            "final": False,
            "package_status": str(deliverable.get("package_status") or ""),
        },
    }
