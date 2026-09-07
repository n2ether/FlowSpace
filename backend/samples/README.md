# Blueprint sample pages

Regenerate (no Mongo / AI / Stripe) from the bake-off garage fixture:

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Source: `backend/fixtures/bakeoff/garage_org_space.json` (six Brain layers + notes).

| File | What |
|---|---|
| `before_page1.png` / `before_page2.png` | Previous cream / forest magazine sample (replaced) |
| `flowspace-blueprint-sample.pdf` | Current site-palette Blueprint with six-layer reasoning |
| `flowspace-blueprint-sample-pageN.png` | Rasterized current pages (PyMuPDF) |
