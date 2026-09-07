# Bake-off fixture — completed org-space case

**File:** `garage_org_space.json`

A completed two-car **garage** Blueprint (not a bedroom). Built from the shipped Ada Lovelace garage sample in `backend/samples/` and `tests/test_pdf_build.py`, then filled with the six Brain layers so a reviewer can answer Ryan’s questions without guessing.

| Ryan question | Where to read it |
|---|---|
| Routine | `blueprint_layers.human_need.routine` → PDF card **Human need** |
| Possessions | `observation.possessions` + `validation.possession_respect` |
| Physical fit | `spatial_constraint` + `validation.fit` |
| Budget | `validation.budget_band` (kit **$227** inside **$100–$300**) |
| Why it should work | `recommendation.why_it_should_work` + Validation checks |

Hard rules in the fixture: windows/dims **~95%**, **preserve_shell**, **no invented floor plan**, paint **optional**.

## Regenerate the sample PDF (no Mongo / AI / Stripe)

```bash
cd backend
python scripts/render_sample_blueprint.py
```

Writes `backend/samples/flowspace-blueprint-sample.pdf` and page rasters from this fixture.

## Sample / inspect layers only

```bash
cd backend
python -c "
import json
from pathlib import Path
from blueprint_layers import ryan_answers, layers_complete
doc = json.loads(Path('fixtures/bakeoff/garage_org_space.json').read_text())
layers = doc['deliverable']['blueprint_layers']
assert layers_complete(layers)
print(json.dumps(ryan_answers(layers), indent=2))
"
```

## How this fixture was chosen

No live customer PII is in the repo. This is the canonical completed org-space case already used for PDF samples (garage, Ada Lovelace). Layers were authored to match that plan — not invented architecture.

To refresh from a future real lead: take a delivered garage/closet/laundry/pantry/mudroom/storage deliverable, run it through `draft_deliverable` (or admin **Draft with AI**), persist `blueprint_layers`, and replace this JSON. Do not invent dimensions when sampling.
