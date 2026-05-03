# ClearSpace — Product Requirements Doc

## Problem statement (original)
Create a webpage + app for a garage storage solutions business. Hero with before/after, value props, how it works, what you get, 3 packages (Basic/Standard/Premium), before/after gallery, who it's for, FAQ, final CTA. Positioning: clarity, flow, mental relief. Trilingual EN/ES/PT-BR. White + green + blue accents.

## User choices
- Multi-step intake form (photos + questions) saved to DB + simple contact
- Stripe checkout for paid plans + intake fallback
- Gallery: placeholder seeds + admin upload panel
- Trilingual (EN / ES / PT-BR)
- Colors: white base, green details, blue accents

## User personas
- Busy families / homeowners tired of clutter
- Client of the business (admin)

## Core requirements (static)
- Landing page with all 9 sections in specified order
- Multi-step intake form (4 steps) saved to MongoDB `leads`
- Stripe checkout (3 fixed packages: $79 / $149 / $299)
- Before/After gallery with filters; seeded + admin-editable
- Admin panel: leads + gallery CRUD + transactions
- Trilingual via LanguageContext
- Before/After sliders (react-compare-slider)

## Implemented (Dec 2025 — session 1)
- FastAPI backend with Stripe via emergentintegrations (+ raw stripe SDK fallback for status)
- MongoDB collections: leads, gallery, payment_transactions
- Auto-seed gallery on empty
- Admin auth via X-Admin-Token = ADMIN_PASSWORD
- React frontend with Tailwind + shadcn UI, Outfit + Manrope fonts
- Language context with browser auto-detect; EN/ES/PT
- All 9 landing sections + hero before/after slider
- Multi-step intake with photo upload (base64 inline), validation, language-aware
- Success polling page with graceful fallback on Stripe error
- Admin login + dashboard (tabs: Leads / Gallery / Transactions)

## Test status
- Backend: 22/23 initial → fixed Stripe status endpoint → verified
- Frontend: 15/15 flows pass

## Next action items
- P1: Email notifications to admin on new lead (SendGrid/Resend)
- P1: Show completed transaction info on Success page and tie back to lead
- P2: Testimonials section below gallery
- P2: Replace photo base64 with cloud storage (S3 / Cloudinary) for large uploads
- P2: Analytics (conversion tracking)
- P3: JWT-based admin auth + rate limit
