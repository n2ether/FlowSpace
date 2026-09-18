# Blueprint sample pages

Regenerate (no Mongo / AI / Stripe) from the bake-off garage fixture:

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Source: `backend/fixtures/bakeoff/garage_org_space.json` (six Brain layers + notes).

## Layout

| Page | What |
|---|---|
| 1 | Dashboard overview (hero, space needs, optional paint, zone plan, extra views, strategy / action / benefits) |
| 2 | Shopping list + estimated budget, DIY this week, six-layer reasoning, compact Before \| After when a photo exists |
| 3 | Only if Before \| After cannot share the DIY sheet |

## Image keys (`build_pdf(..., images=)`)

Documented in [`backend/pdf_images.py`](../pdf_images.py). Values are **image bytes**, not URLs.

| Key | Role |
|---|---|
| `front_view` | Page-1 hero. Live automation puts successful FLUX (Kontext) bytes here. |
| `front_view_kind` | `organized` (FLUX), `original` (labeled customer photo when FLUX fails), or `placeholder`. |
| `before` | DIY-page **Before** — customer original photo. |
| `after` | DIY-page **After** — FLUX organized render. Never invented. |
| `floor_plan` | Optional. Only a real plan — never invented. |
| `view_1` / `view_2` / `view_3` | Optional extra views on the dashboard. Omitted when missing. |
| `customer_photos` | Extra original uploads (first photo is also `before`). |

**UX if FLUX fails:** use the customer original as a labeled interim hero (`front_view_kind="original"`). If no original exists, keep the branded mint “Organized view coming soon” panel. The pipeline does not crash.

| File | What |
|---|---|
| `flowspace-blueprint-sample.pdf` | Current site-palette Blueprint **with** organized hero + DIY-page Before \| After |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with `images={}` — mint placeholder hero |
| `flowspace-blueprint-sample-pageN.png` | Rasterized current pages with hero image (PyMuPDF) |
| `flowspace-blueprint-placeholders-pageN.png` | Rasterized placeholder pages (PyMuPDF) |
