# Blueprint sample pages

Regenerate (no Mongo / AI / Stripe) from the bake-off garage fixture:

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Source: `backend/fixtures/bakeoff/garage_org_space.json` (six Brain layers + notes).

## Image keys (`build_pdf(..., images=)`)

Documented in [`backend/pdf_images.py`](../pdf_images.py). Values are **image bytes**, not URLs.

| Key | Role |
|---|---|
| `front_view` | Page-1 hero. Live automation puts successful FLUX (Kontext) bytes here. |
| `front_view_kind` | `organized` (FLUX), `original` (labeled customer photo when FLUX fails), or `placeholder`. |
| `floor_plan` | Optional. Only a real plan — never invented. |
| `view_1` / `view_2` / `view_3` | Optional detail-card photos. |
| `customer_photos` | List of original uploads for later reference pages. |

**UX if FLUX fails:** use the customer original as a labeled interim hero (`front_view_kind="original"`). If no original exists, keep the branded mint “Organized view coming soon” panel. The pipeline does not crash.

| File | What |
|---|---|
| `before_page1.png` / `before_page2.png` | Previous cream / forest magazine sample (replaced) |
| `flowspace-blueprint-sample.pdf` | Current site-palette Blueprint **with** a synthetic organized hero (FLUX stand-in) |
| `flowspace-blueprint-sample-placeholders.pdf` | Same plan with `images={}` — mint placeholder hero |
| `flowspace-blueprint-sample-pageN.png` | Rasterized current pages with hero image (PyMuPDF) |
| `flowspace-blueprint-placeholders-pageN.png` | Rasterized placeholder pages (PyMuPDF) |
