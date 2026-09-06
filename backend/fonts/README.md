# Embedded Blueprint fonts

Bundled so Railway’s slim Python image matches flowspace.solutions.

| File | Family | Use | License |
|---|---|---|---|
| `Fraunces-*.ttf` | [Fraunces](https://github.com/undercasetype/Fraunces) | Display / titles | SIL OFL 1.1 |
| `Inter-*.ttf` | [Inter](https://rsms.me/inter/) | Body / UI | SIL OFL 1.1 |

`pdf_generator.py` registers these as `FSSerif*` / `FSSans*` and falls back to Times / Helvetica if a file is missing.

Regenerate a sample PDF (no Mongo / AI / Stripe):

```bash
cd backend
python scripts/render_sample_blueprint.py
# writes backend/samples/flowspace-blueprint-sample.pdf and page PNGs
```
