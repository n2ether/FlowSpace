# FlowSpace.solutions

AI-powered room organization and mental-health-focused transformation site for
FlowSpace.

The customer uploads 2-4 photos of a cluttered room, completes an intake form,
and receives:

- AI-organized room images that preserve the original room structure.
- A PDF organization plan with storage solutions, DIY steps, budget guidance,
  and Walmart/Target/IKEA search links.
- A calm walkthrough video when video generation succeeds.
- A results page with downloads.

## Provider choices for production

This build is configured for:

1. **Replicate** for image editing.
2. **Runway** for virtual walkthrough video.
3. **Stripe** for checkout.

The relevant environment variables are listed in
`docs/flowspace-production-env.example`.

Minimum production settings:

```bash
IMAGE_PROVIDER=replicate
REPLICATE_API_TOKEN=r8_...

VIDEO_PROVIDER=runway
RUNWAY_API_KEY=key_...

STRIPE_SECRET_KEY=sk_live_...
REQUIRE_PAYMENT_FOR_ROOM_JOBS=true

MONGO_URL=mongodb+srv://...
DB_NAME=flowspace
REACT_APP_BACKEND_URL=https://api.flowspace.solutions
PUBLIC_APP_URL=https://flowspace.solutions
CORS_ORIGINS=https://flowspace.solutions
```

Optional but recommended:

```bash
EMERGENT_LLM_KEY=...
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=Ryan at FlowSpace <hello@flowspace.solutions>
```

If SMTP is not configured, jobs still complete and the results page still works;
the completion email is simply marked as skipped.

## Main routes

Customer:

- `/` - landing page
- `/checkout` - package selection and Stripe checkout
- `/success` - verifies the Stripe session before upload
- `/upload` - photo upload and room intake form for paid sessions
- `/results/:jobId` - generated images, plan, PDF, and video download

Admin:

- `/admin/login`
- `/admin/jobs` - automation job dashboard
- `/admin` - legacy leads/gallery/payment dashboard

Backend API:

- `/api/process-room`
- `/api/generate-images`
- `/api/generate-plan`
- `/api/generate-pdf`
- `/api/generate-video`
- `/api/jobs/{jobId}`
- `/api/admin/jobs`
- `/api/admin/provider-status`

## Processing stages

By default, `/api/process-room` requires a paid Stripe checkout session. The
success page passes the verified `session_id` to `/upload`, and the backend
marks that session as used when it creates the room job. This prevents direct
upload processing without payment and prevents one paid session from creating
multiple jobs.

Room jobs move through:

```text
pending -> uploaded -> image_processing -> image_complete ->
plan_generating -> pdf_generating -> video_generating -> complete
```

Failures are recorded on the job. If one image fails, other images continue. If
video generation fails, the PDF is still delivered and the job can complete.

## Local verification

Provider/env readiness check:

```bash
python3 scripts/check_flowspace_env.py
```

The check reports whether required settings are present without printing secret
values. The admin dashboard also shows provider readiness at `/admin/jobs`.

Backend syntax check:

```bash
python3 -m py_compile backend/server.py backend/ai_image_generator.py backend/ai_drafter.py backend/pdf_generator.py backend/video_generator.py
```

Frontend build:

```bash
cd frontend
yarn install --frozen-lockfile
yarn build
```
