# Auth-Gated App Testing Playbook (FlowSpace)

Authentication: Emergent-managed Google OAuth.
- Cookie name: `session_token` (httpOnly). Backend also accepts `Authorization: Bearer <session_token>`.
- Collections: `users` (custom `user_id`), `user_sessions` (`session_token`, `expires_at`).

## Seed a test user + session
```python
import pymongo, datetime, uuid
c = pymongo.MongoClient("mongodb://localhost:27017")["test_database"]
uid = "user_test" + uuid.uuid4().hex[:8]
tok = "test_session_" + uuid.uuid4().hex
c.users.insert_one({
  "user_id": uid, "email": f"{uid}@example.com", "name": "Test User",
  "picture": "", "subscription_plan": "free", "stripe_customer_id": None,
  "monthly_generation_limit": 1, "monthly_generations_used": 0,
  "period_start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "is_admin": False, "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
})
c.user_sessions.insert_one({
  "user_id": uid, "session_token": tok,
  "expires_at": (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=7)).isoformat(),
  "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
})
print(uid, tok)
```

## Browser cookie for Playwright
```python
await page.context.add_cookies([{
  "name": "session_token", "value": "<TOKEN>",
  "domain": "space-transform-59.preview.emergentagent.com", "path": "/",
  "httpOnly": True, "secure": True, "sameSite": "None"
}])
```

## Key flows to test
- `/login` → Google button (cannot complete real OAuth in automation; use seeded cookie to reach `/app`).
- `/app` dashboard loads projects, shows credits/plan.
- `/app/new` → select room + style + upload photo → POST `/api/projects` → redirect to results, polls to `complete`.
- `/app/project/:id` shows before/after slider, plan steps, shopping list, affiliate links, PDF button (Pro/Premium only).
- `/app/billing` plans; checkout uses LIVE Stripe (do NOT complete a live payment in tests).
- Admin: `/admin/login` password `garage2025` → tabs (Overview, Users, Projects, Subscriptions, Transactions, Affiliate, Gallery).

## Plans / credits
free=1 lifetime (watermark, no PDF), pro=10/mo (PDF), premium=unlimited (PDF + affiliate).
To test paid features, set a seeded user's `subscription_plan` to "pro" and `monthly_generation_limit` 10.
