# FlowSpace Solutions — Product Requirements Doc

## Problem statement (current)
FlowSpace Solutions helps homeowners, renters, property managers & businesses visualize
organized spaces with AI. The EXISTING marketing site (hero, before/after slider, packages,
gallery, FAQ — locked design) is preserved. We ADDED a full authenticated AI platform:
users upload a cluttered room photo, pick a room type + organization style, and AI generates
an organized version of the SAME room (preserving architecture), plus an organization plan,
shopping list with affiliate links, and a downloadable branded PDF report.

## Tech stack (as built on the Emergent platform)
- React + FastAPI + MongoDB (platform-managed; Node/Supabase from the original spec mapped to this stack).
- Auth: **Email + password (JWT)** — single login/signup screen accepting any email; bcrypt hashing, httpOnly `access_token` cookie (7-day) + Bearer; brute-force lockout; password reset via Resend email (`/reset-password`). (Replaced Emergent Google OAuth in Jun 2026 to remove a confusing double-prompt.)
- AI image: Replicate `black-forest-labs/flux-kontext-pro` (image-to-image, match_input_image).
- AI text: GPT-5.2 via Emergent Universal Key (organization plan + shopping list).
- Storage: Emergent Object Storage (original-room-images / generated-room-images / project-pdfs), served via authed backend endpoints.
- Payments: Stripe subscriptions (LIVE keys) — Pro $9.99 (price_1Tfm3YLjPaM58nJzBhAqXuuP), Premium $19.99 (price_1Tfm3SLjPaM58nJzVF3GHEM0).
- PDF: ReportLab. Trilingual EN/ES/PT.

## Membership / credits
- Free: 1 transformation (lifetime), watermarked, no PDF.
- Pro $9.99/mo: 10/mo, HD, PDF report, shopping list.
- Premium $19.99/mo: unlimited (fair-use 1000), HD, PDF, affiliate recommendations.

## Implemented (Jun 2026 — fork session)
- Backend modules: db, plans, storage_service, replicate_service, room_service (prompt+GPT plan+watermark+PDF), auth, projects (background AI pipeline + credit consume/refund), billing (subscriptions/portal/webhook), admin_api, server (public gallery + wiring).
- Frontend: AuthContext, AuthCallback, ProtectedRoute routing; pages Login, Dashboard, NewProject, Results (before/after slider, plan steps, shopping list w/ affiliate links, PDF), Billing; AppHeader, AuthImage/ProjectCompare; extended Admin (Overview/Users/Projects/Subscriptions/Transactions/Affiliate/Gallery). Landing/Header CTAs repointed to /app/new (old /intake + /success removed). Trilingual `app` block added.
- DB collections: users, user_sessions, projects, subscriptions, payment_transactions, affiliate_products, gallery.
- Verified: full E2E pipeline (Replicate gen, plan score 92, PDF) via test_e2e_pipeline.py; 22/22 backend pytest; 7/7 UI flows; landing visually unchanged.

## Next action items / backlog
- ✅ DONE (Jun 2026): Replaced Google OAuth with **email/password JWT auth** — single login/signup screen (any email), password reset via email, brute-force lockout, trilingual. Tested 9/9 UI flows + 22/22 API tests. Reset links pinned to trusted hosts.
- USER ACTION: **Redeploy** to push the new login experience to https://flowspace.solutions (the live site still has the old Google login until you redeploy).
- ✅ DONE (Jun 2026): PDF email delivery via Resend (auto + on-demand, BCC camila).
- ✅ DONE (Jun 2026): Stripe webhook — endpoint `we_1TfnOI…` registered at `https://flowspace.solutions/api/billing/webhook` (events: checkout.session.completed, customer.subscription.updated/deleted). STRIPE_WEBHOOK_SECRET set; signature verification active (forged→400); upgrade/cancel sync verified. Deployment-readiness check PASSED.
- USER ACTION: Click **Deploy** to push to production. Webhook delivery activates once flowspace.solutions points at the deployed app (Stripe retries until then).
- P1: Real affiliate tags/IDs (currently store-search URLs for Amazon/Home Depot/Lowe's/Container Store).
- P2: Atomic credit decrement (findOneAndUpdate) to close concurrent double-submit race.
- P2: Pin Stripe success/cancel origin to a trusted host (currently uses client origin_url).
- P2: Prune stale user_sessions on login.
- P3: Premium "multiple style variations" (generate 2-3 styles per upload).

## Test status
- Backend: 22/22 pytest (test_flowspace_api.py). E2E: test_e2e_pipeline.py (cost-incurring — run sparingly).
- Frontend: 7/7 flows. Admin password garage2025. See /app/auth_testing.md + /app/memory/test_credentials.md.
