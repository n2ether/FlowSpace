# Blueprint samples

Regenerate (no Mongo / AI / Stripe):

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Every paid Blueprint is two files:

| File | What |
|---|---|
| Image board (PNG) | Photo-faithful after hero, 2–4 extra views or honest crops, approximate top view (furniture, window, door, clear path), design moves, palette and materials, roadmap, and one list total |
| Companion PDF | Full steps, shopping list and links, safety, climate, maintenance, and the weekly reset |

The garage bake-off still produces a companion PDF. Nico's nursery sample is the two-file pair, including the dresser / budget corrections.

| File | What |
|---|---|
| `flowspace-blueprint-sample.pdf` | Garage companion guide with a synthetic before and after |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with no photos |
| `nicos-nursery-image-board.png` | Kids' room image board after nursery rails and budget alignment |
| `nicos-nursery-companion.pdf` | Matching companion guide |

Image keys are documented in `backend/pdf_images.py`. Values are image bytes. An organized after is shown only when those bytes exist. Extra views are generated only after that after passes QA; otherwise the board crops the after or leaves the slots empty. The room plan is an approximate top view (furniture, window, door, clear path), not a measured floor plan.
