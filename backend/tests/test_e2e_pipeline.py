import base64
import datetime
import json
import time
import uuid

import pymongo
import requests

API = "https://space-transform-59.preview.emergentagent.com/api"
c = pymongo.MongoClient("mongodb://localhost:27017")["test_database"]

uid = "user_e2e_" + uuid.uuid4().hex[:8]
tok = "test_session_" + uuid.uuid4().hex
now = datetime.datetime.now(datetime.timezone.utc)
c.users.insert_one({
    "user_id": uid, "email": f"{uid}@example.com", "name": "E2E Tester",
    "picture": "", "subscription_plan": "pro", "stripe_customer_id": None,
    "monthly_generation_limit": 10, "monthly_generations_used": 0,
    "period_start": now.isoformat(), "is_admin": False, "created_at": now.isoformat(),
})
c.user_sessions.insert_one({
    "user_id": uid, "session_token": tok,
    "expires_at": (now + datetime.timedelta(days=7)).isoformat(), "created_at": now.isoformat(),
})
print("user", uid, "token", tok)
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

# auth/me
r = requests.get(f"{API}/auth/me", headers=H, timeout=20)
print("auth/me", r.status_code, r.json().get("subscription_plan"))

# download a real cluttered garage image -> base64 data uri
img_url = "https://customer-assets.emergentagent.com/job_space-transformed/artifacts/e8nmvr9k_cluttered_garage.png"
ib = requests.get(img_url, timeout=60).content
data_uri = "data:image/png;base64," + base64.b64encode(ib).decode()
print("image bytes", len(ib))

# create project
r = requests.post(f"{API}/projects", headers=H,
                  data=json.dumps({"room_type": "garage", "style": "modern", "photo": data_uri, "language": "en"}),
                  timeout=60)
print("create", r.status_code, r.text[:200])
pid = r.json()["id"]

# poll
for i in range(40):
    time.sleep(4)
    r = requests.get(f"{API}/projects/{pid}", headers=H, timeout=20)
    st = r.json().get("status")
    print(i, "status", st)
    if st in ("complete", "failed"):
        d = r.json()
        print("score", d.get("organization_score"), "cost", d.get("estimated_cost"),
              "pdf", bool(d.get("pdf_storage_path")), "shopping", len(d.get("shopping_list") or []))
        if st == "failed":
            print("ERROR", d.get("error"))
        break

# check images
ri = requests.get(f"{API}/projects/{pid}/image/generated", headers=H, timeout=30)
print("gen image", ri.status_code, ri.headers.get("content-type"), len(ri.content))
ro = requests.get(f"{API}/projects/{pid}/image/original", headers=H, timeout=30)
print("orig image", ro.status_code, len(ro.content))
rp = requests.get(f"{API}/projects/{pid}/pdf", headers=H, timeout=30)
print("pdf", rp.status_code, rp.headers.get("content-type"), len(rp.content))

# cleanup session/user
c.user_sessions.delete_many({"user_id": uid})
print("DONE pid", pid)
