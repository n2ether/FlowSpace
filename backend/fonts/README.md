# Embedded Design Plan fonts

Bundled so Railway’s slim Python image matches flowspace.solutions.

| File | Family | Use | License |
|---|---|---|---|
| `Montserrat-*.ttf` | [Montserrat](https://github.com/JulietaUla/Montserrat) | Brand hierarchy (board, Room Flow, Companion Guide, email) | SIL OFL 1.1 |
| `Fraunces-*.ttf` | [Fraunces](https://github.com/undercasetype/Fraunces) | Legacy display fallback | SIL OFL 1.1 |
| `Inter-*.ttf` | [Inter](https://rsms.me/inter/) | Legacy body fallback | SIL OFL 1.1 |

`image_board.py` and `room_flow.py` load Montserrat directly. `pdf_generator.py` registers Montserrat as `FSSerif*` / `FSSans*` and falls back to Times / Helvetica if a file is missing.

Regenerate a sample PDF (no Mongo / AI / Stripe):

```bash
cd backend
python scripts/render_sample_blueprint.py
# writes backend/samples/flowspace-blueprint-sample.pdf and page PNGs
```
