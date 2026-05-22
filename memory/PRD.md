# FlowSpace — Product Requirements Doc

## Problem statement (original)
Create a webpage + app for a personalized home organization business. Hero with before/after, value props, how it works, what you get, 3 packages (Basic/Standard/Premium), before/after gallery, who it's for, FAQ, final CTA. Positioning: clarity, flow, mental relief. Trilingual EN/ES/PT-BR. White + green + blue accents.

## User personas
- Busy families / homeowners tired of clutter
- Client of the business (admin)
- 3rd-party builders (receive leads + photos to fulfill designs)

## Core requirements (static)
- Landing page with all 9 sections in specified order
- Multi-section questionnaire (modal + full-page) saved to MongoDB `leads`
- Stripe checkout (3 fixed packages: $79 / $149 / $299)
- Before/After gallery with filters; seeded + admin-editable
- Admin panel: leads + gallery CRUD + transactions
- Trilingual via LanguageContext (EN / ES / PT-BR)
- Before/After sliders (react-compare-slider)
- Earthy minimalist design — white/green/blue tones

## Implemented (Feb 2026 — session 2: Questionnaire + GridFS)
- **11-section Questionnaire** as a standalone modal (Landing CTAs) + full page (`/intake`):
  1. Space type (required)
  2. What bothers you (max 3) + other
  3. Desired feeling (max 3) + other
  4. Must stay items (free text)
  5. Storage needs (multi-select)
  6. Style + color preferences (multi-select)
  7. Budget (single select)
  8. DIY level (single select)
  9. Photo uploads (up to 8 × 10MB)
  10. Daily improvement (free text)
  11. Contact + package pick (required)
- **GridFS photo storage** via Motor (`uploads` bucket):
  - `POST /api/uploads/photo` (multipart) → `{id, url}`
  - `GET /api/uploads/photo/{id}` streams with proper content-type + cache headers
  - Validates image/*, rejects empty + >10MB
- **Lead model** extended with: bothers_about, bothers_other, desired_feeling, feeling_other, must_stay, storage_needs, style_prefs, color_prefs, budget, diy_level, daily_improvement
- **Admin panel** redesigned for richer lead display: chips for each multi-select field, photo thumbnails resolved via `REACT_APP_BACKEND_URL + /api/uploads/photo/{id}`
- **Trilingual** questionnaire (EN/ES/PT) — all 80+ option labels translated
- Dialog a11y: hidden DialogTitle/Description for screen readers

## Previously implemented (Dec 2025 — session 1)
- FastAPI + Stripe (emergentintegrations + raw stripe SDK fallback)
- MongoDB: leads, gallery, payment_transactions
- Auto-seed gallery on empty
- Admin auth via X-Admin-Token
- React + Tailwind + shadcn UI + Outfit/Manrope fonts
- Browser language auto-detect
- Before/After slider component
- Success polling page with Stripe fallback
- Rebrand from ClearSpace → FlowSpace (logo + name)

## Test status
- Backend: 7/7 pytest (questionnaire + uploads) + 23/23 original = all pass
- Frontend: 13/13 E2E flows pass (modal CTAs, 11-section nav, max-3 enforcement, multipart upload, /intake full-page, trilingual switching, admin display + photo render)
- Date: 2026-02-22

## Next action items
- P1: Email notifications — send completed rendering to a "completed folder" inbox + customer confirmation (deferred: user chose to skip until ready to integrate Resend/SendGrid)
- P1: Branded PDF deliverable when design is "ready"
- P2: Stripe-success → Questionnaire linkage (attach session_id to lead on `/intake?session_id=...`)
- P2: Image optimization — auto-compress >2MB uploads on the server
- P2: Replace seeded Unsplash gallery with real before/after photos
- P3: Testimonials section under gallery
- P3: JWT-based admin auth + rate limit
- P3: Analytics (GA4 + conversion events)
