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
| Room-flow zone map (PNG) | The standard Conceptual Zone Map / Flow Plan (`room_flow.py`): outline, window, door, furniture, zones, clear path, "each zone has one job", flow principle, why this helps, source rule |
| Companion PDF | Safety essentials, climate comfort, one why-it-helps paragraph, the consolidated shopping list, and one before/after page per source photo |

The Do Not list, extended notes, steps, and full safety copy are internal (`blueprint_consistency.internal_record`), not customer pages.

The garage bake-off still produces a companion PDF. Nico's nursery sample is the full set, including the dresser / budget corrections and the measured outline.

| File | What |
|---|---|
| `flowspace-blueprint-sample.pdf` | Garage companion guide with a synthetic before and after |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with no photos |
| `nicos-nursery-image-board.png` | Kids' room image board after nursery rails and budget alignment |
| `nicos-nursery-companion.pdf` | Matching companion guide |
| `nicos-nursery-zone-map.png` | Room-flow zone map from the measured outline record in `room_flows/` |

Image keys are documented in `backend/pdf_images.py`. Values are image bytes. An organized after is shown only when those bytes exist. Extra views are generated only after that after passes QA; otherwise the board crops the after or leaves the slots empty. The zone map says "Measured room outline" only when a measured outline was supplied (`room_flows/<lead id>.json` or `deliverable.room_flow`); otherwise it says "Approximate room outline". Furniture and zones are always approximate.
