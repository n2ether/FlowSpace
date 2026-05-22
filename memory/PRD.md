# FlowSpace — Product Requirements Doc

## Problem statement (original)
Create a webpage + app for a personalized home organization business. Hero with before/after, value props, how it works, what you get, 3 packages (Basic/Standard/Premium), before/after gallery, who it's for, FAQ, final CTA. Positioning: clarity, flow, mental relief. Trilingual EN/ES/PT-BR. White + green + blue accents.

## User personas
- Busy families / homeowners tired of clutter
- Client of the business (admin) — fills out design plans and sends deliverables
- 3rd-party builders — receive leads + photos to fulfill designs

## Core requirements
- Landing page with all 9 sections in specified order
- Multi-section questionnaire (modal + full-page) saved to MongoDB `leads`
- Stripe checkout (3 fixed packages: $79 / $149 / $299) — *deferred while we polish workflow*
- Before/After gallery with filters; seeded + admin-editable
- Admin panel: leads + gallery CRUD + transactions + **design deliverable editor**
- Trilingual via LanguageContext (EN / ES / PT-BR)
- Branded PDF deliverable (`reportlab`) — design plan with FlowSpace header bar
- Earthy minimalist design — white/green/blue tones

## Implemented

### Session 5 — AI 3D Front View Rendering (Feb 24, 2026)
- **`/app/backend/ai_image_generator.py`** — Gemini Nano Banana (`gemini-3.1-flash-image-preview`) via `emergentintegrations` + Emergent Universal Key. Builds a contextual prompt from `style_prefs`, `color_prefs`, `desired_feeling`, `storage_needs`, `must_stay`, `bothers_about`, plus the deliverable's `wall_color_*` and `zones`. Pulls up to **2 customer-uploaded photos from GridFS** as ImageContent references so the model preserves the actual room footprint while reimagining contents.
- **`POST /api/admin/leads/{id}/deliverable/generate-image?slot=front_view`** — admin-only. Returns `{slot, url}` (relative GridFS URL); persists image to GridFS w/ correct content-type (JPEG/PNG auto-detected from model output) and updates the deliverable's `{slot}_url` field. Valid slots: `front_view`, `view_1`, `view_2`, `view_3`, `floor_plan`. Typical latency: 12–20s.
- **"Generate with AI" button** on the 3D Front View slot in `AdminDeliverable.jsx` (violet Sparkles styling, `data-testid=d-img-front-ai`). Saves form first so the prompt uses latest wall-color + zones.
- Smoke-tested end-to-end: lead create → generate → image fetch → PDF embed (919 KB PDF, valid JPEG).

### Session 4 — AI "Draft my plan" (Feb 22, 2026)
- **`/app/backend/ai_drafter.py`** — Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via emergentintegrations + Emergent Universal Key. Humanizes questionnaire keys (bothers/feeling/storage/style/colors/budget/diy) into a natural prompt, asks for strict JSON, tolerantly parses the response (strips fences, regex-extracts JSON object), coerces types, validates wall_color_hex.
- **`POST /api/admin/leads/{id}/deliverable/draft`** — admin-only endpoint that returns `{draft: {...}}` matching the Deliverable schema. Typical latency: 15–30s.
- **"Draft with AI" button** on the deliverable editor (violet styling, Sparkles icon, `data-testid=deliverable-ai-draft`).
- **Fill-empty-only merge logic** in `applyDraft()` — preserves anything the admin has already typed (text fields, lists with any content, custom hex). Wall-color hex replaces only the default `#cfd7d3`.

### Session 3 — Branded PDF Deliverable (Feb 22, 2026)
- **`/app/backend/pdf_generator.py`** — reportlab-based PDF builder. Brand bar w/ logo + tagline ("Clear space. Create flow. Live better.") + page numbers on every page.
- **`Deliverable` model + 3 admin endpoints** (`GET/PUT /api/admin/leads/{id}/deliverable`, `GET .../pdf`). Idempotent upsert into `deliverables` collection.
- **Auto-resolves** customer-uploaded photos from GridFS into the PDF body; also supports admin-provided URLs (relative GridFS or absolute http) for the 5 rendering images.
- **PDF structure** — Page 1: greeting + Overall Plan (3D front view, floor plan, 3 additional views, needs/zones, wall-color block w/ swatch, shopping table with running total, design strategy, action plan, benefits, notes). Pages 2–N: customer reference photos (one per page). Last page: Design Summary + Attachment Note + Shopping Links table + "The FlowSpace Design Team" sign-off.
- **`AdminDeliverable.jsx`** — full deliverable editor route at `/admin/leads/:leadId/design`. Inline list editors, zone editor, shopping list with qty/price columns, wall-color picker (HTML5 color input + hex), 5 image-upload fields with thumbnails. "Save" + "Generate PDF" actions.
- **"Design" button** added to every lead row in the admin leads tab.
- Graceful fallbacks: invalid/missing images render labeled placeholders; absent fields render "—".

### Session 2 — Questionnaire Modal + GridFS (Feb 2026)
- 11-section trilingual questionnaire as modal (Landing CTAs) + full page (`/intake`)
- Lead model extended w/ bothers, feeling, must_stay, storage_needs, style/color prefs, budget, diy_level, daily_improvement
- `POST /api/uploads/photo` + `GET /api/uploads/photo/{id}` via Motor AsyncIOMotorGridFSBucket
- Admin panel redesigned with chip-based field display + GridFS photo thumbnails

### Session 1 — MVP (Dec 2025)
- FastAPI + Stripe via emergentintegrations
- MongoDB collections: leads, gallery, payment_transactions
- React + Tailwind + shadcn UI; Outfit + Manrope fonts
- Trilingual EN/ES/PT with browser auto-detect
- 9-section landing page; Before/After slider; Admin auth via X-Admin-Token
- Rebrand ClearSpace → FlowSpace

## Test status (cumulative)
| Iteration | Backend | Frontend |
|-----------|---------|----------|
| 1 | 22/23 → 23/23 | 15/15 |
| 2 | regression OK | rebrand OK |
| 3 (Questionnaire+GridFS) | 7/7 | 13/13 |
| 4 (PDF Deliverable) | 11/11 | all flows |
| **5 (AI Draft)** | **15/15** | **all flows** |

## Next action items (deferred per user)
- **P1: Email notifications** — send completed rendering PDF to "completed folder" inbox + customer confirmation (Resend recommended) — *user asked to skip for now (Session 5)*
- **P1: Stripe integration revival** — user paused; was working in MVP
- P2: Allow "Generate with AI" on the other rendering slots (view_1/2/3, floor_plan) in the admin UI — endpoint already supports them
- P2: Public share link for deliverable PDF (`/d/{token}`) so customer can view without admin auth
- P2: Server-side image compression for very large uploads
- P2: Replace seeded Unsplash gallery with real before/after photos via admin upload
- P3: Testimonials section, JWT admin auth, GA4 analytics
- P3 (refactor): Extract Stripe + Deliverable sections from `server.py` into `routers/` modules (file is ~700 lines)
