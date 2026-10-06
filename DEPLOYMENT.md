# FlowSpace — Railway Deployment Guide

> **Live site note (Sept 2026):** https://flowspace.solutions is still the
> Emergent-hosted marketing app (Emergent chrome / PostHog). The PDF → Resend
> pipeline in this repo only runs after you deploy **this** backend on Railway
> (or equivalent) and point the domain + Stripe webhook at it. Until then,
> customers will not receive Blueprint emails even though Plus/Premium sell a PDF.

## What you're deploying

Two Railway services from one GitHub repo:
1. **Backend** — FastAPI (Python), `/backend` folder
2. **Frontend** — React (Node), `/frontend` folder

## Prerequisites checklist

Before deploying, have these ready:
- [ ] Railway account (railway.app) — free tier works, $5/mo Hobby for production
- [ ] MongoDB Atlas free cluster (mongodb.com/atlas) — free M0 tier is fine
- [ ] Anthropic API key (console.anthropic.com) — plan draft + vision QA only
- [ ] OpenAI API key (platform.openai.com/api-keys) — organized after-image
- [ ] Resend API key (resend.com → API Keys)
- [ ] Stripe account with live keys (dashboard.stripe.com)
- [ ] Domain `flowspace.solutions` pointed to Railway (or use Railway subdomain for now)

---

## Step 1 — Push your code to GitHub

Your code is already in `github.com/n2ether/FlowSpace`. Just push the updated files:

```bash
git add -A
git commit -m "Add automation pipeline: Anthropic + Replicate + Resend + Railway config"
git push origin main
```

---

## Step 2 — Deploy the Backend on Railway

1. Go to **railway.app → New Project → Deploy from GitHub repo**
2. Select `n2ether/FlowSpace`
3. Railway will detect the root. You need to point it to the **`backend`** subfolder:
   - Click **Settings** on the service
   - Set **Root Directory** to `/backend`
   - Railway will find the `Dockerfile` automatically
4. Click **Variables** and add every key from `backend/.env.example`:

| Variable | Value |
|---|---|
| `MONGO_URL` | Your MongoDB Atlas connection string |
| `DB_NAME` | `flowspace` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` (Claude plan draft + vision QA — not used for pixels) |
| `OPENAI_API_KEY` | `sk-...` from [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Required for the organized after-image. Customer photo → Images **edit**; no photo → Images **generations**. Model: `gpt-image-2.5-sunburst`. Already set on the Backend service in production — redeploy Backend to pick up this path. The backend raises `OPENAI_API_KEY is not configured` if this is missing, and the board + PDF continue with the labeled original (or a placeholder). |
| `RESEND_API_KEY` | `re_...` (required for any PDF email — without it the PDF is built but never sent; lead status becomes `pdf_ready`) |
| `RESEND_FROM_EMAIL` | Optional. Defaults to `FlowSpace <blueprints@flowspace.solutions>` |
| `ADMIN_EMAIL` | Your email (receives admin copies) |
| `STRIPE_API_KEY` | `sk_live_...` (or `sk_test_...` for testing) |
| `STRIPE_WEBHOOK_SECRET` | Fill in after step 4 below |
| `ADMIN_PASSWORD` | Change this to a strong password |
| `JWT_SECRET` | Long random string for member session JWTs |
| `CORS_ORIGINS` | `https://flowspace.solutions,https://www.flowspace.solutions` (plus the Railway frontend origin if it is different) |

`REPLICATE_API_TOKEN` is no longer read by the after-image path. If it is already set on the Backend service, leave the secret in place — this deploy does not require deleting it.

**`OPENAI_API_KEY` on the Backend service (not the frontend):** it is already present in production. Redeploy the Backend so this release's OpenAI image path is what the process runs. Do not rotate the key for this change.

Without it, organized-after generation fails closed (`OPENAI_API_KEY is not configured`). The two files still send, using the customer's photo as a labeled interim hero when one exists.

5. Click **Deploy** — Railway builds the Docker image and starts the server
6. Note the generated URL, e.g. `https://flowspace-backend-xyz.up.railway.app`

---

## Step 3 — Deploy the Frontend on Railway

1. In the same Railway project, click **+ New Service → GitHub Repo**
2. Select `n2ether/FlowSpace` again
3. In **Settings**, set **Root Directory** to `/frontend`
4. Railway will use `railway.toml` (NIXPACKS builder)
5. Click **Variables** and add:

| Variable | Value |
|---|---|
| `REACT_APP_BACKEND_URL` | Your backend URL from Step 2 (no trailing slash) |

6. Deploy — Railway runs `npm install && npm run build && npx serve -s build`

---

## Step 4 — Configure Stripe Webhook

1. Go to **Stripe Dashboard → Developers → Webhooks → Add endpoint**
2. Endpoint URL: `https://YOUR-BACKEND.up.railway.app/api/webhook/stripe`
3. Select events: **`checkout.session.completed`**
4. Click **Add endpoint**
5. Copy the **Signing secret** (`whsec_...`)
6. Go back to Railway → Backend service → Variables → set `STRIPE_WEBHOOK_SECRET`
7. Redeploy the backend

---

## Step 5 — Configure Resend Domain

1. Go to **resend.com → Domains → Add Domain**
2. Add `flowspace.solutions`
3. Add the DNS records Resend provides to your domain registrar
4. Wait for verification (5–30 min)
5. The default From address is `blueprints@flowspace.solutions` (`RESEND_FROM_EMAIL` overrides it). Production send **will fail** until this domain is verified in Resend. Test-mode Resend keys can only send to the account owner's email.

---

## Step 6 — Point your domain to Railway

In your domain registrar's DNS settings:
- Add a **CNAME** record: `www` → your Railway frontend URL
- Add an **A** record or CNAME: `@` → your Railway frontend URL

In Railway → Frontend service → Settings → **Custom Domain** → Add `flowspace.solutions` and `www.flowspace.solutions`.

---

## Step 7 — Test the full automation

1. Visit `flowspace.solutions`
2. Click any **Get Started** button
3. Complete the questionnaire (use a real email you can check)
4. On the contact step, do NOT select a package (or select one and pay via Stripe test mode)
5. Submit — if no package selected, automation fires immediately
6. Wait ~2–3 minutes
7. Check your email — you should receive the Blueprint PDF

**If you selected a package + paid via Stripe:**
- Complete the Stripe checkout
- Stripe sends webhook to your backend
- Backend fires automation
- Customer email arrives within ~2–3 minutes

---

## How the automation works

```
Customer pays (Stripe) OR submits without package
          ↓
Stripe webhook → /api/webhook/stripe
          ↓
Background task: automation.py
          ↓
1. AI drafts design plan (Anthropic Claude ~15s)
          ↓
2. Generates room rendering (OpenAI Images edit, or text-to-image if no photo)
          ↓
3. Builds the image board and companion PDF (ReportLab, instant)
          ↓
4. Emails both files to the customer (Resend, instant)
          ↓
Lead status → "delivered"
```

---

## Admin panel

Visit `flowspace.solutions/admin/login`
Password: whatever you set in `ADMIN_PASSWORD`

From the admin panel you can:
- See all leads and their automation status (`new` / `processing` / `delivered` / `error`)
- Click **Design** on any lead to view/edit the AI-generated plan
- Click **Generate PDF** to download the Blueprint
- Click **Retry PDF email** on any lead to re-run Claude → OpenAI image → board + PDF → Resend (`POST /api/admin/leads/{id}/retry-automation`)
- Lead status: `new` → `processing` → `delivered` (email sent) or `pdf_ready` (PDF built, Resend failed) or `error`

### Rug-consistency refine for approved afters

When the organized afters show the room's rug differently from view to view, run a rug-only edit on
each approved AFTER (same OpenAI image-edit model; `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` must be set):

```bash
curl -X POST "$API/api/admin/leads/$LEAD_ID/deliverable/afters/refine" \
  -H "X-Admin-Token: $ADMIN_PASSWORD" -H "Content-Type: application/json" \
  -d '{"rug": {"color": "warm cream with a soft gray border", "pattern": "solid, thin ring near the edge"}}'
# poll until status is "done"; the report lists each view, replaced or kept, with QA reasons
curl "$API/api/admin/leads/$LEAD_ID/deliverable/afters/refine" -H "X-Admin-Token: $ADMIN_PASSWORD"
```

- The body is optional. Shape and size come from the plan's `rug` spec (`room_flows/<lead id>.json`, e.g. round, about
  5 ft / 1.5 m). Color, texture, and pattern you leave out are described from the source photos and AFTER_01 by vision.
- `"labels": ["AFTER_02"]` limits the run to some views. `?wait=true` runs inline instead of in the background.
- AFTER_01 is refined first; its rug is the reference for the other views. Each refined image must pass the
  generation vision QA and a rug check (one rug matching the spec, nothing else changed). Otherwise the existing after stays.
- SOURCE_n → AFTER_n mappings, `package_status`, and the lead status do not change, and no email is sent. The board,
  zone map, PDF, email, and contact sheet pick up the replaced afters on the next render. Old URLs are kept in `after_history`.

---

## Environment quick-reference

```
backend/.env.example   ← copy to backend/.env for local dev
frontend/.env.example  ← copy to frontend/.env for local dev
```

For local dev:
```bash
# Terminal 1 — backend
cd backend
cp .env.example .env   # fill in your keys
pip install -r requirements.txt
uvicorn server:app --reload --port 8001

# Terminal 2 — frontend
cd frontend
cp .env.example .env
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
npm install
npm start
```
