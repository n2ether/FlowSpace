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
