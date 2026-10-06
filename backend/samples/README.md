# Blueprint samples

Regenerate (no Mongo / AI / Stripe):

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Every paid Blueprint is three files:

| File | What |
|---|---|
| Image board (PNG) | Photo-faithful after hero, 2–4 extra views or honest crops, the room-flow card (same zone-map plan as below), design moves, palette and materials, roadmap, and one list total |
| Room-flow zone map (PNG) | The standard Conceptual Zone Map / Flow Plan (`room_flow.py`): outline, window, door, furniture, zones with numbered markers matching the zones column, clear path, "each zone has one job", flow principle, why the FlowSpace zone approach helps, source rule |
| Companion PDF | Safety essentials, climate comfort, the "why the FlowSpace zone approach helps" paragraph (same words as the zone map), the consolidated shopping list, and one before/after page per source photo |

The Do Not list, extended notes, steps, and full safety copy are internal (`blueprint_consistency.internal_record`), not customer pages.

The garage bake-off still produces a companion PDF. Nico's nursery sample is the full set, including the dresser / budget corrections and the measured outline.

| File | What |
|---|---|
| `flowspace-blueprint-sample.pdf` | Garage companion guide with a synthetic before and after |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with no photos |
| `nicos-nursery-image-board.png` | Kids' room image board after nursery rails and budget alignment |
| `nicos-nursery-companion.pdf` | Matching companion guide |
| `nicos-nursery-zone-map.png` | Room-flow zone map from the measured outline record in `room_flows/` |

Companion pages are never near-empty: each before/after pair sizes its photos to the page, a short shopping-list tail shares its page with the next pair, and `tests/test_pdf_page_fill.py` holds every page at 40% or more of its frame (`pdf_generator.companion_page_fill`). Customer copy is evergreen (no ages, dates, week labels, or countdowns; `evergreen_copy.py`).

Nicholas's Nursery curated list (`shopping_links/<lead id>.json`) is nine items, $195. The 4×6 nuLOOM Deepika rug was retired: no Target rug verified on 2026-10-06 was round, about 5 ft, low pile, washable, non-slip, and warm neutral, so the room keeps its existing round rug. The record's `retired` list drops that row from a stored deliverable, so every surface shows the same total. The zone map draws that rug round at 1.5 m from the record's `rug` spec.

Image keys are documented in `backend/pdf_images.py`. Values are image bytes. An organized after is shown only when those bytes exist. Extra views are generated only after that after passes QA; otherwise the board crops the after or leaves the slots empty. The zone map says "Measured room outline" only when a measured outline was supplied (`room_flows/<lead id>.json` or `deliverable.room_flow`); otherwise it says "Approximate room outline". Furniture and zones are always approximate.
