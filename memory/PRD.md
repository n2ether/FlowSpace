# FlowSpace.Solutions — Product Requirements Document

## Problem Statement (original)
Rebuild FlowSpace.Solutions — an AI-powered room organization service. Users upload photos of cluttered rooms and receive AI-generated organized versions. Three consumer plans (Free / Plus / Premium). Keep existing emerald + slate color scheme, before/after sliders, and overall feel. No authentication. PDF deliverable is a placeholder for Plus/Premium.

## Architecture
- **Frontend:** React 19 + React Router 7 + Tailwind + Fraunces/Inter typography + react-compare-slider + react-dropzone + sonner toasts.
- **Backend:** FastAPI + Motor (MongoDB).
- **AI:** Gemini Nano Banana via `emergentintegrations.llm.chat` (`gemini-3.1-flash-image-preview`) for image-to-image transformation.
- **Payments:** Stripe Checkout via `emergentintegrations.payments.stripe.checkout` (one-time $10 / $20).
- **Email:** Resend (admin notification to `contact@flowspace.solutions`).
- **Storage:** MongoDB collections `payment_transactions`, `submissions`.

## User Personas
1. Busy parents drowning in garage / closet clutter.
2. Renters who want a visual plan before buying storage bins.
3. First-time homeowners overwhelmed by organization decisions.

## Core Requirements (static)
- Single-page landing with hero, value props, how-it-works, pricing (3 plans), gallery, FAQ, footer.
- Photo upload limits: Free=2, Plus=3, Premium=4. JPG/PNG/WebP only.
- AI transformation of every uploaded photo, served as base64 in result page.
- Stripe checkout for paid plans, polled success page that gates upload by paid `session_id`.
- Admin email with submission details + photos.
- Responsive across mobile / tablet / desktop.
- No authentication, no user accounts, no dashboards.

## What's Been Implemented (2026-06-14)
- Full responsive landing page with sticky header, hero before/after slider, value grid, 3-step "how it works", pricing cards (Free/Plus/Premium), filtered gallery with sliders, who-it's-for grid, FAQ accordion, CTA banner, footer.
- Plan-based upload flow with drag-and-drop, previews, remove/replace, name + email capture.
- Stripe one-time checkout for Plus ($10) and Premium ($20); free plan goes directly to upload.
- Success page polls `/api/checkout/status` and redirects to upload only when paid.
- Backend AI generation pipeline (Gemini Nano Banana, image-to-image, parallel per-photo).
- Result page renders each photo as a before/after slider; PDF placeholder copy for Plus/Premium.
- Resend email notification to `contact@flowspace.solutions` on every submission (background task).
- 14/14 backend pytest cases passing; end-to-end frontend flows verified by Playwright.

## Prioritized Backlog
### P0 — Blockers for production
- Configure Resend domain & verified sender (`SENDER_EMAIL` currently `onboarding@resend.dev`).
- Confirm Stripe live key + enable live webhook secret (`STRIPE_WEBHOOK_SECRET`).

### P1 — High value next
- Real PDF deliverable: server-side PDF (WeasyPrint / Puppeteer) bundling AI image, room category breakdown, and product/shopping list.
- Move image storage from base64 in Mongo to S3/GridFS to avoid DB bloat.
- Customer-facing email after submission (deliver the AI images + magic link to result page).
- Light optimization of the Gemini prompt for better "same-angle, same-room" results.

### P2 — Nice-to-have
- Mobile hamburger nav.
- Lightweight admin dashboard (protected) to review submissions.
- Optional 3D mockup add-on for Premium (Sora 2 or specialized 3D model).
- A/B testing for hero copy.
- SEO: meta tags, sitemap, OpenGraph images.

## Next Tasks (suggested order)
1. Verify Resend sender domain so admin emails reliably arrive.
2. Build real PDF generation pipeline.
3. Add customer-facing transactional email with result link.
4. Persist photos in object storage instead of MongoDB.
