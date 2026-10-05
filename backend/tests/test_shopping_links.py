from shopping_links import (
    curated_links,
    links_are_search_only,
    resolve_shopping_links,
    short_search_term,
    search_label,
)


LEAD = "9dbedfba-81fc-45e0-b99d-36e0a1de01bb"


def test_short_search_term_strips_parentheticals():
    term = short_search_term(
        "Thermal blackout curtain panel (single, 52×84 in., warm taupe or oatmeal linen-look)"
    )
    assert "curtain" in term.lower()
    assert "(" not in term
    assert len(term.split()) <= 6


def test_search_label():
    assert search_label("Target") == "Search at Target"
    assert search_label("Amazon") == "Search at Amazon"


def test_camila_curated_links_prefer_products():
    links = curated_links(LEAD)
    assert len(links) == 10
    products = [link for link in links if link["link_type"] == "product"]
    searches = [link for link in links if link["link_type"] == "search"]
    assert len(products) >= 8
    assert len(searches) >= 1
    assert any(link["label"] == "Search at Target" for link in searches)
    assert all(link["url"].startswith("http") for link in links)


def test_resolve_prefers_curated_file():
    links = resolve_shopping_links(
        {"id": LEAD},
        {"shopping_list": [{"name": "Bins", "qty": 1, "price": 10}]},
    )
    assert links[0]["name"].startswith("Furniture anti-tip")
    assert not links_are_search_only(links)


VERIFIED = {
    "Furniture anti-tip kit": ("https://www.target.com/p/qdos-zero-screw-furniture-anti-tip-kit-white-2pk/-/A-82320730", "product", 18, 1),
    "Thermal blackout curtain panel": ("https://www.target.com/p/lenox-serene-blackout-single-window-curtain-panel-taupe-52-w-x-84-l/-/A-1012628480", "product", 30, 2),
    "Adhesive window insulation film kit": ("https://www.target.com/p/3m-5pk-indoor-window-insulator-kit/-/A-94632174", "product", 15, 1),
    "Draft stopper for door": ("https://www.target.com/p/evideco-french-home-goods-taupe-draft-stopper-32/-/A-1010599541", "product", 12, 1),
    "Wall-mounted nursery organizer caddy": ("https://www.target.com/p/baby-diaper-caddy-and-nursery-organizer-for-baby-39-s-essentials/-/A-94794473", "product", 22, 1),
    "Cordless rechargeable LED night-light": ("https://www.target.com/p/ihome-magnetic-rechargeable-motion-sensor-night-light-auto-sensing-cordless-2-modes-mounts-anywhere/-/A-1010867043", "product", 16, 1),
    "Digital room thermometer": ("https://www.target.com/p/thermopro-tp49w-mini-hygrometer-thermometer-with-large-digital-view-indoor-thermometer-humidity-gauge-monitor-for-greenhouse-cellar-in-white/-/A-80783749", "product", 14, 1),
    "Felt wall decor": ("https://www.target.com/s?searchTerm=felt%20moon%20planet%20wall%20decor", "search", 10, 2),
    "Low-profile woven storage basket": ("https://www.target.com/p/household-essentials-natural-seagrass-basket-with-handles-natural-woven-wicker-storage-basket-great-for-decoration-or-organization/-/A-1011210373", "product", 18, 1),
    "Soft cotton area rug": ("https://www.target.com/p/nuloom-deepika-contemporary-abstract-cotton-area-rug-4-x-6-beige/-/A-93015688", "product", 45, 1),
}


def test_camila_record_matches_the_verified_link_table():
    from shopping_links import load_record

    items = load_record(LEAD)["items"]
    assert len(items) == len(VERIFIED)
    for item in items:
        key = next(k for k in VERIFIED if item["name"].startswith(k))
        url, link_type, price, qty = VERIFIED[key]
        assert (item["url"], item["link_type"], item["price"], item["qty"]) == (url, link_type, price, qty)
        if link_type == "search":
            assert item["label"] == "Search at Target"
    assert sum(item["price"] * item["qty"] for item in items) == 240


def test_fallback_is_a_labeled_short_search():
    links = resolve_shopping_links(
        {"id": "no-such-lead-0000"},
        {"shopping_list": [{"name": "Clear stackable shoe boxes (set of 6, for the closet floor)"}]},
    )
    assert links[0]["label"] == "Search at Target"
    assert links[0]["link_type"] == "search"
    assert "set" not in links[0]["url"].split("searchTerm=")[1].lower()
    assert links_are_search_only(links)
