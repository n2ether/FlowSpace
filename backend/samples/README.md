# Blueprint samples

Regenerate (no Mongo / AI / Stripe):

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Every paid Blueprint is two files:

| File | What |
|---|---|
| Image board (PNG) | Hero before/after, detail views, approximate room plan, what's-new callouts, palette, product references, roadmap, and one list total |
| Companion PDF | Full steps, shopping list and links, safety, climate, maintenance, and the weekly reset |

The garage bake-off still produces a companion PDF. Nico's nursery sample is the two-file pair, including the dresser / budget corrections.

| File | What |
|---|---|
| `flowspace-blueprint-sample.pdf` | Garage companion guide with a synthetic before and after |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with no photos |
| `nicos-nursery-image-board.png` | Kids' room image board after nursery rails and budget alignment |
| `nicos-nursery-companion.pdf` | Matching companion guide |

Image keys are documented in `backend/pdf_images.py`. Values are image bytes. An organized after is shown only when those bytes exist. The room plan on the board is a zone diagram, not a measured floor plan.
