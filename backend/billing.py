"""Stripe subscription billing for FlowSpace (live account, official SDK)."""
import logging
import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import db
from auth import get_current_user
from plans import PLAN_LIMITS, PLAN_TO_PRICE, PRICE_TO_PLAN, plan_cfg

logger = logging.getLogger(__name__)
billing_router = APIRouter(prefix="/api/billing")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")


class CheckoutReq(BaseModel):
    plan: str          # "pro" | "premium"
    origin_url: str


class PortalReq(BaseModel):
    origin_url: str


@billing_router.get("/config")
async def config():
    return {
        "publishable_key": PUBLISHABLE_KEY,
        "plans": [
            {"id": k, **{kk: vv for kk, vv in v.items()}}
            for k, v in PLAN_LIMITS.items()
        ],
    }


async def _get_or_create_customer(user: dict) -> str:
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]
    cust = stripe.Customer.create(
        email=user["email"], name=user.get("name"),
        metadata={"user_id": user["user_id"]},
    )
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"stripe_customer_id": cust.id}})
    return cust.id


@billing_router.post("/checkout")
async def checkout(payload: CheckoutReq, request: Request):
    user = await get_current_user(request)
    if payload.plan not in PLAN_TO_PRICE:
        raise HTTPException(status_code=400, detail="Invalid plan")
    price_id = PLAN_TO_PRICE[payload.plan]
    origin = payload.origin_url.rstrip("/")
    customer_id = await _get_or_create_customer(user)

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{origin}/app/billing?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/app/billing?canceled=1",
            allow_promotion_codes=True,
            metadata={"user_id": user["user_id"], "plan": payload.plan},
            subscription_data={"metadata": {"user_id": user["user_id"], "plan": payload.plan}},
        )
    except Exception as e:
        logger.exception("Stripe checkout failed")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "email": user["email"],
        "plan": payload.plan,
        "amount": PLAN_LIMITS[payload.plan]["price"],
        "currency": "usd",
        "payment_status": "initiated",
        "status": "open",
        "processed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.id}


async def _activate_plan(user_id: str, plan: str, subscription_id: str = None, customer_id: str = None):
    cfg = plan_cfg(plan)
    update = {
        "subscription_plan": plan,
        "monthly_generation_limit": cfg["limit"],
        "monthly_generations_used": 0,
        "period_start": datetime.now(timezone.utc).isoformat(),
    }
    if customer_id:
        update["stripe_customer_id"] = customer_id
    await db.users.update_one({"user_id": user_id}, {"$set": update})
    if subscription_id:
        await db.subscriptions.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id, "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id, "plan_name": plan,
                "status": "active", "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )


@billing_router.get("/status/{session_id}")
async def status(session_id: str, request: Request):
    user = await get_current_user(request)
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")

    payment_status = session.get("payment_status")
    plan = (session.get("metadata") or {}).get("plan", tx.get("plan"))

    if payment_status == "paid" and not tx.get("processed"):
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "paid", "status": "complete", "processed": True,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        await _activate_plan(
            user["user_id"], plan,
            subscription_id=session.get("subscription"),
            customer_id=session.get("customer"),
        )

    return {"payment_status": payment_status, "plan": plan,
            "status": session.get("status")}


@billing_router.post("/portal")
async def portal(payload: PortalReq, request: Request):
    user = await get_current_user(request)
    if not user.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No billing account yet")
    try:
        ps = stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"],
            return_url=f"{payload.origin_url.rstrip('/')}/app/billing",
        )
    except Exception as e:
        logger.exception("Portal failed")
        raise HTTPException(status_code=502, detail=f"Billing portal error: {e}")
    return {"url": ps.url}


@billing_router.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    if not WEBHOOK_SECRET:
        # No signing secret configured yet → cannot trust the payload.
        # The primary activation path is /billing/status (verified server-side via Stripe),
        # so we safely ignore unsigned webhooks to prevent spoofed plan upgrades.
        logger.warning("Webhook received but STRIPE_WEBHOOK_SECRET is not set; ignoring.")
        return {"received": True, "ignored": "no_webhook_secret"}
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        if obj.get("payment_status") == "paid" and meta.get("user_id"):
            await _activate_plan(meta["user_id"], meta.get("plan", "pro"),
                                 obj.get("subscription"), obj.get("customer"))
    elif etype in ("customer.subscription.deleted",):
        meta = obj.get("metadata") or {}
        uid = meta.get("user_id")
        if uid:
            await _activate_plan(uid, "free")
            await db.subscriptions.update_one({"user_id": uid}, {"$set": {"status": "canceled"}})
    elif etype == "customer.subscription.updated":
        meta = obj.get("metadata") or {}
        uid = meta.get("user_id")
        items = (obj.get("items") or {}).get("data") or []
        price_id = items[0]["price"]["id"] if items else None
        plan = PRICE_TO_PLAN.get(price_id)
        if uid and plan and obj.get("status") == "active":
            await _activate_plan(uid, plan, obj.get("id"), obj.get("customer"))

    return {"received": True}
