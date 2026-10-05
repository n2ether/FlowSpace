"""Per-lead curated shopping links, plus short generic retailer-search fallbacks.

Admin-curated product pages live in ``shopping_links/<lead id>.json``.
When no curated row exists, we fall back to a short retailer search URL and
label it plainly as ``Search at <Retailer>`` — never an invented SKU.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

RECORDS_DIR = Path(__file__).resolve().parent / "shopping_links"
DEFAULT_RETAILER = "Target"
DEFAULT_SEARCH_BASE = "https://www.target.com/s?searchTerm="

# Keep search terms short and clean when no curated product page exists.
_STOP = {
    "a", "an", "the", "and", "or", "for", "with", "of", "to", "in", "on",
    "single", "optional", "layering", "under", "existing", "reduces", "drafts",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def short_search_term(name: str, *, max_words: int = 6) -> str:
    """Collapse a long shopping-list name into a short retailer search phrase."""
    raw = _clean(name)
    # Drop parenthetical detail.
    raw = re.sub(r"\([^)]*\)", " ", raw)
    raw = re.sub(r"[—–\-]+", " ", raw)
    words = [w for w in re.findall(r"[A-Za-z0-9×x]+", raw) if w.lower() not in _STOP]
    if not words:
        words = re.findall(r"[A-Za-z0-9]+", _clean(name))[:max_words]
    return " ".join(words[:max_words])


def search_label(retailer: str) -> str:
    retailer = _clean(retailer) or DEFAULT_RETAILER
    return f"Search at {retailer}"


def load_record(lead_id: str) -> Optional[Dict[str, Any]]:
    lead_id = _clean(lead_id)
    if not lead_id or not re.fullmatch(r"[A-Za-z0-9-]{8,64}", lead_id):
        return None
    path = RECORDS_DIR / f"{lead_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _from_record_item(item: Dict[str, Any]) -> Dict[str, str]:
    name = _clean(item.get("name"))
    url = _clean(item.get("url"))
    retailer = _clean(item.get("retailer")) or DEFAULT_RETAILER
    link_type = _clean(item.get("link_type") or "product").lower()
    if link_type not in {"product", "search"}:
        link_type = "search" if "/s?" in url or "search" in url.lower() else "product"
    label = _clean(item.get("label"))
    if not label:
        label = search_label(retailer) if link_type == "search" else f"View at {retailer}"
    return {
        "name": name,
        "url": url,
        "retailer": retailer,
        "link_type": link_type,
        "label": label,
    }


def curated_links(lead_id: str) -> List[Dict[str, str]]:
    record = load_record(lead_id)
    if not record:
        return []
    out: List[Dict[str, str]] = []
    for item in record.get("items") or []:
        if not isinstance(item, dict):
            continue
        row = _from_record_item(item)
        if row["name"] and row["url"]:
            out.append(row)
    return out


def deliverable_links(deliverable: Dict[str, Any]) -> List[Dict[str, str]]:
    """Admin-curated links already stored on the deliverable document."""
    provided: List[Dict[str, str]] = []
    for link in deliverable.get("shopping_links") or []:
        if not isinstance(link, dict):
            continue
        name = _clean(link.get("name") or link.get("url"))
        url = _clean(link.get("url"))
        if not (name or url):
            continue
        retailer = _clean(link.get("retailer")) or DEFAULT_RETAILER
        link_type = _clean(link.get("link_type") or "").lower()
        if link_type not in {"product", "search"}:
            link_type = "search" if (not url or "/s?" in url or "searchTerm=" in url) else "product"
        label = _clean(link.get("label"))
        if not label:
            label = search_label(retailer) if link_type == "search" else f"View at {retailer}"
        provided.append(
            {
                "name": name or url,
                "url": url,
                "retailer": retailer,
                "link_type": link_type,
                "label": label,
            }
        )
    return provided


def fallback_search_links(deliverable: Dict[str, Any], *, retailer: str = DEFAULT_RETAILER) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for item in deliverable.get("shopping_list") or []:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        if not name:
            continue
        term = short_search_term(name)
        links.append(
            {
                "name": name,
                "url": f"{DEFAULT_SEARCH_BASE}{quote_plus(term)}",
                "retailer": retailer,
                "link_type": "search",
                "label": search_label(retailer),
            }
        )
    return links


def resolve_shopping_links(
    lead: Optional[Dict[str, Any]],
    deliverable: Optional[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Prefer per-lead file, then deliverable.shopping_links, then short searches."""
    lead = lead or {}
    deliverable = deliverable or {}
    lead_id = _clean(lead.get("id") or deliverable.get("lead_id"))
    curated = curated_links(lead_id) if lead_id else []
    if curated:
        return curated
    provided = deliverable_links(deliverable)
    if provided:
        return provided
    return fallback_search_links(deliverable)


def links_are_search_only(links: List[Dict[str, str]]) -> bool:
    if not links:
        return False
    return all(str(link.get("link_type") or "") == "search" for link in links)
