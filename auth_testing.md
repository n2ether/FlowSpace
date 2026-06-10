# Auth-Gated App Testing Playbook (FlowSpace) — Email/Password JWT

Authentication is now **email + password (JWT)**. Google OAuth has been removed.
- Token: JWT in an httpOnly cookie `access_token` (7-day). Backend also accepts `Authorization: Bearer <token>`.
- Collections: `users` (custom `user_id`, `password_hash` bcrypt `$2b$`), `password_reset_tokens`, `login_attempts`.

## Auth endpoints (all under /api/auth)
- POST `/register` {email, password (min 8), name?} → creates Free user, sets cookie, returns user
- POST `/login` {email, password} → sets cookie, returns user (5 fails = 15-min lockout, 429)
- GET `/me` → current user (401 if not authed)
- POST `/logout` → clears cookie
- POST `/forgot-password` {email, origin_url} → always returns {ok:true}; emails a reset link if the email exists (Resend)
- POST `/reset-password` {token, password} → sets new password, logs in

## Frontend login screen (single screen, /login)
- data-testids: `login-card`, `login-title`, `auth-name` (signup only), `auth-email`, `auth-password`,
  `auth-submit`, `auth-switch-btn` (toggles Sign in ↔ Sign up), `auth-forgot-link`, `auth-error`,
  `forgot-sent`, `forgot-back`, `login-back-home`.
- Reset page `/reset-password?token=...`: `reset-card`, `reset-password`, `reset-confirm`, `reset-submit`.

## Quick API test
```
curl -c ck.txt -X POST $URL/api/auth/register -H 'Content-Type: application/json' -d '{"email":"qa1@gmail.com","password":"supersecret1","name":"QA"}'
curl -b ck.txt $URL/api/auth/me
```

## Seed a logged-in session for protected-route tests
Register/login via API (above) saves the `access_token` cookie; reuse it (cookie or Bearer) to hit
`/app`, `/api/projects`, `/api/billing/*`. Plans: free=1 lifetime, pro=10/mo, premium=unlimited.
Set a user's `subscription_plan` to "pro" in Mongo to test PDF/email features without paying.

## Admin (separate, unchanged)
- /admin/login password `garage2025`. Tabs: Overview/Users/Projects/Subscriptions/Transactions/Affiliate/Gallery.

## NOTE — Replicate calls cost money; create at most ONE project via UI in tests.
